#!/usr/bin/env python3
"""服务器侧验证 P4.1：服务健康 + reload 端点 + 闸代码就位 + workspace_env 接线。"""
from __future__ import annotations

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
REMOTE = "/opt/aida_liwen"

PYSNIP = (
    "import json; "
    "import agent.main as M; "
    "from agent.skills import registry; "
    "import os; "
    "os.environ['ZHGK_ROOT']='/tmp/_ws_probe_zhgk'; "
    "registry.reload(['zhgk']); "
    "sk=registry.get('zhgk'); "
    "rt=sk.metadata.runtime or {}; "
    "print('GATE_PRESENT=', hasattr(M,'_skill_run_gate')); "
    "print('WS_ENV=', rt.get('workspace_env')); "
    "print('WORK_ROOT=', sk.work_root); "
    "print('VER=', sk.metadata.version, 'ENABLED=', sk.metadata.enabled)"
)

CMD = f"""
echo '=== /agent/skills (structure) ==='
curl -s http://127.0.0.1:7401/agent/skills | python3 -c "import sys,json; d=json.load(sys.stdin); items=(d.get('skills') if isinstance(d,dict) else d) or (list(d.keys()) if isinstance(d,dict) else []); nm=lambda s: s.get('name') if isinstance(s,dict) else s; print('type=', type(d).__name__, 'count=', len(items), [nm(s) for s in items])"
echo '=== POST /admin/skills/reload (localhost) ==='
curl -s -X POST http://127.0.0.1:7401/admin/skills/reload -H 'Content-Type: application/json' -d '{{}}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok=', d.get('ok'), 'reloaded=', d.get('reloaded'), 'added=', d.get('added'), 'removed=', d.get('removed'))"
echo '=== code-level: gate + workspace_env wiring ==='
cd {REMOTE}
source agent/.venv/bin/activate
export PYTHONPATH={REMOTE}
python3 -c "{PYSNIP}"
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    _, stdout, stderr = client.exec_command(CMD, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("--- stderr ---")
        print(err)
    client.close()
    return stdout.channel.recv_exit_status()


if __name__ == "__main__":
    raise SystemExit(main())
