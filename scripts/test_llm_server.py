#!/usr/bin/env python3
import os
import sys

ROOT = "/opt/aida_liwen"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from agent.llm import chat_once, healthcheck

print("healthcheck:", healthcheck())
try:
    r = chat_once([{"role": "user", "content": "say hi in 3 words"}])
    print("chat_once:", (r or "")[:200])
except Exception as e:
    print("chat_once ERROR:", type(e).__name__, e)
    raise
