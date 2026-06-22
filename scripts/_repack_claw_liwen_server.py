#!/usr/bin/env python3
"""231：镜像改名为 aida/claw_liwen:dev → 清理旧容器 → 重打包 → smoke。"""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"
IMAGE = "aida/claw_liwen:dev"

CMD = f"""
set -e
cd {REMOTE}
export DOCKER_API_VERSION=1.42

echo "=== stop old claw containers ==="
docker ps -aq --filter name=claw- | xargs -r docker rm -f
docker ps -aq --filter name=claw-u | xargs -r docker rm -f

echo "=== update CLAW_IMAGE ==="
touch agent/.env
sed -i 's|^CLAW_IMAGE=.*|CLAW_IMAGE={IMAGE}|' agent/.env || echo 'CLAW_IMAGE={IMAGE}' >> agent/.env
grep '^CLAW_IMAGE=' agent/.env

echo "=== docker build {IMAGE} ==="
docker build --build-arg PYTHON_BASE=python:3.12-slim \\
  -f deploy/claw/Dockerfile -t {IMAGE} . 2>&1 | tail -25

echo "=== smoke ==="
source agent/.venv/bin/activate
python3 scripts/claw_container_smoke.py --build 2>&1 | tail -15

echo "=== images ==="
docker images | grep -E 'claw|REPOSITORY' | head -6

echo "=== restart manager (pick up CLAW_IMAGE) ==="
export AIDA_CLAW_ORCHESTRATION=1
pkill -f 'uvicorn manager.main' || true
sleep 2
nohup python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8001 --workers 1 > /tmp/manager-claw.log 2>&1 &
sleep 3
curl -sf http://127.0.0.1:8001/healthz | head -c 200
echo
echo REPACK_CLAW_LIWEN_DONE
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    sftp = client.open_sftp()
    for rel in (
        "manager/config.py",
        "scripts/claw_container_smoke.py",
        "deploy/claw/Dockerfile",
    ):
        sftp.put(rel, f"{REMOTE}/{rel}")
    sftp.close()

    _, stdout, stderr = client.exec_command(CMD, timeout=3600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[:2000])
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
