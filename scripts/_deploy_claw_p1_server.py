#!/usr/bin/env python3
"""部署 Claw P0–P2 到 10.143.2.231：上传 → docker build → smoke → 前端 build → 重启。"""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

UPLOAD_PATHS = [
    "deploy/claw/Dockerfile",
    "deploy/claw/claw_bootstrap.py",
    "scripts/remote_skill_org_sync.py",
    "deploy/claw/claw_entrypoint.sh",
    "deploy/claw/wait_nanobot_then_agent.sh",
    "deploy/claw/claw-supervisor.conf",
    "deploy/claw/.env.container.example",
    "deploy/claw/README.md",
    "deploy/nginx/claw-location.conf.tpl",
    "manager/orchestrator.py",
    "manager/registry.py",
    "manager/nginx_writer.py",
    "manager/sessions.py",
    "manager/config.py",
    "manager/main.py",
    "manager/requirements.txt",
    "manager/routes/auth.py",
    "manager/routes/chat.py",
    "manager/routes/session.py",
    "agent/nanobot_integration/bootstrap.py",
    "scripts/claw_container_smoke.py",
    "scripts/start_aida_nanobot.py",
    "frontend/src/lib/runtimeBase.ts",
    "frontend/src/lib/agentBase.ts",
    "frontend/src/lib/aida-session.tsx",
    "frontend/src/lib/claw-manager-client.ts",
    "frontend/src/components/screens/landing.tsx",
    "frontend/src/components/screens/preview.tsx",
    "frontend/src/components/screens/survey-agent.tsx",
    "frontend/src/hooks/useSduiStream.ts",
    ".dockerignore",
]

UPLOAD_DIRS = [
    "agent",
    "shared",
    "skills",
    "nanobot-main",
]


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


def _upload_tree(sftp: paramiko.SFTPClient, local_dir: Path, remote_dir: str) -> None:
    skip = {".venv", "__pycache__", ".git", "node_modules", ".pytest_cache"}
    for path in local_dir.rglob("*"):
        if path.is_dir():
            continue
        if any(part in skip for part in path.parts):
            continue
        rel = path.relative_to(local_dir).as_posix()
        remote = f"{remote_dir}/{rel}"
        _ensure_remote_parent(sftp, remote)
        sftp.put(str(path), remote)


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()

    for rel in UPLOAD_PATHS:
        local = ROOT / rel
        if not local.is_file():
            print(f"skip missing file: {rel}")
            continue
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        _ensure_remote_parent(sftp, remote)
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")

    for d in UPLOAD_DIRS:
        local = ROOT / d
        if not local.is_dir():
            print(f"skip missing dir: {d}")
            continue
        remote = f"{REMOTE}/{d}"
        print(f"uploading tree {d} ...")
        _upload_tree(sftp, local, remote)

    sftp.close()

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "remote_skill_org_sync", ROOT / "scripts" / "remote_skill_org_sync.py"
    )
    rss = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rss)
    print("=== sync agent/skills -> /opt/aida/aida-data/skill/org ===")
    n = rss.upload_agent_skills_to_org(client, clear_first=True)
    print(f"synced {n} skill files to skill/org")

    remote_script = f"""
set -e
cd {REMOTE}

# Claw 编排环境变量（追加到 agent/.env）
touch agent/.env
grep -q '^AIDA_CLAW_ORCHESTRATION=' agent/.env || echo 'AIDA_CLAW_ORCHESTRATION=1' >> agent/.env
sed -i 's/^AIDA_CLAW_ORCHESTRATION=.*/AIDA_CLAW_ORCHESTRATION=1/' agent/.env
grep -q '^CLAW_IMAGE=' agent/.env || echo 'CLAW_IMAGE=aida/claw_liwen:dev' >> agent/.env
sed -i 's|^CLAW_IMAGE=.*|CLAW_IMAGE=aida/claw_liwen:dev|' agent/.env
grep -q '^CLAW_EDGE_BASE_URL=' agent/.env || echo 'CLAW_EDGE_BASE_URL=http://10.143.2.231' >> agent/.env
sed -i 's|^CLAW_EDGE_BASE_URL=.*|CLAW_EDGE_BASE_URL=http://10.143.2.231|' agent/.env
grep -q '^CLAW_EDGE_MODE=' agent/.env || echo 'CLAW_EDGE_MODE=port' >> agent/.env
grep -q '^CLAW_DATA_MOUNT=' agent/.env || echo 'CLAW_DATA_MOUNT=/opt/aida/aida-data' >> agent/.env
sed -i 's|^CLAW_DATA_MOUNT=.*|CLAW_DATA_MOUNT=/opt/aida/aida-data|' agent/.env
grep -q '^CLAW_ENV_FILE=' agent/.env || echo 'CLAW_ENV_FILE=/opt/aida_liwen/agent/.env' >> agent/.env
sed -i 's|^CLAW_ENV_FILE=.*|CLAW_ENV_FILE=/opt/aida_liwen/agent/.env|' agent/.env
grep -q '^CLAW_PORT_POOL_START=' agent/.env || echo 'CLAW_PORT_POOL_START=17501' >> agent/.env
grep -q '^CLAW_PORT_POOL_END=' agent/.env || echo 'CLAW_PORT_POOL_END=17600' >> agent/.env
grep -q '^CLAW_IDLE_SECONDS=' agent/.env || echo 'CLAW_IDLE_SECONDS=1800' >> agent/.env

mkdir -p /opt/aida/aida-data/business /opt/aida/aida-data/runtime/checkpoints /opt/aida/aida-data/skill/org

echo "=== docker build claw ==="
export DOCKER_API_VERSION=1.42
docker build --build-arg PYTHON_BASE=python:3.12-slim -f deploy/claw/Dockerfile -t aida/claw_liwen:dev . 2>&1 | tail -40

source agent/.venv/bin/activate
pip install -q docker>=7.0.0 2>&1 | tail -3

echo "=== claw smoke ==="
export DOCKER_API_VERSION=1.42
python3 scripts/claw_container_smoke.py --build 2>&1 | tail -40

echo "=== frontend build ==="
cd frontend
export VITE_CLAWMANAGER_BASE=http://10.143.2.231:8001
export VITE_AGENT_BASE=http://10.143.2.231:7401
/usr/local/bin/npm exec vite build > /tmp/fe-claw-build.log 2>&1 || npx vite build > /tmp/fe-claw-build.log 2>&1
tail -5 /tmp/fe-claw-build.log
test -f dist/index.html && echo BUILD_OK

cd {REMOTE}
echo "=== restart stack ==="
export AIDA_CLAW_ORCHESTRATION=1
python3 scripts/start_aida_nanobot.py 2>&1 | tail -25

echo "=== manager health ==="
curl -sf http://127.0.0.1:8081/healthz || curl -sf http://127.0.0.1:8001/healthz
echo
echo DEPLOY_CLAW_DONE
"""
    _, stdout, stderr = client.exec_command(remote_script, timeout=3600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("STDERR:", err.encode("ascii", errors="backslashreplace").decode("ascii")[:4000])
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
