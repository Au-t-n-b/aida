#!/usr/bin/env python3
"""Verify P4 hot-reload endpoint on server 231."""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"

SCRIPT = r"""
echo '=== /agent/skills (count after restart) ==='
curl -s http://127.0.0.1:7401/agent/skills | python3 -c "import sys,json; d=json.load(sys.stdin); print('skills:', len(d['skills']), sorted(s['name'] for s in d['skills']))"
echo
echo '=== POST /admin/skills/reload (loopback, full re-discover) ==='
curl -s -X POST http://127.0.0.1:7401/admin/skills/reload -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok:', d.get('ok'), '| reloaded:', sorted(d.get('reloaded',[])), '| added:', d.get('added'), '| removed:', d.get('removed'), '| errors:', d.get('errors'))"
echo
echo '=== POST /admin/skills/reload names=[zhgk] ==='
curl -s -X POST http://127.0.0.1:7401/admin/skills/reload -H 'Content-Type: application/json' -d '{"names":["zhgk"]}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok:', d.get('ok'), '| reloaded:', d.get('reloaded'), '| errors:', d.get('errors'))"
echo
echo '=== auth: loopback -> expect 200 ==='
curl -s -o /dev/null -w 'loopback status=%{http_code}\n' -X POST http://127.0.0.1:7401/admin/skills/reload -H 'Content-Type: application/json' -d '{}'
echo '=== auth: non-loopback (public IP, no token) -> expect 403 ==='
curl -s -o /dev/null -w 'non-loopback status=%{http_code}\n' -X POST http://10.143.2.231:7401/admin/skills/reload -H 'Content-Type: application/json' -d '{}'
echo
echo '=== /agent/skills (count after reloads · sanity) ==='
curl -s http://127.0.0.1:7401/agent/skills | python3 -c "import sys,json; d=json.load(sys.stdin); print('skills:', len(d['skills']))"
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    _, out, err = c.exec_command(SCRIPT, timeout=120)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("ERR:", e)
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
