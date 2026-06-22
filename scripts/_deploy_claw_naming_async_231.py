#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"
FILES = [
    "manager/registry.py",
    "manager/orchestrator.py",
    "manager/routes/session.py",
    "manager/routes/auth.py",
    "frontend/src/lib/claw-manager-client.ts",
    "frontend/src/lib/aida-session.tsx",
    "frontend/src/components/screens/landing.tsx",
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
    cmd = f"""
set -e
cd {REMOTE}
source agent/.venv/bin/activate
python3 -c "from manager.registry import container_name; print(container_name(17, '9aef7388', 'liwen'))"
ss -lptn | grep ':8001' | grep -oP 'pid=\\K[0-9]+' | xargs -r kill || true
sleep 2
nohup env AIDA_CLAW_ORCHESTRATION=1 DOCKER_API_VERSION=1.42 \\
  python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8001 --workers 1 \\
  > /tmp/manager-8001.log 2>&1 &
sleep 4
curl -sf http://127.0.0.1:8001/healthz && echo manager_ok
cd frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:8001
export VITE_AGENT_BASE=http://{HOST}:7401
npx vite build 2>&1 | tail -2
echo DONE
"""
    _, o, e = c.exec_command(cmd, timeout=300)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[:1500])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
