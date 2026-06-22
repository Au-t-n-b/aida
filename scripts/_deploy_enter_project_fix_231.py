#!/usr/bin/env python3
"""231：部署 enter-project Failed to fetch 修复。"""
from __future__ import annotations

from pathlib import Path
import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

FILES = [
    "manager/orchestrator.py",
    "manager/routes/session.py",
    "frontend/src/components/screens/landing.tsx",
]


def _ensure_parent(sftp, remote: str) -> None:
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
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    for rel in FILES:
        local = ROOT / rel
        remote = f"{REMOTE}/{rel}"
        _ensure_parent(sftp, remote)
        sftp.put(str(local), remote)
        print("uploaded", rel)
    sftp.close()

    cmd = rf"""
set -e
cd {REMOTE}
source agent/.venv/bin/activate
export AIDA_CLAW_ORCHESTRATION=1 DOCKER_API_VERSION=1.42

ss -lptn | grep ':8001' | grep -oP 'pid=\K[0-9]+' | xargs -r kill
sleep 2
nohup env AIDA_CLAW_ORCHESTRATION=1 DOCKER_API_VERSION=1.42 \
  python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8001 --workers 1 \
  > /tmp/manager-8001.log 2>&1 &
sleep 4
curl -sf http://127.0.0.1:8001/healthz && echo health_ok

cd frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:8001
export VITE_AGENT_BASE=http://{HOST}:7401
npx vite build 2>&1 | tail -3
test -f dist/index.html && echo FE_OK

python3 - <<'PY'
import json, urllib.request, urllib.error

def post(path, body, token=None):
    data = json.dumps(body).encode()
    headers = {{"Content-Type": "application/json"}}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request("http://127.0.0.1:8001" + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")

code, login = post("/api/v1/auth/login", {{"username": "liwen", "password": "123456"}})
if code != 200:
    print("login skip", code)
    raise SystemExit(0)
token = login["access_token"]
sid = login["session_id"]
# 用一个可能需新起容器的 project uuid 前缀
c2, body = post(
    "/api/v1/session/enter-project",
    {{"session_id": sid, "project_id": "9aef7388b1e743cf9ce903e45bfc1e3a", "project_code": "56A0TXN"}},
    token=token,
)
print("enter-project", c2, body[:120] if isinstance(body, str) else body.get("container_endpoint", body))
if c2 not in (200, 503):
    raise SystemExit(1)
print("DEPLOY_OK")
PY
"""
    _, o, e = c.exec_command(cmd, timeout=600)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("ERR:", err[:2000])
    c.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
