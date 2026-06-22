#!/usr/bin/env python3
"""231：部署 Claw 启动优化 + 前端准备中遮罩。"""
from __future__ import annotations

from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

FILES = [
    "agent/main.py",
    "agent/nanobot_integration/bootstrap.py",
    "manager/orchestrator.py",
    "manager/routes/session.py",
    "deploy/claw/claw_bootstrap.py",
    "deploy/claw/claw_entrypoint.sh",
    "deploy/claw/Dockerfile",
    "frontend/src/components/screens/landing.tsx",
    "frontend/src/styles/globals.css",
]


def _ensure_parent(sftp, remote: str) -> None:
    parent = remote.rsplit("/", 1)[0]
    parts: list[str] = []
    for part in parent.split("/"):
        if not part:
            continue
        parts.append(part)
        path = "/" + "/".join(parts)
        try:
            sftp.stat(path)
        except OSError:
            try:
                sftp.mkdir(path)
            except OSError:
                pass


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    for rel in FILES:
        local = ROOT / rel
        remote = f"{REMOTE}/{rel}"
        _ensure_parent(sftp, remote)
        sftp.put(str(local), remote)
        print("uploaded", rel)
    sftp.close()

    cmd = rf"""
set -e
cd {REMOTE}
export DOCKER_API_VERSION=1.42
source agent/.venv/bin/activate

echo "=== rebuild claw image ==="
docker build --build-arg PYTHON_BASE=python:3.12-slim -f deploy/claw/Dockerfile -t aida/claw_liwen:dev . 2>&1 | tail -15

echo "=== frontend build ==="
cd frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:8001
export VITE_AGENT_BASE=http://{HOST}:7401
npx vite build 2>&1 | tail -3
test -f dist/index.html && echo FE_OK

echo "=== restart manager :8001 ==="
cd {REMOTE}
ss -lptn | grep ':8001' | grep -oP 'pid=\K[0-9]+' | xargs -r kill || true
sleep 2
nohup env AIDA_CLAW_ORCHESTRATION=1 DOCKER_API_VERSION=1.42 \
  python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8001 --workers 1 \
  > /tmp/manager-8001.log 2>&1 &
sleep 4
curl -sf http://127.0.0.1:8001/healthz && echo manager_ok

echo DEPLOY_CLAW_SPEED_UI_DONE
"""
    _, o, e = c.exec_command(cmd, timeout=3600)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("ERR:", err[:3000])
    c.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
