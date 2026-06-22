#!/usr/bin/env python3
"""231：修复部署调测导航 + 挂载 software_deployment 工作区。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

FILES = [
    "manager/config.py",
    "manager/orchestrator.py",
    "agent/skills/software_deployment/SKILL.md",
    "scripts/remote_skill_org_sync.py",
]


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    for rel in FILES:
        sftp.put(str(ROOT / rel), f"{REMOTE}/{rel}")
        print("uploaded", rel)
    sftp.close()

    spec = importlib.util.spec_from_file_location(
        "remote_skill_org_sync", ROOT / "scripts" / "remote_skill_org_sync.py"
    )
    rss = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rss)
    n = rss.upload_agent_skills_to_org(c, clear_first=True)
    print(f"synced {n} files to skill/org")

    cmd = rf"""
set -e
cd {REMOTE}
source agent/.venv/bin/activate
ss -lptn | grep ':8001' | grep -oP 'pid=\K[0-9]+' | xargs -r kill || true
sleep 2
nohup env AIDA_CLAW_ORCHESTRATION=1 DOCKER_API_VERSION=1.42 AIDA_REPO_ROOT={REMOTE} \
  python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8001 --workers 1 \
  > /tmp/manager-8001.log 2>&1 &
sleep 3
curl -sf http://127.0.0.1:8001/healthz && echo manager_ok
test -f /opt/aida/aida-data/skill/org/software_deployment/SKILL.md && echo skill_md_on_org_ok
echo FIX_DEPLOY_SD_DONE
"""
    _, o, _ = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
