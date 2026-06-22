#!/usr/bin/env python3
"""增量部署：仅上传指定文件，服务器 build + restart。

重启走 scripts/start_aida_nanobot.py，固定拉起 README 要求的全栈服务：
  nanobot :8900 · AIDA :7401 · Manager :8081 · ontology :8011 · mailgw :8025 · frontend :8080
"""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

DEFAULT_FILES = [
    "frontend/src/components/screens/landing.tsx",
    "frontend/src/components/screens/preview.tsx",
    "frontend/src/components/screens/survey-agent.tsx",
    "frontend/src/router.tsx",
    "skills/device_install/SKILL.md",
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
    files = sys.argv[1:] or DEFAULT_FILES
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    for rel in files:
        local = ROOT / rel
        if not local.is_file():
            print(f"skip missing: {rel}")
            continue
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        _ensure_remote_parent(sftp, remote)
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")
    sftp.close()

    cmd = f"""
set -e
cd {REMOTE}/frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:8081
export VITE_AGENT_BASE=http://{HOST}:7401
/usr/local/bin/npm exec vite build > /tmp/fe-build.log 2>&1 || npx vite build > /tmp/fe-build.log 2>&1
tail -3 /tmp/fe-build.log
test -f dist/index.html && echo BUILD_OK
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
