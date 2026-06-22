#!/usr/bin/env python3
import paramiko
CMD = r"""
cd /opt/aida_liwen
export AIDA_CLAW_ORCHESTRATION=1
source agent/.venv/bin/activate
pkill -f 'uvicorn manager.main' || true
sleep 2
nohup python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8001 --workers 1 > /tmp/manager.log 2>&1 &
sleep 4
curl -sf http://127.0.0.1:8001/healthz
echo
python3 -c 'from manager.config import claw_image; print("claw_image", claw_image())'
"""
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.231", username="root", password="Xvz!DI0g", timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(CMD, timeout=60)
print(o.read().decode())
c.close()
