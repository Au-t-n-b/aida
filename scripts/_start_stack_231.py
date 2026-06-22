#!/usr/bin/env python3
"""231：启动 Claw 容器编排栈（宿主机控制面：Manager / Frontend / Ontology / MailGW）。

红线：数据中心（:8000 / aida-fs）由人工运维，本脚本不启动、不停止。
"""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

CMD = rf"""
set -e
export DOCKER_API_VERSION=1.42

echo "=== datacenter status (read-only, not managed here) ==="
ss -lptn | grep -E ':8000|:8765' || echo "(datacenter ports not up yet — start manually)"

echo "=== claw container orchestration stack ==="
cd {REMOTE}
touch agent/.env
grep -q '^AIDA_CLAW_ORCHESTRATION=' agent/.env || echo 'AIDA_CLAW_ORCHESTRATION=1' >> agent/.env
sed -i 's/^AIDA_CLAW_ORCHESTRATION=.*/AIDA_CLAW_ORCHESTRATION=1/' agent/.env
grep -q '^CLAW_IMAGE=' agent/.env || echo 'CLAW_IMAGE=aida/claw_liwen:dev' >> agent/.env
sed -i 's|^CLAW_IMAGE=.*|CLAW_IMAGE=aida/claw_liwen:dev|' agent/.env
grep -q '^MANAGER_PORT=' agent/.env || echo 'MANAGER_PORT=8001' >> agent/.env
sed -i 's/^MANAGER_PORT=.*/MANAGER_PORT=8001/' agent/.env
grep -q '^DATA_CENTER_BASE_URL=' agent/.env || echo 'DATA_CENTER_BASE_URL=http://10.143.2.231:8000' >> agent/.env

source agent/.venv/bin/activate
export AIDA_CLAW_ORCHESTRATION=1
export CLAW_IMAGE=aida/claw_liwen:dev
export MANAGER_PORT=8001
export DATA_CENTER_BASE_URL=http://10.143.2.231:8000

python3 scripts/start_aida_nanobot.py 2>&1

echo "=== post-check ==="
ss -lptn | grep -E ':8001|:8011|:8025|:8080' || true
curl -sf http://127.0.0.1:8001/healthz && echo " Manager OK"
curl -sf -o /dev/null -w "frontend %{{http_code}}\n" http://127.0.0.1:8080/login
docker images aida/claw_liwen --format 'claw image {{.Repository}}:{{.Tag}}'
echo START_STACK_DONE
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    sftp.put("scripts/start_aida_nanobot.py", f"{REMOTE}/scripts/start_aida_nanobot.py")
    sftp.close()
    _, stdout, stderr = client.exec_command(CMD, timeout=180)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[:3000].encode("ascii", errors="backslashreplace").decode("ascii"))
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
