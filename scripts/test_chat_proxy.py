#!/usr/bin/env python3
"""Quick test: AIDA chat/stream proxies to nanobot."""
import json
import urllib.request

url = "http://127.0.0.1:7401/agent/chat/stream"
req = urllib.request.Request(
    url,
    data=json.dumps({"message": "say hi in 3 words", "conv_id": "test-proxy"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=120) as resp:
    data = resp.read(2000).decode(errors="replace")
print(data[:1500])
