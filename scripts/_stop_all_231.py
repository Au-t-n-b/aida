#!/usr/bin/env python3
"""231：停止 AIDA 相关服务（宿主机 Claw 控制面 + Claw 容器 + docker compose）。

红线：勿停止数据中心（:8000 API、aida-fs :8765、Postgres）；日常重启只动 /opt/aida_liwen 栈。
"""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

CMD = rf"""
set +e
cd {REMOTE}
export AIDA_CLAW_ORCHESTRATION=1
source agent/.venv/bin/activate 2>/dev/null || true

echo "=== 1) stop_old (host processes + claw containers) ==="
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
mod.stop_old(remove_claw_containers=True)
print("stop_old done")
PY

echo "=== 2) remove all aida-claw / claw-u containers ==="
export DOCKER_API_VERSION=1.42
docker ps -aq --filter name=aida-claw | xargs -r docker rm -f
docker ps -aq --filter name=claw-u | xargs -r docker rm -f
docker ps -aq --filter name=claw-smoke | xargs -r docker rm -f

echo "=== 3) systemd aida-* (exclude datacenter: aida-fs) ==="
for svc in aida-master-agent aida-master-frontend aida-manager aida-frontend; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    echo "stopping $svc"
    systemctl stop "$svc" 2>/dev/null || true
  fi
done
# 兜底：停 aida 前缀 unit，但跳过数据中心 aida-fs
systemctl list-units --type=service --state=running 2>/dev/null | grep -oP 'aida[^ ]*' | sort -u | while read -r svc; do
  if [ "$svc" = "aida-fs.service" ] || [ "$svc" = "aida-fs" ]; then
    echo "skip datacenter unit $svc"
    continue
  fi
  echo "stopping unit $svc"
  systemctl stop "$svc" 2>/dev/null || true
done

echo "=== 4) docker compose stacks (if any) ==="
for d in {REMOTE} /home/aida /opt/aida; do
  if [ -f "$d/docker-compose.yml" ]; then
    echo "compose down in $d"
    (cd "$d" && docker compose down 2>/dev/null || docker-compose down 2>/dev/null) || true
  fi
done

echo "=== 5) force kill remaining listeners (exclude datacenter :8000 :8765) ==="
for port in 8001 8081 8011 8025 8900 7401 8080 5173; do
  pids=$(ss -lptn "sport = :$port" 2>/dev/null | grep -oP 'pid=\\K[0-9]+' | sort -u)
  if [ -n "$pids" ]; then
    echo "kill port $port pids: $pids"
    echo "$pids" | xargs -r kill -9 2>/dev/null
  fi
done
sleep 2

echo "=== 6) status ==="
echo "--- listening (aida ports) ---"
ss -lptn | grep -E ':8001|:8081|:8011|:8025|:8900|:7401|:8080' || echo "(claw stack ports clear)"
echo "--- datacenter (should stay up) ---"
ss -lptn | grep -E ':8000|:8765' || echo "(datacenter ports down)"
echo "--- claw containers ---"
docker ps -a --filter name=aida-claw --format '{{{{.Names}}}} {{{{.Status}}}}' 2>/dev/null || true
docker ps -a --filter name=claw-u --format '{{{{.Names}}}} {{{{.Status}}}}' 2>/dev/null || true
echo "--- aida docker compose ---"
docker ps -a --filter name=aida- --format '{{{{.Names}}}} {{{{.Status}}}}' 2>/dev/null || true
echo "--- aida processes ---"
ps aux | grep -E 'uvicorn|nanobot|mailgw|spa_static|start_aida' | grep -v grep || echo "(none)"
echo STOP_ALL_DONE
"""

def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    _, o, e = c.exec_command(CMD, timeout=180)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))
    if err.strip():
        print("ERR:", err[:2000])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
