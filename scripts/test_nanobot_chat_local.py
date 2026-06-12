#!/usr/bin/env python3
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AIDA_CHAT_VIA_NANOBOT", "1")
os.environ.setdefault("NANOBOT_API_URL", "http://127.0.0.1:8900")
# 模拟服务器上配置了企业代理的环境
os.environ["HTTP_PROXY"] = "http://10.143.2.250:8088/"
os.environ["HTTPS_PROXY"] = "http://10.143.2.250:8088/"


async def main() -> int:
    from agent.nanobot_integration.nanobot_chat import run_nanobot_chat_async

    async for ev in run_nanobot_chat_async("say hi in 2 words", conv_id="proxy-fix-test"):
        print(json.dumps(ev, ensure_ascii=False))
        if ev.get("type") in ("done", "error"):
            return 0 if ev.get("type") == "done" else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
