#!/usr/bin/env python3
import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
CMD = r"""
tail -80 /tmp/manager-8001.log 2>/dev/null
echo '=== docker claw containers ==='
export DOCKER_API_VERSION=1.42
docker ps -a --filter name=claw-u --format '{{.Names}} {{.Status}} {{.Ports}}' | head -10
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(CMD, timeout=60)
print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
c.close()
