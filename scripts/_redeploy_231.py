#!/usr/bin/env python3
"""231 全量上传 + skill/org 同步 + 前端 build + claw 镜像 + 重启控制面栈（不动数据中心）。"""
from __future__ import annotations

import importlib.util
import os
import tarfile
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "_deploy_redeploy.tar.gz"
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "stubs", "dist"}
SKIP_REL_DIRS = {"agent/runtime"}
SKIP_SUFFIX = {".pyc"}
SKIP_FILES = {"_deploy_full.tar.gz", "_deploy_redeploy.tar.gz", "_deploy_sync.tar.gz"}


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
    print(f"packed {count} files, {ARCHIVE.stat().st_size / 1024 / 1024:.1f} MB")
    return count


def main() -> int:
    print("=== 1) pack ===")
    pack()

    print("=== 2) upload ===")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    remote_tar = "/tmp/aida_redeploy.tar.gz"
    with client.open_sftp() as sftp:
        sftp.put(str(ARCHIVE), remote_tar)
    print("uploaded", remote_tar)

    print("=== 3) extract + skill/org + build + restart ===")
    remote_script = f"""
set -e
cd {REMOTE}
tar xzf {remote_tar}
rm -f {remote_tar}
echo EXTRACT_OK

mkdir -p /opt/aida/aida-data/skill/org
rm -rf /opt/aida/aida-data/skill/org/*
cp -a {REMOTE}/agent/skills/. /opt/aida/aida-data/skill/org/
echo SKILL_ORG_SYNC files=$(find /opt/aida/aida-data/skill/org -type f | wc -l)

touch agent/.env
grep -q '^AIDA_CLAW_ORCHESTRATION=' agent/.env || echo 'AIDA_CLAW_ORCHESTRATION=1' >> agent/.env
sed -i 's/^AIDA_CLAW_ORCHESTRATION=.*/AIDA_CLAW_ORCHESTRATION=1/' agent/.env
grep -q '^CLAW_IMAGE=' agent/.env || echo 'CLAW_IMAGE=aida/claw_liwen:dev' >> agent/.env
sed -i 's|^CLAW_IMAGE=.*|CLAW_IMAGE=aida/claw_liwen:dev|' agent/.env
grep -q '^MANAGER_PORT=' agent/.env || echo 'MANAGER_PORT=8001' >> agent/.env
sed -i 's/^MANAGER_PORT=.*/MANAGER_PORT=8001/' agent/.env
grep -q '^DATA_CENTER_BASE_URL=' agent/.env || echo 'DATA_CENTER_BASE_URL=http://10.143.2.231:8000' >> agent/.env

export DOCKER_API_VERSION=1.42
echo "=== docker build claw ==="
docker build --build-arg PYTHON_BASE=python:3.12-slim -f deploy/claw/Dockerfile -t aida/claw_liwen:dev . 2>&1 | tail -20

echo "=== frontend build ==="
cd frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:8001
export VITE_AGENT_BASE=http://{HOST}:7401
/usr/local/bin/npm exec vite build > /tmp/fe-build.log 2>&1 || npx vite build > /tmp/fe-build.log 2>&1
tail -5 /tmp/fe-build.log
test -f dist/index.html && echo BUILD_OK

cd {REMOTE}
source agent/.venv/bin/activate
export AIDA_CLAW_ORCHESTRATION=1
export CLAW_IMAGE=aida/claw_liwen:dev
export MANAGER_PORT=8001
export DATA_CENTER_BASE_URL=http://10.143.2.231:8000
export DOCKER_API_VERSION=1.42
python3 scripts/start_aida_nanobot.py 2>&1

echo "=== verify ==="
ss -lptn | grep -E ':8000|:8001|:8011|:8025|:8080' || true
curl -sf http://127.0.0.1:8001/healthz && echo " manager_ok"
curl -sf -o /dev/null -w "frontend_login %{{http_code}}\\n" http://127.0.0.1:8080/login
echo REDEPLOY_231_DONE
"""
    _, stdout, stderr = client.exec_command(remote_script, timeout=1200)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[:3000].encode("ascii", errors="backslashreplace").decode("ascii"))

    spec = importlib.util.spec_from_file_location(
        "remote_skill_org_sync", ROOT / "scripts" / "remote_skill_org_sync.py"
    )
    # optional double-check count via ssh
    client.close()
    ARCHIVE.unlink(missing_ok=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
