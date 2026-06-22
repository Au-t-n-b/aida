#!/usr/bin/env python3
"""231：部署 ClawRail chat 地址修复（动态 container_endpoint）。"""
from __future__ import annotations

from pathlib import Path
import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    sftp.put(str(ROOT / "frontend/src/components/claw-rail.tsx"), f"{REMOTE}/frontend/src/components/claw-rail.tsx")
    sftp.close()

    cmd = rf"""
set -e
cd {REMOTE}/frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:8001
export VITE_AGENT_BASE=http://{HOST}:7401
/usr/local/bin/npm exec vite build > /tmp/fe-chat-fix.log 2>&1 || npx vite build > /tmp/fe-chat-fix.log 2>&1
tail -3 /tmp/fe-chat-fix.log
test -f dist/index.html && echo BUILD_OK
# restart frontend static server
ss -lptn | grep ':8080' | grep -oP 'pid=\K[0-9]+' | xargs -r kill || true
sleep 1
cd {REMOTE}
source agent/.venv/bin/activate
nohup python3 scripts/spa_static_server.py --host 0.0.0.0 --port 8080 --directory frontend/dist \
  > /tmp/frontend-8080.log 2>&1 &
sleep 2
curl -sf -o /dev/null -w 'login %{{http_code}}\n' http://127.0.0.1:8080/login
echo DEPLOY_CHAT_FIX_DONE
"""
    _, o, e = c.exec_command(cmd, timeout=600)
    print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[:1000])
    c.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
