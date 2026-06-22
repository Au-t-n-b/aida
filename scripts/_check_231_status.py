#!/usr/bin/env python3
"""Quick status check on 231 (docker + services)."""

from __future__ import annotations

import sys

import paramiko


def main() -> int:
    do_fix = "--fix" in sys.argv
    host, user, password = "10.143.2.231", "root", "Xvz!DI0g"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user,
        password=password,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )

    cmd = r"""
set -e
cd /opt/aida_liwen
"""

    if do_fix:
        cmd += r"""
echo '=== FIX: restart spa_static_server ==='
pkill -f 'spa_static_server.py --host 0.0.0.0 --port 8080' || true
nohup python3 scripts/spa_static_server.py --host 0.0.0.0 --port 8080 --directory frontend/dist > /tmp/fe-spa.log 2>&1 &
sleep 1
echo '=== FIX: remove claw containers ==='
claws=$(docker ps -aq --filter 'name=claw-') || true
if [ -n "$claws" ]; then docker rm -f $claws || true; fi
"""

    cmd += r"""
echo '=== docker image aida/claw_liwen:dev ==='
docker image inspect -f '{{.Id}} {{.RepoTags}}' aida/claw_liwen:dev || true

echo '=== claw containers ==='
docker ps -a --filter 'name=claw-' --format '{{.Names}} {{.Image}} {{.Status}}' || true

echo '=== frontend ==='
curl -s -o /dev/null -w 'frontend %{http_code}\n' http://127.0.0.1:8080/login || true

echo '=== manager ==='
curl -s -o /dev/null -w 'manager %{http_code}\n' http://127.0.0.1:8001/healthz || true

echo '=== agent ready (host) ==='
curl -s -o /dev/null -w 'agent-ready %{http_code}\n' http://127.0.0.1:7401/healthz/ready || true

echo '=== listeners ==='
ss -lptn | grep -E ':8080|:7401|:8900|:8001' || true

echo '=== processes (top) ==='
ps -eo pid,etime,cmd --sort=-lstart | head -n 25 || true

echo '=== frontend log tail (/tmp/fe-spa.log) ==='
tail -n 80 /tmp/fe-spa.log 2>/dev/null || true

echo '=== claw container last logs ==='
name=$(docker ps --filter 'name=claw-' --format '{{.Names}}' | head -n 1)
if [ -n "$name" ]; then
  docker logs --tail 60 "$name" 2>/dev/null || true
fi

echo 'DONE'
"""

    _, stdout, stderr = client.exec_command(cmd, timeout=120)
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

