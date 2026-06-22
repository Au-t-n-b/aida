#!/usr/bin/env python3
"""Restart AIDA stack on server 231 and verify health."""
from __future__ import annotations

import sys
import time

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out + err


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    restart_script = f"""
cd {REMOTE}
source agent/.venv/bin/activate
export AIDA_USE_NANOBOT_LLM=1 AIDA_CHAT_VIA_NANOBOT=1 NANOBOT_API_URL=http://127.0.0.1:8900
export MANAGER_PORT=8081
python3 - <<'PY'
import os, sys, time
from pathlib import Path

ROOT = Path({REMOTE!r})
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import importlib.util
spec = importlib.util.spec_from_file_location("start_aida_nanobot", ROOT / "scripts" / "start_aida_nanobot.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

mod.stop_old()
mod.bootstrap()
procs = []
nb = mod.start_nanobot_serve()
if nb:
    procs.append(nb)
    time.sleep(5)
procs.append(mod.start_aida())
time.sleep(8)
procs.append(mod.start_manager())
time.sleep(3)
ba = mod.start_backend_app()
if ba:
    procs.append(ba)
    time.sleep(5)
mg = mod.start_mailgw()
mailgw_started = mg is not None
if mg:
    procs.append(mg)
    time.sleep(2)
fe = mod.start_frontend()
if fe:
    procs.append(fe)
time.sleep(3)
ok = mod.verify(mailgw_started=mailgw_started)
print("[ok] running PIDs:", [p.pid for p in procs])
print("[verify]", "PASS" if ok else "PARTIAL")
PY
"""
    print("=== restart ===")
    code, out = run(client, restart_script)
    print(out.encode("ascii", errors="backslashreplace").decode("ascii"))

    time.sleep(15)
    verify_script = """
curl -s -o /dev/null -w '7401:%{http_code}\\n' http://127.0.0.1:7401/healthz
curl -s -o /dev/null -w '8081:%{http_code}\\n' http://127.0.0.1:8081/health
curl -s -o /dev/null -w '8900:%{http_code}\\n' http://127.0.0.1:8900/health
curl -s -o /dev/null -w '8011:%{http_code}\\n' http://127.0.0.1:8011/health
curl -s -o /dev/null -w '8080:%{http_code}\\n' http://127.0.0.1:8080/
echo '---ports---'
ss -tlnp | egrep '7401|8080|8081|8900|8011|8025' || true
echo '---procs---'
ps aux | egrep 'uvicorn|nanobot|mailgw|spa_static' | grep -v grep || true
"""
    print("=== verify (after 10s) ===")
    _, verify_out = run(client, verify_script, timeout=60)
    print(verify_out)

    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
