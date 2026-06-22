#!/usr/bin/env python3
"""231：重建 claw 容器 + 重启前端 SPA server（不重建镜像）。"""

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
echo '=== restart spa_static_server ==='
pkill -f 'spa_static_server.py --host 0.0.0.0 --port 8080' || true
nohup python3 scripts/spa_static_server.py --host 0.0.0.0 --port 8080 --directory frontend/dist > /tmp/fe-spa.log 2>&1 &
sleep 1
ss -lptn | grep -E ':8080' || true
curl -s -o /dev/null -w 'frontend %{{http_code}}\\n' http://127.0.0.1:8080/login || true

echo '=== remove claw containers ==='
docker ps -a --filter 'name=claw-' --format '  {{.Names}}  {{.Image}}  up={{.Status}}' || true
claws=$(docker ps -aq --filter 'name=claw-') || true
if [ -n "$claws" ]; then
  docker rm -f $claws && echo REMOVED_CLAW_CONTAINERS
else
  echo NO_CLAW_CONTAINERS
fi
echo DONE
"""

    _, stdout, stderr = client.exec_command(cmd, timeout=180, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    print(out)
    if err:
        print("STDERR:", err[:4000])
    client.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

