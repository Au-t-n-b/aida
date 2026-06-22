#!/usr/bin/env python3
from __future__ import annotations

import paramiko


def main() -> int:
    host, user, password = "10.143.2.231", "root", "Xvz!DI0g"
    remote = "/opt/aida_liwen"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=30, allow_agent=False, look_for_keys=False)

    cmd = f"""
set -e
cd {remote}
echo '=== stop old spa_static_server ==='
pkill -f 'spa_static_server.py --host 0.0.0.0 --port 8080' || true
echo 'AFTER_PKILL'
sleep 1
echo '=== start spa_static_server ==='
test -f frontend/dist/index.html && echo FE_DIST_OK
nohup python3 scripts/spa_static_server.py --host 0.0.0.0 --port 8080 --directory frontend/dist </dev/null >/tmp/fe-spa.log 2>&1 &
sleep 2
echo '=== listeners ==='
ss -lptn | grep -E ':8080' || true
curl -s -o /dev/null -w 'frontend %{{http_code}}\\n' http://127.0.0.1:8080/login || true
echo DONE
"""

    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err[:2000])
    client.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

