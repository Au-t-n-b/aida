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
echo '=== pgrep spa_static_server ==='
pgrep -af spa_static_server || true
echo '=== pgrep http.server 8080 ==='
pgrep -af '8080' || true
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=60)
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

