#!/usr/bin/env python3
"""231 上仅执行 docker build + smoke（已上传代码后）。"""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

CMD = f"""
set -e
cd {REMOTE}
export DOCKER_API_VERSION=1.42
mkdir -p /opt/aida/aida-data/business /opt/aida/aida-data/runtime/checkpoints
echo BUILD_START
docker build --build-arg PYTHON_BASE=python:3.12-slim -f deploy/claw/Dockerfile -t aida/claw_liwen:dev . 2>&1 | tail -40
source agent/.venv/bin/activate
pip install -q 'docker>=7.0.0'
python3 scripts/claw_container_smoke.py --build 2>&1 | tail -50
echo BUILD_SMOKE_DONE
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
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
