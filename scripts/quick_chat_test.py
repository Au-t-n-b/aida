#!/usr/bin/env python3
"""Quick server-side nanobot chat test (bypass proxy for localhost)."""
import json
import os
import sys
import urllib.request

os.environ["HTTP_PROXY"] = "http://10.143.2.250:8088/"
os.environ["HTTPS_PROXY"] = "http://10.143.2.250:8088/"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

ROOT = "/opt/aida_liwen"
sys.path.insert(0, ROOT)
os.chdir(ROOT)


def health():
  opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
  req = urllib.request.Request("http://127.0.0.1:8900/health")
  with opener.open(req, timeout=10) as r:
    print("nanobot health:", r.status, r.read()[:120])


def direct_chat():
  payload = json.dumps({
    "messages": [{"role": "user", "content": "say hi in 3 words"}],
    "stream": True,
    "session_id": "quick-test",
  }).encode()
  opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
  req = urllib.request.Request(
    "http://127.0.0.1:8900/v1/chat/completions",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
  )
  with opener.open(req, timeout=120) as resp:
    chunks = []
    while True:
      line = resp.readline()
      if not line:
        break
      chunks.append(line.decode(errors="replace"))
      if len(chunks) > 20:
        break
    body = "".join(chunks)
    print("direct chat sample:", body[:600])
    if "502" in body or "Cntlm" in body:
      return 1
    if "data:" in body:
      return 0
    return 1


def module_chat():
  import asyncio
  from agent.nanobot_integration.nanobot_chat import run_nanobot_chat_async

  async def run():
    async for ev in run_nanobot_chat_async("say hi in 3 words", conv_id="quick-mod"):
      print("event:", ev)
      if ev.get("type") == "error":
        return 1
      if ev.get("type") == "done":
        return 0
    return 1

  return asyncio.run(asyncio.wait_for(run(), timeout=120))


if __name__ == "__main__":
  health()
  c1 = direct_chat()
  print("direct exit", c1)
  c2 = module_chat()
  print("module exit", c2)
  raise SystemExit(0 if c1 == 0 and c2 == 0 else 1)
