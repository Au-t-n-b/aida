#!/usr/bin/env python3
"""Compare local agent/ vs server /opt/aida_liwen/agent."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AGENT = ROOT / "agent"
REMOTE_AGENT = "/opt/aida_liwen/agent"
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
SKIP = {".venv", "__pycache__", "runtime", "node_modules"}


def local_files() -> set[str]:
    out: set[str] = set()
    for r, ds, fs in os.walk(LOCAL_AGENT):
        ds[:] = [d for d in ds if d not in SKIP]
        for f in fs:
            if f.endswith(".pyc"):
                continue
            p = Path(r) / f
            out.add(p.relative_to(LOCAL_AGENT).as_posix())
    return out


def remote_files() -> set[str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=20, allow_agent=False, look_for_keys=False)
    cmd = (
        f"find {REMOTE_AGENT} -type f "
        r"! -path '*/.venv/*' ! -path '*/__pycache__/*' ! -path '*/runtime/*' "
        "-printf '%P\n'"
    )
    _, stdout, _ = client.exec_command(cmd)
    lines = stdout.read().decode("utf-8", errors="replace").splitlines()
    client.close()
    return {x.strip() for x in lines if x.strip()}


def main() -> int:
    local = local_files()
    remote = remote_files()
    missing = sorted(local - remote)
    extra = sorted(remote - local)

    print(f"local_count={len(local)} remote_count={len(remote)}")
    print(f"missing_on_server={len(missing)} extra_on_server={len(extra)}")
    print("--- missing on server ---")
    for p in missing:
        print(p)
    print("--- extra on server only ---")
    for p in extra:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
