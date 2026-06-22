#!/usr/bin/env python3
import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
CMD = r"""
echo '=== nginx edge config snippets ==='
docker exec nginx-231-edge cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -80 || true
docker exec nginx-231-edge ls /etc/nginx/conf.d/ 2>/dev/null || true
echo '=== curl edge api ==='
curl -s -o /dev/null -w 'edge80 health %{http_code}\n' http://127.0.0.1/api/v1/auth/login -X POST -H 'Content-Type: application/json' -d '{}' 2>/dev/null || true
curl -s http://127.0.0.1/healthz 2>/dev/null | head -c 200; echo
echo '=== aida-manager mount ==='
docker inspect aida-manager --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' 2>/dev/null
echo '=== host manager files ==='
ls -la /opt/aida_liwen/manager/session_resolve.py
echo '=== container manager root ==='
docker exec aida-manager pwd
docker exec aida-manager ls manager/ 2>/dev/null | head -10
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(CMD, timeout=60)
print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
c.close()
