#!/usr/bin/env python3
import paramiko
CMD = r"""
cd /opt/aida_liwen/frontend
export VITE_CLAWMANAGER_BASE=http://10.143.2.231:8001
export VITE_AGENT_BASE=http://10.143.2.231:7401
npx vite build 2>&1 | tail -5
test -f dist/index.html && echo FE_OK
curl -sf http://127.0.0.1:8001/healthz | head -c 200
echo
curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8001/api/v1/session/enter-project -H 'Content-Type: application/json' -d '{"session_id":"x","project_id":"K1903"}'
echo enter_no_auth
"""
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.231", username="root", password="Xvz!DI0g", timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(CMD, timeout=300)
print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
c.close()
