#!/usr/bin/env python3
"""Pack entire aida_project_new tree and deploy to server 231."""
from __future__ import annotations

import os
import tarfile
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "_deploy_full.tar.gz"
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

# 遍历时跳过的目录名（任意层级）
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    "stubs",  # frontend/src/stubs 本地占位
    "dist",  # frontend/dist 服务器上 npm build 重建
}
# 仅跳过该相对路径（LangGraph checkpoint，勿与 a3_engine/runtime 等源码混淆）
SKIP_REL_DIRS = {"agent/runtime"}
SKIP_SUFFIX = {".pyc"}
SKIP_FILES = {
    "_deploy_full.tar.gz",
    "_deploy_sync.tar.gz",
}


def should_skip_dir(parent: Path, name: str) -> bool:
    if name in SKIP_DIRS:
        return True
    if name == "runtime":
        try:
            rel = (parent / name).relative_to(ROOT).as_posix()
        except ValueError:
            return True
        return rel in SKIP_REL_DIRS
    return False


def ok(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        return False
    if path.name in SKIP_FILES:
        return False
    return path.suffix not in SKIP_SUFFIX


def pack() -> int:
    count = 0
    with tarfile.open(ARCHIVE, "w:gz") as tar:
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if not should_skip_dir(Path(root), d)]
            for name in files:
                p = Path(root) / name
                if not ok(p):
                    continue
                tar.add(p, arcname=p.relative_to(ROOT).as_posix())
                count += 1
    print(f"packed {count} files, archive={ARCHIVE.stat().st_size / 1024 / 1024:.1f}MB")
    return count


def main() -> int:
    print("=== packing entire project ===")
    pack()

    print("=== connect server ===")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    _, out, _ = client.exec_command("df -h /opt | tail -1")
    print("disk:", out.read().decode().strip())

    print("=== uploading ===")
    remote_tar = "/tmp/aida_deploy_full.tar.gz"
    with client.open_sftp() as sftp:
        sftp.put(str(ARCHIVE), remote_tar)
    print("uploaded", remote_tar)

    remote_script = f"""
set -e
cd {REMOTE}
if [ -d data ]; then echo before_data=$(du -sh data | cut -f1); else echo before_data=none; fi
tar xzf {remote_tar}
rm -f {remote_tar}
echo after_data=$(du -sh data | cut -f1)
echo project_size=$(du -sh . | cut -f1)
echo EXTRACT_OK
mkdir -p /opt/aida/aida-data/skill/org
rm -rf /opt/aida/aida-data/skill/org/*
cp -a {REMOTE}/agent/skills/. /opt/aida/aida-data/skill/org/
echo SKILL_ORG_SYNC_OK
cd frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:8081
export VITE_AGENT_BASE=http://{HOST}:7401
/usr/local/bin/npm exec vite build > /tmp/fe-build.log 2>&1 || npx vite build > /tmp/fe-build.log 2>&1
tail -3 /tmp/fe-build.log
test -f dist/index.html && echo BUILD_OK
cd {REMOTE}
source agent/.venv/bin/activate
echo === reset zhgk workspace before restart ===
python3 agent/scripts/reset_zhgk_workspace.py
echo RESET_OK
export AIDA_USE_NANOBOT_LLM=1 AIDA_CHAT_VIA_NANOBOT=1 NANOBOT_API_URL=http://127.0.0.1:8900
export MANAGER_PORT=8081
python3 scripts/start_aida_nanobot.py 2>&1
"""
    print("=== extract, build, restart ===")
    _, stdout, stderr = client.exec_command(remote_script, timeout=900)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    safe_out = out.encode("ascii", errors="backslashreplace").decode("ascii")
    print(safe_out)
    if err.strip():
        print(err, file=__import__("sys").stderr)
    client.close()
    ARCHIVE.unlink(missing_ok=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
