"""Test LLM via different proxy strategies."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

API_KEY = os.environ.get("ZHIPU_API_KEY", "")
if not API_KEY:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    API_KEY = os.environ["ZHIPU_API_KEY"]

BASE = os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4")
MODEL = os.environ.get("ZHIPU_MODEL", "glm-4-flash")
URL = f"{BASE.rstrip('/')}/chat/completions"
PAYLOAD = {"model": MODEL, "messages": [{"role": "user", "content": "say hi"}], "max_tokens": 10}

strategies = [
    ("direct trust_env=False", {"trust_env": False}),
    ("127.0.0.1:7890", {"proxy": "http://127.0.0.1:7890", "trust_env": False}),
    ("127.0.0.1:7890 verify=False", {"proxy": "http://127.0.0.1:7890", "verify": False, "trust_env": False}),
    ("system proxy verify=False", {"verify": False, "trust_env": True}),
]

for name, kwargs in strategies:
    try:
        with httpx.Client(timeout=15.0, **kwargs) as c:
            r = c.post(URL, json=PAYLOAD, headers={"Authorization": f"Bearer {API_KEY}"})
            print(f"{name}: {r.status_code} {r.text[:80]}")
    except Exception as e:
        print(f"{name}: FAIL {type(e).__name__}: {e}")
