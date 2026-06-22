#!/usr/bin/env python3
"""231：停非容器服务 → 切容器编排模式 → 重启宿主机控制面 + 清理旧 claw 容器。"""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

CMD = rf"""
set -e
cd {REMOTE}
export DOCKER_API_VERSION=1.42

# 强制容器编排模式
touch agent/.env
grep -q '^AIDA_CLAW_ORCHESTRATION=' agent/.env || echo 'AIDA_CLAW_ORCHESTRATION=1' >> agent/.env
sed -i 's/^AIDA_CLAW_ORCHESTRATION=.*/AIDA_CLAW_ORCHESTRATION=1/' agent/.env
grep -q '^CLAW_IMAGE=' agent/.env || echo 'CLAW_IMAGE=aida/claw_liwen:dev' >> agent/.env
sed -i 's|^CLAW_IMAGE=.*|CLAW_IMAGE=aida/claw_liwen:dev|' agent/.env

echo "=== env ==="
grep -E '^(AIDA_CLAW_ORCHESTRATION|CLAW_IMAGE|MANAGER_PORT)=' agent/.env

echo "=== stop legacy host processes (7401/8900 etc) ==="
source agent/.venv/bin/activate
export AIDA_CLAW_ORCHESTRATION=1
export CLAW_IMAGE=aida/claw_liwen:dev
python3 scripts/start_aida_nanobot.py --no-stop 2>/dev/null || true
python3 - <<'PY'
import os, sys
from pathlib import Path
ROOT = Path({REMOTE!r})
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
import importlib.util
spec = importlib.util.spec_from_file_location("start", ROOT / "scripts" / "start_aida_nanobot.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
os.environ["AIDA_CLAW_ORCHESTRATION"] = "1"
mod.stop_old(remove_claw_containers=True)
print("[ok] stop_old done")
PY

echo "=== confirm :7401 :8900 free on host ==="
ss -lptn | grep -E ':7401|:8900' || echo "host agent/nanobot ports free"

echo "=== restart control-plane stack ==="
python3 scripts/start_aida_nanobot.py 2>&1

echo "=== post-check ==="
ss -lptn | grep -E ':8001|:8011|:8025|:8080' || true
docker images aida/claw_liwen --format 'image {{.Repository}}:{{.Tag}}'
docker ps --filter name=claw-u --format '{{.Names}} {{.Status}}' || true
curl -sf http://127.0.0.1:8001/healthz || curl -sf http://127.0.0.1:8081/healthz
echo
echo SWITCH_CONTAINER_STACK_DONE
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    sftp.put("scripts/start_aida_nanobot.py", f"{REMOTE}/scripts/start_aida_nanobot.py")
    sftp.close()
    _, stdout, stderr = client.exec_command(CMD, timeout=180)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[:3000])
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
