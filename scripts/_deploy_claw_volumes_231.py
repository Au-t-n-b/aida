#!/usr/bin/env python3
"""231：部署 Claw 容器路径挂载（org-assets + projects/{id} → business/project）。"""
from __future__ import annotations

from pathlib import Path
import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

FILES = [
    "manager/config.py",
    "manager/registry.py",
    "manager/orchestrator.py",
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

    cmd = rf"""
set -e
cd {REMOTE}
export AIDA_CLAW_ORCHESTRATION=1 DOCKER_API_VERSION=1.42
source agent/.venv/bin/activate
python3 -c "
from manager.config import claw_container_volumes
v = claw_container_volumes('70e5ca737ae5433e9f0f3134d216acf7')
assert '/business/org-assets' in list(v.keys())[0]
assert v['/opt/aida/aida-data/business/projects/70e5ca737ae5433e9f0f3134d216acf7']['bind'] == '/opt/aida/aida-data/business/project'
print('volume_contract_ok')
"
ss -lptn | grep ':8001' | grep -oP 'pid=\K[0-9]+' | xargs -r kill || true
sleep 2
nohup env AIDA_CLAW_ORCHESTRATION=1 DOCKER_API_VERSION=1.42 \
  python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8001 --workers 1 \
  > /tmp/manager-8001.log 2>&1 &
sleep 4
curl -sf http://127.0.0.1:8001/healthz && echo manager_ok
echo DEPLOY_CLAW_VOLUMES_DONE
"""
    _, o, e = c.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("ERR:", err[:1000])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
