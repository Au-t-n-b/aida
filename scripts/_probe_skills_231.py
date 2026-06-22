#!/usr/bin/env python3
import paramiko
CMD = r"""
cd /opt/aida_liwen && source agent/.venv/bin/activate && python3 <<'PY'
from agent.skills._loader import load_skill_md, default_skill_md_path
p = default_skill_md_path("software_deployment")
m = load_skill_md(p)
print("path", p)
print("ui", m.ui)
print("enabled", m.enabled)
PY
"""
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.231", username="root", password="Xvz!DI0g", timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(CMD, timeout=60)
print(o.read().decode("utf-8", errors="replace"))
c.close()
