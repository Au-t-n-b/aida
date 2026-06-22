#!/usr/bin/env python3
"""231：部署 Claw 容器生命周期修复（活跃会话不回收 + 心跳重绑 + 前端保活）。"""
from __future__ import annotations

from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"
MANAGER_PORT = 8001

UPLOAD_FILES = [
    "manager/orchestrator.py",
    "manager/sessions.py",
    "manager/routes/session.py",
    "frontend/src/lib/aida-session.tsx",
    "frontend/src/lib/claw-manager-client.ts",
    "frontend/src/routes/workspace-shell.tsx",
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

echo "=== frontend build ==="
cd {REMOTE}/frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:{MANAGER_PORT}
export VITE_AGENT_BASE=http://{HOST}:7401
npx vite build 2>&1 | tail -8
test -f dist/index.html && echo FE_BUILD_OK

echo "=== restart control plane (no datacenter) ==="
cd {REMOTE}
touch agent/.env
grep -q '^AIDA_CLAW_ORCHESTRATION=' agent/.env || echo 'AIDA_CLAW_ORCHESTRATION=1' >> agent/.env
sed -i 's/^AIDA_CLAW_ORCHESTRATION=.*/AIDA_CLAW_ORCHESTRATION=1/' agent/.env
grep -q '^MANAGER_PORT=' agent/.env || echo 'MANAGER_PORT={MANAGER_PORT}' >> agent/.env
sed -i 's/^MANAGER_PORT=.*/MANAGER_PORT={MANAGER_PORT}/' agent/.env

source agent/.venv/bin/activate
export AIDA_CLAW_ORCHESTRATION=1
export CLAW_IMAGE=aida/claw_liwen:dev
export MANAGER_PORT={MANAGER_PORT}
export DATA_CENTER_BASE_URL=http://{HOST}:8000
python3 scripts/start_aida_nanobot.py 2>&1

echo "=== verify ==="
ss -lptn | grep -E ':8001|:8011|:8025|:8080' || true
curl -sf http://127.0.0.1:{MANAGER_PORT}/healthz && echo " manager_ok"
curl -sf -o /dev/null -w "frontend %{{http_code}}\\n" http://127.0.0.1:8080/login
docker ps --filter name=aida-claw --format 'claw {{.Names}} {{.Status}}' || true
echo DEPLOY_CLAW_LIFECYCLE_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=600)
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
