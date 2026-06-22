#!/usr/bin/env python3
"""231：启动宿主机 Manager :8001（claw 模式）并验收 session rehydrate。"""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

CMD = rf"""
set +e
cd {REMOTE}
export AIDA_CLAW_ORCHESTRATION=1
export MANAGER_PORT=8001
export DOCKER_API_VERSION=1.42
source agent/.venv/bin/activate

echo "=== stop only host :8001 manager ==="
for pid in $(ss -lptn | grep ':8001' | grep -oP 'pid=\\K[0-9]+' | sort -u); do
  cmd=$(ps -p "$pid" -o args= 2>/dev/null)
  echo "kill pid=$pid $cmd"
  case "$cmd" in
    *"/opt/aida_liwen"*|*aida_liwen*)
      kill "$pid" 2>/dev/null || true
      ;;
  esac
done
sleep 1

echo "=== start host manager :8001 ==="
nohup env AIDA_CLAW_ORCHESTRATION=1 MANAGER_PORT=8001 DOCKER_API_VERSION=1.42 \
  python3 -m uvicorn manager.main:app --host 0.0.0.0 --port 8001 --workers 1 \
  > /tmp/manager-8001.log 2>&1 &
sleep 5
curl -sf http://127.0.0.1:8001/healthz && echo " health_ok" || (echo health_fail; tail -20 /tmp/manager-8001.log; exit 1)

python3 -c "from manager.session_resolve import resolve_manager_session; print('import_ok')"

python3 - <<'PY'
import json, subprocess, time, urllib.request, urllib.error, os

os.chdir("{REMOTE}")
BASE = "http://127.0.0.1:8001"
USER, PASS = "liwen", "123456"

def post(path, body, token=None):
    data = json.dumps(body).encode()
    headers = {{"Content-Type": "application/json"}}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw
        return e.code, detail

code, login = post("/api/v1/auth/login", {{"username": USER, "password": PASS}})
print("login", code)
if code != 200:
    print("LOGIN_SKIP (use your account to manual test)", login)
    raise SystemExit(0)
token = login["access_token"]
sid = login["session_id"]
proj = "K1903"

# 模拟 Manager 重启：只杀 :8001 宿主机进程
subprocess.run(
    "ss -lptn | grep ':8001' | grep -oP 'pid=\\K[0-9]+' | xargs -r kill",
    shell=True,
    check=False,
)
time.sleep(2)
subprocess.Popen(
    ["python3", "-m", "uvicorn", "manager.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"],
    stdout=open("/tmp/manager-8001.log", "w"),
    stderr=subprocess.STDOUT,
    cwd="{REMOTE}",
    env={{**os.environ, "AIDA_CLAW_ORCHESTRATION": "1", "DOCKER_API_VERSION": "1.42"}},
)
time.sleep(5)

code2, enter = post(
    "/api/v1/session/enter-project",
    {{"session_id": sid, "project_id": proj, "project_code": proj}},
    token=token,
)
print("enter_after_restart", code2)
if code2 == 200:
    print("REHYDRATE_OK", enter.get("container_endpoint", "")[:80])
else:
    print("REHYDRATE_FAIL", enter)
    raise SystemExit(1)
PY

echo READY_FOR_MANUAL_TEST
echo "  1. 打开 http://{HOST}:8080/login 登录"
echo "  2. 进入 /landing 后刷新页面"
echo "  3. 点击进入项目 — 应成功进入（不再报会话无效）"
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
_, o, e = c.exec_command(CMD, timeout=300)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
code = o.channel.recv_exit_status()
print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
if err.strip():
    print("ERR:", err[:2000])
print("exit", code)
c.close()
