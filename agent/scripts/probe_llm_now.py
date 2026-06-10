"""Probe LLM connectivity with detailed error."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

print("HTTP_PROXY =", repr(os.environ.get("HTTP_PROXY")))
print("HTTPS_PROXY =", repr(os.environ.get("HTTPS_PROXY")))

from llm import get_llm, _proxy_url, _llm_instance

print("proxy_url() =", repr(_proxy_url()))

try:
    llm = get_llm()
    print("model =", llm.model_name)
    resp = llm.invoke([("human", "say hi in one word")])
    print("PASS:", resp.content[:100])
except Exception as e:
    print("FAIL:", type(e).__name__, e)
    import traceback
    traceback.print_exc()
    sys.exit(1)
