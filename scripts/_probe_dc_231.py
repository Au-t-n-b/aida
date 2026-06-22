#!/usr/bin/env python3
import paramiko
CMD = r"""
ls -la /opt/aida/aida-data-center/.venv/ 2>&1
ls -la /opt/aida/aida-data-center/.venv/bin/ 2>&1 | head -15
/usr/local/bin/uvicorn --version
head -3 /opt/aida/aida-data-center/datacenter_backend.log
ps aux | grep 'app.main' | grep -v grep
"""
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.231", username="root", password="Xvz!DI0g", timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(CMD, timeout=30)
print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
c.close()
