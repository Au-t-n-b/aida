#!/usr/bin/env python3
"""Restart full AIDA stack on server 231 (Manager + mailgw included)."""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
ROOT = "/opt/aida_liwen"


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    cmd = f"""
set -e
cd {ROOT}
source agent/.venv/bin/activate
export AIDA_USE_NANOBOT_LLM=1 AIDA_CHAT_VIA_NANOBOT=1 NANOBOT_API_URL=http://127.0.0.1:8900
export MANAGER_PORT=8081
python3 scripts/start_aida_nanobot.py 2>&1
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print(err)
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
