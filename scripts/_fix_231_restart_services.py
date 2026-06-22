#!/usr/bin/env python3
"""231：重启宿主机服务 + 强制 claw 容器采用新镜像。

用于上一次增量部署后，frontend/host 服务未起来或 claw 仍在旧镜像的兜底修复。
"""

from __future__ import annotations

import sys
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

echo '=== 1) kill old host services (keep datacenter) ==='
pkill -f 'spa_static_server.py --host 0.0.0.0 --port 8080' || true
pkill -f 'uvicorn ontology' || true
pkill -f 'mailgw' || true
# manager 在跑也可以重启；这里温和处理，避免端口冲突
pkill -f 'uvicorn manager.main' || true
sleep 2

echo '=== 2) start host stack ==='
export AIDA_CLAW_ORCHESTRATION=1
source agent/.venv/bin/activate
nohup python3 scripts/start_aida_nanobot.py --no-stop > /tmp/aida-restart.log 2>&1 &
sleep 4

echo '=== 3) ensure frontend spa ==='
cd {remote}/frontend
test -f dist/index.html && echo FE_DIST_OK || (echo FE_DIST_MISSING && exit 1)
cd {remote}
nohup python3 scripts/spa_static_server.py --host 0.0.0.0 --port 8080 --directory frontend/dist > /tmp/fe-spa.log 2>&1 &
sleep 2

echo '=== 4) remove claw containers (pick new image on next enter-project) ==='
claws=$(docker ps -aq --filter 'name=claw-') || true
if [ -n "$claws" ]; then
  docker rm -f $claws && echo REMOVED_CLAW_CONTAINERS
else
  echo NO_CLAW_CONTAINERS
fi

echo '=== 5) listeners ==='
ss -lptn | grep -E ':8080|:8001|:8011|:8025' || true
echo '=== 6) curls ==='
curl -s -o /dev/null -w 'frontend %{{http_code}}\\n' http://127.0.0.1:8080/login || true
curl -s -o /dev/null -w 'manager %{{http_code}}\\n' http://127.0.0.1:8001/healthz || true
curl -s -o /dev/null -w 'ontology %{{http_code}}\\n' http://127.0.0.1:8011/healthz || true
curl -s -o /dev/null -w 'mailgw %{{http_code}}\\n' http://127.0.0.1:8025/healthz || true
echo DONE
"""

    _, stdout, stderr = client.exec_command(cmd, timeout=240)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write(err[:4000])
    client.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

