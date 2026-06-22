#!/usr/bin/env python3
"""Merge BAILIAN_* into agent/.env locally and on server, then restart stack."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "agent" / ".env"
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

BAILIAN_VARS = {
    "BAILIAN_API_KEY": "sk-d91d8863de604885a9a27cc5bd0f72f8",
    "BAILIAN_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "BAILIAN_TIMEOUT_SECONDS": "90",
    "BAILIAN_LIVENESS_TIMEOUT_SECONDS": "10",
    "BAILIAN_MAX_RETRIES": "2",
    "BAILIAN_RETRY_BACKOFF_SECONDS": "0.5",
}


def merge_env(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        m = re.match(r"^([A-Z0-9_]+)=", line)
        if m and m.group(1) in BAILIAN_VARS:
            key = m.group(1)
            out.append(f"{key}={BAILIAN_VARS[key]}")
            seen.add(key)
        else:
            out.append(line)
    if out and out[-1].strip():
        out.append("")
    if not any(l.strip().startswith("# ── 百炼") for l in out):
        out.append("# ── 百炼（阿里云 DashScope）──")
    for key, val in BAILIAN_VARS.items():
        if key not in seen:
            out.append(f"{key}={val}")
    return "\n".join(out).rstrip() + "\n"


def read_remote_env(sftp: paramiko.SFTPClient) -> str:
    remote = f"{REMOTE}/agent/.env"
    try:
        with sftp.open(remote, "r") as f:
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        example = ROOT / "agent" / ".env.example"
        if example.is_file():
            return example.read_text(encoding="utf-8")
        return ""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    base = read_remote_env(sftp)
    merged = merge_env(base)
    ENV_PATH.write_text(merged, encoding="utf-8", newline="\n")
    print(f"updated local {ENV_PATH}")
    remote_env = f"{REMOTE}/agent/.env"
    with sftp.open(remote_env, "w") as f:
        f.write(merged.encode("utf-8"))
    print(f"uploaded {remote_env}")
    sftp.close()

    cmd = f"""
set -e
cd {REMOTE}
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
        print(err, file=sys.stderr)
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
