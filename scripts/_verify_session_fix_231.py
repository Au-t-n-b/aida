#!/usr/bin/env python3
import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
CMD = r"""
cd /opt/aida_liwen
source agent/.venv/bin/activate
export AIDA_CLAW_ORCHESTRATION=1 DOCKER_API_VERSION=1.42

python3 - <<'PY'
import json, subprocess, time, urllib.request, urllib.error, os

BASE = "http://127.0.0.1:8001"

def post(path, body, token=None):
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw
        return e.code, detail

code, login = post("/api/v1/auth/login", {"username": "liwen", "password": "123456"})
token, sid = login["access_token"], login["session_id"]
print("login", code)

# restart manager only on 8001
subprocess.run("ss -lptn | grep ':8001' | grep -oP 'pid=\\K[0-9]+' | xargs -r kill", shell=True)
time.sleep(2)
subprocess.Popen(
    ["python3", "-m", "uvicorn", "manager.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"],
    stdout=open("/tmp/manager-8001.log", "a"),
    stderr=subprocess.STDOUT,
    cwd="/opt/aida_liwen",
    env={**os.environ, "AIDA_CLAW_ORCHESTRATION": "1", "DOCKER_API_VERSION": "1.42"},
)
time.sleep(4)

# 无 auth 应 401
c0, _ = post("/api/v1/session/enter-project", {"session_id": sid, "project_id": "K1903"})
print("no_auth", c0, "expect 401")

# 有 token + 重启后内存空 → 不应再 401
c1, r1 = post(
    "/api/v1/session/enter-project",
    {"session_id": sid, "project_id": "K1903", "project_code": "K1903"},
    token=token,
)
print("after_restart", c1, type(r1).__name__)
if c1 == 401:
    print("FAIL still 401", r1)
    raise SystemExit(1)
if c1 == 200:
    print("OK enter-project", r1.get("container_endpoint", "")[:60])
else:
    print("non-401 (claw/infra):", str(r1)[:200])
print("SESSION_FIX_VERIFIED no_401_after_rehydrate")
PY

ss -lptn | grep ':8001' || echo '8001 not listening'
curl -sf http://127.0.0.1:8001/healthz | head -c 120; echo
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(CMD, timeout=300)
print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
c.close()
