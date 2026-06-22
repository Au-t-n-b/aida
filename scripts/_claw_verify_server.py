#!/usr/bin/env python3
"""231 完整验收：smoke + 重启 manager + enter-project 探测。"""
import json
import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"
CMD = f"""
set -e
cd {REMOTE}
export DOCKER_API_VERSION=1.42
source agent/.venv/bin/activate
pip install -q 'docker>=7.0.0'

python3 scripts/claw_container_smoke.py --build 2>&1 | tail -20

export AIDA_CLAW_ORCHESTRATION=1
pkill -f 'uvicorn manager.main' || true
sleep 2
nohup python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8081 --workers 1 > /tmp/manager-claw.log 2>&1 &
sleep 4
curl -sf http://127.0.0.1:8081/healthz | head -c 300
echo

# 探测 enter-project 路由存在
curl -sf -o /dev/null -w '%{{http_code}}' -X POST http://127.0.0.1:8081/api/v1/session/enter-project \
  -H 'Content-Type: application/json' -d '{{}}' || true
echo
echo VERIFY_DONE
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
_, o, e = c.exec_command(CMD, timeout=600)
print(o.read().decode('utf-8', errors='replace').encode('ascii', errors='backslashreplace').decode('ascii'))
c.close()
