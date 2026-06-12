#!/usr/bin/env python3
"""Verify nanobot chat proxy fix on server."""
import json
import os
import sys
import urllib.request

# simulate enterprise proxy in env (should NOT affect local nanobot)
os.environ["HTTP_PROXY"] = "http://10.143.2.250:8088/"
os.environ["HTTPS_PROXY"] = "http://10.143.2.250:8088/"

ROOT = "/opt/aida_liwen"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

print("=== 1. direct nanobot health ===")
try:
    with urllib.request.urlopen("http://127.0.0.1:8900/health", timeout=10) as r:
        print("health", r.status, r.read()[:80])
except Exception as e:
    print("health FAIL", e)

print("=== 2. nanobot_chat module (with proxy env) ===")
import asyncio
from agent.nanobot_integration.nanobot_chat import run_nanobot_chat_async

async def test_chat():
    got_token = False
    async for ev in run_nanobot_chat_async("say hi", conv_id="verify-fix"):
        t = ev.get("type")
        if t == "token":
            got_token = True
            print("token", (ev.get("text") or "")[:80])
        elif t == "error":
            print("ERROR", ev.get("message", "")[:300])
            return 1
        elif t == "done":
            print("done ok, got_token=", got_token)
            return 0 if got_token else 1
    return 1

code = asyncio.run(asyncio.wait_for(test_chat(), timeout=60))
print("chat module exit", code)

print("=== 3. AIDA /agent/chat/stream ===")
req = urllib.request.Request(
    "http://127.0.0.1:7401/agent/chat/stream",
    data=json.dumps({"message": "hi", "conv_id": "verify-stream"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=90) as resp:
    body = resp.read(1500).decode(errors="replace")
print(body[:1200])
if "502" in body or "Cntlm" in body:
    sys.exit(1)
if "error" in body and '"type": "error"' in body:
    sys.exit(1)
print("ALL OK")
