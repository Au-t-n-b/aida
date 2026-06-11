#!/usr/bin/env python3
"""SSH/SFTP helper for cursor-auto-deploy (Windows, no rsync)."""
from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
from pathlib import Path

import paramiko

SERVERS = {
    "198": {"host": "10.143.2.198", "user": "root", "password": "TzB!Kal7"},
    "197": {"host": "10.143.2.197", "user": "root", "password": "Xvz!DI0g"},
    "231": {"host": "10.143.2.231", "user": "root", "password": "Xvz!DI0g"},
}

# Actual deployment paths discovered on 198
PATHS_198 = {
    "clawmanager": "/home/l00617902/0604/clawmanager",
    "aida": "/opt/aida/aida",
    "build": "/opt/aida/build",
}


def connect(server: str) -> paramiko.SSHClient:
    cfg = SERVERS[server]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        cfg["host"],
        username=cfg["user"],
        password=cfg["password"],
        timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )
    return client


def run(server: str, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    client = connect(server)
    try:
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err
    finally:
        client.close()


def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def remote_md5(sftp: paramiko.SFTPClient, remote_path: str) -> str | None:
    try:
        with sftp.open(remote_path, "rb") as f:
            h = hashlib.md5()
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
            return h.hexdigest()
    except OSError:
        return None


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = []
    for part in remote_dir.replace("\\", "/").split("/"):
        if not part:
            continue
        parts.append(part)
        path = "/" + "/".join(parts)
        try:
            sftp.stat(path)
        except OSError:
            sftp.mkdir(path)


def sync_dir(
    server: str,
    local_dir: Path,
    remote_dir: str,
    excludes: set[str] | None = None,
) -> tuple[int, int]:
    excludes = excludes or set()
    client = connect(server)
    sftp = client.open_sftp()
    uploaded = 0
    skipped = 0
    try:
        ensure_remote_dir(sftp, remote_dir)
        for root, dirs, files in os.walk(local_dir):
            rel_root = Path(root).relative_to(local_dir)
            if any(x in rel_root.parts for x in excludes):
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in excludes]
            remote_root = remote_dir.rstrip("/") + "/" + str(rel_root).replace("\\", "/")
            if str(rel_root) != ".":
                ensure_remote_dir(sftp, remote_root)
            for name in files:
                if name in excludes or name.endswith(".pyc"):
                    continue
                local_path = Path(root) / name
                rel = str(local_path.relative_to(local_dir)).replace("\\", "/")
                remote_path = remote_dir.rstrip("/") + "/" + rel
                local_hash = file_md5(local_path)
                remote_hash = remote_md5(sftp, remote_path)
                if local_hash == remote_hash:
                    skipped += 1
                    continue
                ensure_remote_dir(sftp, os.path.dirname(remote_path).replace("\\", "/"))
                sftp.put(str(local_path), remote_path)
                uploaded += 1
    finally:
        sftp.close()
        client.close()
    return uploaded, skipped


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("server")
    p_run.add_argument("command")

    p_sync = sub.add_parser("sync")
    p_sync.add_argument("server")
    p_sync.add_argument("local")
    p_sync.add_argument("remote")
    p_sync.add_argument("--exclude", action="append", default=[])

    args = parser.parse_args()
    if args.cmd == "run":
        code, out, err = run(args.server, args.command)
        if out:
            print(out, end="" if out.endswith("\n") else "\n")
        if err:
            print(err, end="" if err.endswith("\n") else "\n", file=sys.stderr)
        return code
    if args.cmd == "sync":
        up, skip = sync_dir(
            args.server,
            Path(args.local),
            args.remote,
            excludes=set(args.exclude),
        )
        print(f"synced: uploaded={up} skipped={skip}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
