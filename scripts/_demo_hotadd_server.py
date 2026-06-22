#!/usr/bin/env python3
"""Demo P4 end-to-end hot-ADD / hot-REMOVE on server 231 (no restart). Self-cleaning."""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"

SCRIPT = r"""
D=/opt/aida_liwen/agent/skills/demohot
mkdir -p $D
: > $D/__init__.py
cat > $D/skill.py <<'EOF'
from ..base import BaseSkill
class DemoHotSkill(BaseSkill):
    name = "demohot"
    description = "P4 hot-add demo (temporary)"
    steps = []
def get_demohot_skill():
    import tempfile
    from pathlib import Path
    return DemoHotSkill(work_root=Path(tempfile.gettempdir()) / "demohot_ws", llm_factory=None)
EOF

echo '=== 1) before reload (dir exists but not loaded) ==='
curl -s http://127.0.0.1:7401/agent/skills | python3 -c "import sys,json;d=json.load(sys.stdin);print('count=',len(d['skills']),'has_demohot=','demohot' in [s['name'] for s in d['skills']])"

echo '=== 2) reload(full) -> ADD demohot (no restart) ==='
curl -s -X POST http://127.0.0.1:7401/admin/skills/reload -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('added=',d.get('added'),'ok=',d.get('ok'),'errors=',d.get('errors'))"

echo '=== 3) after add: demohot is live ==='
curl -s http://127.0.0.1:7401/agent/skills | python3 -c "import sys,json;d=json.load(sys.stdin);print('count=',len(d['skills']),'has_demohot=','demohot' in [s['name'] for s in d['skills']])"

echo '=== 4) remove dir + reload -> REMOVE demohot ==='
rm -rf $D
curl -s -X POST http://127.0.0.1:7401/admin/skills/reload -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('removed=',d.get('removed'),'ok=',d.get('ok'))"

echo '=== 5) after remove: back to baseline ==='
curl -s http://127.0.0.1:7401/agent/skills | python3 -c "import sys,json;d=json.load(sys.stdin);print('count=',len(d['skills']),'has_demohot=','demohot' in [s['name'] for s in d['skills']])"

rm -rf $D
echo 'CLEANUP_DONE'
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
