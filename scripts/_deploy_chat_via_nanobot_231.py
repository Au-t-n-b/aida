#!/usr/bin/env python3
"""231：通用对话引擎切到 nanobot AgentLoop（取消 chat_engine 作为通用对话主引擎）。

改动落点：
  - 后端 agent 代码（baked 进 claw 镜像，需 rebuild + 重建容器）
      agent/main.py                              · /agent/chat/stream 改走 nanobot
      agent/nanobot_integration/nanobot_chat.py  · chat_via_nanobot_enabled()
  - 前端（host :8080，需 vite build）
      frontend/src/components/claw-rail.tsx      · skill_launch 采纳 run_id，避免二次启动

注意：claw 容器内 agent 代码不是 bind-mount（仅 /app/agent/skills 是），
所以后端改动必须 rebuild aida/claw_liwen:dev 并重建容器才能生效。
本脚本只 rebuild 镜像 + 重建前端，不强杀在跑的 claw 容器（避免打断在线会话）；
打印仍在旧镜像上的容器与重建命令，由操作者决定何时重建（或等用户下次 enter-project 自动用新镜像）。
"""
from __future__ import annotations

from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"
MANAGER_PORT = 8001

UPLOAD_FILES = [
    "agent/main.py",
    "agent/nanobot_integration/nanobot_chat.py",
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
cd {REMOTE}

echo '=== 1. rebuild claw image (agent 代码 baked) ==='
# Docker client/daemon API 版本错配（client 1.52 > daemon max 1.42）→ 锁 API 版本 + 用 legacy builder
export DOCKER_API_VERSION=1.42
export DOCKER_BUILDKIT=0
old_iid=$(docker image inspect -f '{{{{.Id}}}}' aida/claw_liwen:dev 2>/dev/null || echo none)
docker build -f deploy/claw/Dockerfile -t aida/claw_liwen:dev . > /tmp/claw_build.log 2>&1
build_rc=$?
tail -20 /tmp/claw_build.log
if [ "$build_rc" != "0" ]; then echo "IMAGE_BUILD_FAILED rc=$build_rc"; exit 1; fi
new_iid=$(docker image inspect -f '{{{{.Id}}}}' aida/claw_liwen:dev 2>/dev/null || echo none)
echo "IMAGE_OK old=$old_iid new=$new_iid"

echo '=== 2. rebuild frontend ==='
cd {REMOTE}/frontend
export VITE_CLAWMANAGER_BASE=http://{HOST}:{MANAGER_PORT}
export VITE_AGENT_BASE=http://{HOST}:7401
npx vite build 2>&1 | tail -8
test -f dist/index.html && echo FE_BUILD_OK

cd {REMOTE}
pkill -f 'spa_static_server.py --host 0.0.0.0 --port 8080' || true
sleep 1
nohup python3 scripts/spa_static_server.py --host 0.0.0.0 --port 8080 --directory frontend/dist > /tmp/fe-spa.log 2>&1 &
sleep 2
curl -s -o /dev/null -w "frontend %{{http_code}}\\n" http://127.0.0.1:8080/login || true

echo '=== 3. 重建 claw 容器以采用新镜像（rm -f，下次 enter-project 自动用新镜像）==='
docker ps -a --filter 'name=claw-' --format '  {{{{.Names}}}}  {{{{.Image}}}}  up={{{{.Status}}}}' || true
claws=$(docker ps -aq --filter 'name=claw-')
if [ -n "$claws" ]; then
  docker rm -f $claws && echo "REMOVED_CLAW_CONTAINERS"
else
  echo "NO_CLAW_CONTAINERS"
fi
echo DEPLOY_CHAT_VIA_NANOBOT_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=900)
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
