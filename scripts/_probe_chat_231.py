#!/usr/bin/env python3
import json
import paramiko

CMD = r"""
port=$(docker ps --filter name=aida-claw -q | head -1 | xargs -I{} docker port {} 7401/tcp 2>/dev/null | head -1 | awk -F: '{print $NF}')
echo claw_port=$port
if [ -n "$port" ]; then
  curl -sf http://127.0.0.1:$port/healthz/ready && echo ready_ok
  curl -s -o /tmp/chat_test.txt -w 'chat_http %{http_code}\n' -X POST http://127.0.0.1:$port/agent/chat/stream \
    -H 'Content-Type: application/json' \
    -d '{"message":"ping","conv_id":"test","context":{}}' --max-time 15 | head -3
  head -5 /tmp/chat_test.txt 2>/dev/null
fi
echo host_7401:
curl -s -o /dev/null -w '%{http_code}\n' --connect-timeout 2 http://127.0.0.1:7401/healthz || echo refused
grep VITE_AGENT_BASE /opt/aida_liwen/frontend/dist/assets/*.js 2>/dev/null | head -1 || strings /opt/aida_liwen/frontend/dist/assets/*.js 2>/dev/null | grep -E '7401|8001' | head -5
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.231", username="root", password="Xvz!DI0g", timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(CMD, timeout=60)
print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
c.close()
