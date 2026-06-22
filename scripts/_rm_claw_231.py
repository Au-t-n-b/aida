#!/usr/bin/env python3
from __future__ import annotations

import paramiko


def main() -> int:
    host, user, password = "10.143.2.231", "root", "Xvz!DI0g"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=30, allow_agent=False, look_for_keys=False)
    cmd = r"""
set -e
echo '=== claw containers before ==='
docker ps -a --filter 'name=claw-' --format '{{.Names}} {{.Image}} {{.Status}}' || true
claws=$(docker ps -aq --filter 'name=claw-') || true
if [ -n "$claws" ]; then
  docker rm -f $claws
  echo REMOVED
fi
echo '=== claw containers after ==='
docker ps -a --filter 'name=claw-' --format '{{.Names}} {{.Image}} {{.Status}}' || true
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

