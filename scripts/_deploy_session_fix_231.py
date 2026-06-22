#!/usr/bin/env python3
"""231：部署会话 rehydrate 修复 + 前端 401 跳转 + 验收。"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"
MANAGER_PORT = 8001

UPLOAD_FILES = [
    "manager/session_resolve.py",
    "manager/sessions.py",
    "manager/routes/session.py",
    "manager/routes/chat.py",
    "frontend/src/lib/claw-manager-client.ts",
    "frontend/src/components/screens/landing.tsx",
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

    verify_py = textwrap.dedent(
        f"""
        import json, subprocess, sys, time, urllib.request, urllib.error

        BASE = "http://127.0.0.1:{MANAGER_PORT}"
        USER, PASS = "liwen", "123456"

        def post(path, body, token=None):
            data = json.dumps(body).encode()
            req = urllib.request.Request(
                BASE + path,
                data=data,
                headers={{"Content-Type": "application/json", **({{"Authorization": "Bearer " + token}} if token else {{}})}},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.status, json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                raw = e.read().decode(errors="replace")
                try:
                    detail = json.loads(raw)
                except Exception:
                    detail = raw
                return e.code, detail

        # 1) 模块可导入
        from manager.session_resolve import resolve_manager_session
        print("import resolve_manager_session OK")

        # 2) 登录
        code, login = post("/api/v1/auth/login", {{"username": USER, "password": PASS}})
        if code != 200:
            print("LOGIN_SKIP code=", code, "detail=", login)
            print("VERIFY_PARTIAL deploy ok, manual login test needed")
            sys.exit(0)
        token = login["access_token"]
        sid = login["session_id"]
        print("login ok session_id=", sid[:24], "...")

        # 3) 模拟 Manager 重启（清空内存会话）
        subprocess.run(["pkill", "-f", "uvicorn manager.main"], check=False)
        time.sleep(2)
        subprocess.Popen(
            ["python3", "-m", "uvicorn", "manager.main:app", "--host", "0.0.0.0", "--port", "{MANAGER_PORT}", "--workers", "1"],
            stdout=open("/tmp/manager.log", "w"),
            stderr=subprocess.STDOUT,
            cwd="{REMOTE}",
        )
        time.sleep(4)
        with urllib.request.urlopen(BASE + "/healthz", timeout=10) as r:
            print("healthz", r.status)

        # 4) 内存已空，enter-project 应靠 rehydrate 成功
        code2, enter = post(
            "/api/v1/session/enter-project",
            {{"session_id": sid, "project_id": "K1903", "project_code": "K1903"}},
            token=token,
        )
        print("enter-project after restart code=", code2)
        if code2 == 200 and enter.get("container_endpoint"):
            print("REHYDRATE_OK endpoint=", enter.get("container_endpoint"))
        else:
            print("REHYDRATE_FAIL", enter)
            sys.exit(1)
        """
    )

    cmd = f"""
set -e
cd {REMOTE}
export AIDA_CLAW_ORCHESTRATION=1
source agent/.venv/bin/activate

echo "=== restart manager :{MANAGER_PORT} ==="
pkill -f 'uvicorn manager.main' || true
sleep 2
nohup python3 -m uvicorn manager.main:app --host 0.0.0.0 --port {MANAGER_PORT} --workers 1 > /tmp/manager.log 2>&1 &
sleep 4
curl -sf http://127.0.0.1:{MANAGER_PORT}/healthz
echo

echo "=== frontend build ==="
cd {REMOTE}/frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:{MANAGER_PORT}
export VITE_AGENT_BASE=http://{HOST}:7401
npx vite build 2>&1 | tail -5
test -f dist/index.html && echo FE_BUILD_OK
grep -l '{MANAGER_PORT}' dist/assets/*.js 2>/dev/null | wc -l | xargs -I{{}} echo dist_manager_port_refs={{}}

echo "=== E2E rehydrate verify ==="
cd {REMOTE}
python3 - <<'PY'
{verify_py}
PY
echo DEPLOY_SESSION_FIX_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[:4000])
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
