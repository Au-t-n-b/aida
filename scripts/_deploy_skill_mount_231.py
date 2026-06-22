#!/usr/bin/env python3
"""231：skill/org 同步 + 容器 skill 挂载 + 重建 claw 镜像 + 重启 Manager。"""
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
    "manager/registry.py",
    "deploy/claw/Dockerfile",
    "deploy/claw/claw_bootstrap.py",
    "scripts/remote_skill_org_sync.py",
    "scripts/claw_container_smoke.py",
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
    print(f"synced {n} skill files to /opt/aida/aida-data/skill/org")

    cmd = rf"""
set -e
cd {REMOTE}
export DOCKER_API_VERSION=1.42
mkdir -p /opt/aida/aida-data/skill/org
echo "=== docker build (skills via mount, not COPY) ==="
docker build --build-arg PYTHON_BASE=python:3.12-slim -f deploy/claw/Dockerfile -t aida/claw_liwen:dev . 2>&1 | tail -25
source agent/.venv/bin/activate
ss -lptn | grep ':8001' | grep -oP 'pid=\K[0-9]+' | xargs -r kill || true
sleep 2
nohup env AIDA_CLAW_ORCHESTRATION=1 DOCKER_API_VERSION=1.42 \
  python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8001 --workers 1 \
  > /tmp/manager-8001.log 2>&1 &
sleep 4
curl -sf http://127.0.0.1:8001/healthz && echo manager_ok
ls /opt/aida/aida-data/skill/org | head -5
echo DEPLOY_SKILL_MOUNT_DONE
"""
    _, o, e = c.exec_command(cmd, timeout=900)
    print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[:1500])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
