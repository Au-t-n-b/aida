#!/usr/bin/env python3
"""231：部署对话 think 内容过滤（后端 SSE + 前端展示）。"""
from __future__ import annotations

from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"
MANAGER_PORT = 8001

UPLOAD_FILES = [
    "agent/chat_sanitize.py",
    "agent/chat_engine.py",
    "frontend/src/lib/strip-thinking.ts",
    "frontend/src/components/claw-rail.tsx",
    "frontend/src/hooks/useChatStream.ts",
    "frontend/src/routes/chat.tsx",
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


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    for rel in UPLOAD_FILES:
        local = ROOT / rel
        if not local.is_file():
            print(f"MISSING local: {rel}")
            return 1
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        _ensure_remote_parent(sftp, remote)
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")
    sftp.close()

    cmd = f"""
set -e
export DOCKER_API_VERSION=1.42
cd {REMOTE}

echo "=== docker build claw (chat_sanitize in image) ==="
cd {REMOTE}
export DOCKER_API_VERSION=1.42
docker build --build-arg PYTHON_BASE=python:3.12-slim -f deploy/claw/Dockerfile -t aida/claw_liwen:dev . 2>&1 | tail -15
docker images aida/claw_liwen:dev --format 'claw_image {{.Repository}}:{{.Tag}} {{.ID}}'

echo "=== frontend build ==="
cd {REMOTE}/frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:{MANAGER_PORT}
export VITE_AGENT_BASE=http://{HOST}:7401
npx vite build 2>&1 | tail -8
test -f dist/index.html && echo FE_BUILD_OK

echo "=== restart control plane (no datacenter) ==="
cd {REMOTE}
source agent/.venv/bin/activate
export AIDA_CLAW_ORCHESTRATION=1
export CLAW_IMAGE=aida/claw_liwen:dev
export MANAGER_PORT={MANAGER_PORT}
export DATA_CENTER_BASE_URL=http://{HOST}:8000
python3 scripts/start_aida_nanobot.py 2>&1

echo "=== verify ==="
curl -sf http://127.0.0.1:{MANAGER_PORT}/healthz && echo " manager_ok"
curl -sf -o /dev/null -w "frontend %{{http_code}}\\n" http://127.0.0.1:8080/login
python3 -c "from agent.chat_sanitize import strip_thinking_content; assert strip_thinking_content('<think>x</think>hi')=='hi'; print('sanitize_ok')"
echo DEPLOY_THINK_STRIP_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=1200)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[:4000].encode("ascii", errors="backslashreplace").decode("ascii"))
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
