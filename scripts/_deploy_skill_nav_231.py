#!/usr/bin/env python3
"""231：部署对话 skill_launch 后自动跳转作业模块（P0）。"""
from __future__ import annotations

from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"
MANAGER_PORT = 8001

UPLOAD_FILES = [
    "frontend/src/data/skill-registry.ts",
    "frontend/src/components/claw-rail.tsx",
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
cd {REMOTE}/frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:{MANAGER_PORT}
export VITE_AGENT_BASE=http://{HOST}:7401
npx vite build 2>&1 | tail -8
test -f dist/index.html && echo FE_BUILD_OK

cd {REMOTE}
source agent/.venv/bin/activate
pkill -f 'spa_static_server.py --host 0.0.0.0 --port 8080' || true
sleep 1
nohup python3 scripts/spa_static_server.py --host 0.0.0.0 --port 8080 --directory frontend/dist > /tmp/fe-spa.log 2>&1 &
sleep 2
curl -sf -o /dev/null -w "frontend %{{http_code}}\\n" http://127.0.0.1:8080/login
echo DEPLOY_SKILL_NAV_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[:2000].encode("ascii", errors="backslashreplace").decode("ascii"))
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
