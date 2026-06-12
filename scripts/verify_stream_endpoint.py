#!/usr/bin/env python3
"""Verify AIDA /agent/chat/stream via nanobot (server-side)."""
import json
import os
import sys
import urllib.request

os.environ["HTTP_PROXY"] = "http://10.143.2.250:8088/"
os.environ["HTTPS_PROXY"] = "http://10.143.2.250:8088/"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
req = urllib.request.Request(
    "http://127.0.0.1:7401/agent/chat/stream",
    data=json.dumps({"message": "say hi in 3 words", "conv_id": "verify-e2e"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with opener.open(req, timeout=90) as resp:
    body = resp.read(3000).decode(errors="replace")

print(body[:1500].encode("ascii", "backslashreplace").decode("ascii"))
if "502" in body or "Cntlm" in body:
    sys.exit(1)
if '"type": "error"' in body:
    sys.exit(1)
if '"type": "token"' not in body:
    sys.exit(1)
print("STREAM_OK")
