#!/usr/bin/env python3
"""部署 AIDA+nanobot 融合：同步代码、安装 nanobot、停服、重启、验证。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"
ROOT = Path(__file__).resolve().parents[1]


def run_ssh(cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    c.close()
    return code, out, err


def sync() -> None:
    subprocess.check_call([
        sys.executable, str(ROOT / "scripts" / "deploy_ssh.py"), "sync", "231",
        str(ROOT), REMOTE,
        "--exclude", "node_modules", "--exclude", ".venv", "--exclude", "__pycache__",
        "--exclude", "agent/runtime", "--exclude", ".git",
        "--exclude", "frontend/node_modules", "--exclude", "nanobot-main/.venv",
    ])


def main() -> int:
    print("=== 1. sync ===")
    sync()

    remote_script = f"""
set -e
cd {REMOTE}

echo "=== stop old services ==="
pkill -f 'uvicorn agent.main' || true
pkill -f 'http.server 8080' || true
pkill -f 'nanobot serve' || true
pkill -f 'nanobot.cli.commands serve' || true
sleep 2

echo "=== remove nanobot builtin skills ==="
python3 scripts/remove_nanobot_builtin_skills.py

echo "=== install nanobot venv ==="
NB_PY=python3.11
if ! command -v python3.11 >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y python3.11 python3.11-venv 2>&1 | tail -3 || true
fi
if command -v python3.11 >/dev/null 2>&1; then
  NB_PY=python3.11
fi
cd nanobot-main
rm -rf .venv
$NB_PY -m venv .venv
.venv/bin/pip install -U pip -q
.venv/bin/pip install -e ".[api]" -q 2>&1 | tail -5
cd ..

echo "=== start fusion ==="
source agent/.venv/bin/activate
export AIDA_USE_NANOBOT_LLM=1
export AIDA_CHAT_VIA_NANOBOT=1
export NANOBOT_API_URL=http://127.0.0.1:8900
python3 scripts/start_aida_nanobot.py --no-stop 2>&1

sleep 3
echo "=== verify ==="
curl -s -o /dev/null -w 'nanobot:%{{http_code}} ' http://127.0.0.1:8900/health
curl -s -o /dev/null -w 'backend:%{{http_code}} ' http://127.0.0.1:7401/healthz
curl -s -o /dev/null -w 'frontend:%{{http_code}}' http://127.0.0.1:8080
echo
curl -s http://127.0.0.1:7401/healthz | python3 -c "import sys,json;d=json.load(sys.stdin);print('llm',d.get('llm',{{}}).get('model'),d.get('llm',{{}}).get('source'))"
"""
    print("=== 2. deploy remote ===")
    code, out, err = run_ssh(remote_script, timeout=600)
    print(out)
    if err:
        print(err, file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
