#!/usr/bin/env python3
import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.231", username="root", password="Xvz!DI0g", timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(
    "docker stop nginx-231-edge nginx-231-a nginx-231-b 2>/dev/null; "
    "docker ps -a --format '{{.Names}} {{.Status}}'; "
    "ss -lptn | grep -E ':80|:443|:8000|:8080|:8001|:7401|:7402' || echo ports_clear",
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
