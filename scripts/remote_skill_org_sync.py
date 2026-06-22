#!/usr/bin/env python3
"""将本地 agent/skills 同步到服务器 /opt/aida/aida-data/skill/org（先清空再上传）。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SKILLS = ROOT / "agent" / "skills"
DEFAULT_REMOTE_ORG = "/opt/aida/aida-data/skill/org"
DEFAULT_HOST = "10.143.2.231"
DEFAULT_USER = "root"
DEFAULT_PASSWORD = "Xvz!DI0g"
SKIP_PARTS = {".venv", "__pycache__", ".pytest_cache", ".git", "node_modules"}


def _ensure_remote_parent(sftp: paramiko.SFTPClient, remote: str) -> None:
    parent = remote.rsplit("/", 1)[0]
    parts: list[str] = []
    for part in parent.split("/"):
        if not part:
            continue
        parts.append(part)
        path = "/" + "/".join(parts)
        try:
            sftp.stat(path)
        except OSError:
            try:
                sftp.mkdir(path)
            except OSError:
                pass


def _iter_local_skill_files() -> list[Path]:
    if not LOCAL_SKILLS.is_dir():
        raise FileNotFoundError(f"local skills dir not found: {LOCAL_SKILLS}")
    files: list[Path] = []
    for path in LOCAL_SKILLS.rglob("*"):
        if path.is_dir():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix == ".pyc":
            continue
        files.append(path)
    # 补齐仅存在于 skills/<name>/SKILL.md 的 manifest（如 software_deployment）
    legacy_skills = ROOT / "skills"
    if legacy_skills.is_dir():
        for md in legacy_skills.glob("*/SKILL.md"):
            name = md.parent.name
            if name.startswith("_"):
                continue
            colocated = LOCAL_SKILLS / name / "SKILL.md"
            if not colocated.is_file():
                files.append(md)
    return files


def clear_remote_org(client: paramiko.SSHClient, remote_org: str) -> None:
    cmd = f"mkdir -p {remote_org} && rm -rf {remote_org}/*"
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    code = stdout.channel.recv_exit_status()
    if code != 0:
        err = stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"clear {remote_org} failed ({code}): {err}")


def upload_agent_skills_to_org(
    client: paramiko.SSHClient,
    *,
    remote_org: str = DEFAULT_REMOTE_ORG,
    clear_first: bool = True,
) -> int:
    if clear_first:
        clear_remote_org(client, remote_org)
    sftp = client.open_sftp()
    count = 0
    for path in _iter_local_skill_files():
        if path.is_relative_to(LOCAL_SKILLS):
            rel = path.relative_to(LOCAL_SKILLS).as_posix()
        else:
            rel = path.relative_to(ROOT / "skills").as_posix()
        remote = f"{remote_org}/{rel}"
        _ensure_remote_parent(sftp, remote)
        sftp.put(str(path), remote)
        count += 1
    sftp.close()
    return count


def copy_from_liwen_on_server(
    client: paramiko.SSHClient,
    *,
    liwen_root: str = "/opt/aida_liwen",
    remote_org: str = DEFAULT_REMOTE_ORG,
) -> None:
    """服务器上从 /opt/aida_liwen/agent/skills 复制到 skill/org（全量部署后用）。"""
    cmd = rf"""
set -e
mkdir -p {remote_org}
rm -rf {remote_org}/*
test -d {liwen_root}/agent/skills
cp -a {liwen_root}/agent/skills/. {remote_org}/
echo SKILL_ORG_COPY_OK files=$(find {remote_org} -type f | wc -l)
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.strip())
    if code != 0:
        raise RuntimeError(f"copy skills on server failed ({code}): {err}")


def connect(
    host: str,
    user: str,
    password: str,
) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=30, allow_agent=False, look_for_keys=False)
    return client


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync agent/skills → server skill/org")
    parser.add_argument("--host", default=os.environ.get("AIDA_DEPLOY_HOST", DEFAULT_HOST))
    parser.add_argument("--user", default=os.environ.get("AIDA_DEPLOY_USER", DEFAULT_USER))
    parser.add_argument("--password", default=os.environ.get("AIDA_DEPLOY_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument("--remote-org", default=DEFAULT_REMOTE_ORG)
    parser.add_argument(
        "--from-liwen",
        action="store_true",
        help="copy from /opt/aida_liwen/agent/skills on server instead of uploading from local",
    )
    args = parser.parse_args()

    client = connect(args.host, args.user, args.password)
    try:
        if args.from_liwen:
            copy_from_liwen_on_server(client, remote_org=args.remote_org)
        else:
            n = upload_agent_skills_to_org(client, remote_org=args.remote_org, clear_first=True)
            print(f"uploaded {n} files to {args.remote_org}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
