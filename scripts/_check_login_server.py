#!/usr/bin/env python3
"""Diagnose login Failed to fetch on server 231."""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"


def run(client: paramiko.SSHClient, cmd: str) -> str:
    _, o, e = client.exec_command(cmd, timeout=30)
    out = o.read().decode("utf-8", errors="replace").strip()
    err = e.read().decode("utf-8", errors="replace").strip()
    return out or err or "(empty)"


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    checks = [
        ("listening ports", "ss -tlnp | grep -E '8080|8081|8001|7401'"),
        ("8080 POST login", "curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8080/api/v1/auth/login -H 'Content-Type: application/json' -d '{}'"),
        ("8081 health", "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8081/health"),
        ("8001 health", "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/health"),
        ("8081 POST login", "curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8081/api/v1/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"x\",\"password\":\"y\"}'"),
        ("grep 8081 in dist", "grep -l '8081' /opt/aida_liwen/frontend/dist/assets/*.js 2>/dev/null | wc -l"),
        ("CORS preflight", "curl -s -o /dev/null -w '%{http_code}' -X OPTIONS 'http://127.0.0.1:8081/api/v1/auth/login' -H 'Origin: http://10.143.2.231:8080' -H 'Access-Control-Request-Method: POST'"),
        ("dist js grep 8001", "grep -l '8001' /opt/aida_liwen/frontend/dist/assets/*.js 2>/dev/null | wc -l"),
        ("dist auth/login ctx", "grep -F 'auth/login' /opt/aida_liwen/frontend/dist/assets/*.js | head -c 500"),
        ("agent .env manager", "grep -E 'DATA_CENTER|MANAGER|AGENT' /opt/aida_liwen/agent/.env 2>/dev/null | head -10"),
    ]
    for label, cmd in checks:
        print(f"=== {label} ===")
        print(run(c, cmd))
        print()
    c.close()


if __name__ == "__main__":
    main()
