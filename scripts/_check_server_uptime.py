#!/usr/bin/env python3
"""Check latest start time of AIDA services on server 231."""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"

SCRIPT = r"""
echo '=== server time ==='
date '+%Y-%m-%d %H:%M:%S %Z'
echo
echo '=== aida_liwen processes (newest first) ==='
ps -eo pid,lstart,etime,cmd --sort=-lstart | grep '/opt/aida_liwen' | grep -v grep
echo
echo '=== nanobot + spa_static ==='
ps -eo pid,lstart,etime,cmd --sort=-lstart | grep -E 'nanobot serve|spa_static_server' | grep -v grep
echo
echo '=== ontology (8011) ==='
ps -eo pid,lstart,etime,cmd --sort=-lstart | grep 'backend_app:app' | grep -v grep | head -3
echo
echo '=== listening ports ==='
ss -tlnp | egrep '7401|8080|8081|8900|8011|8025' || true
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    _, out, err = c.exec_command(SCRIPT, timeout=60)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("ERR:", e)
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
