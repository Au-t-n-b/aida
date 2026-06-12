#!/usr/bin/env python3
"""Restart AIDA backend + frontend on server 231."""
import time
import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
ROOT = "/opt/aida_liwen"


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)

    def run(cmd: str, timeout: int = 30) -> str:
        _, o, _ = c.exec_command(cmd, timeout=timeout)
        return o.read().decode("utf-8", errors="replace").strip()

    run("pkill -f 'uvicorn agent.main:app' || true")
    run("pkill -f 'http.server 8080' || true")
    time.sleep(1)

    c.exec_command(
        f"cd {ROOT} && nohup agent/.venv/bin/uvicorn agent.main:app "
        "--host 0.0.0.0 --port 7401 --workers 1 "
        "> /var/log/aida-liwen-agent.log 2>&1 </dev/null &"
    )
    time.sleep(4)

    c.exec_command(
        f"cd {ROOT}/frontend/dist && nohup python3 -m http.server 8080 --bind 0.0.0.0 "
        "> /var/log/aida-liwen-frontend.log 2>&1 </dev/null &"
    )
    time.sleep(2)

    ports = run("ss -tlnp | grep -E '7401|8080'")
    backend = run("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:7401/healthz")
    health = run("curl -s http://127.0.0.1:7401/healthz")
    frontend = run("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080")

    print("PORTS:\n", ports)
    print(f"backend healthz: HTTP {backend}")
    print(f"healthz body: {health[:200]}")
    print(f"frontend: HTTP {frontend}")
    c.close()
    return 0 if backend == "200" and frontend == "200" else 1


if __name__ == "__main__":
    raise SystemExit(main())
