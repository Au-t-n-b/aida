"""
自由聊天 → nanobot OpenAI API 代理。

将 nanobot /v1/chat/completions 的 SSE 流转换为 AIDA chat_engine 事件格式
（token / done / error），供 main.py /agent/chat/stream 消费。
"""
from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import httpx

NANOBOT_API_URL = os.environ.get("NANOBOT_API_URL", "http://127.0.0.1:8900").rstrip("/")
DEFAULT_SESSION = "aida-chat-default"
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _is_local_service(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in _LOCAL_HOSTS


def _http_client_kwargs(url: str) -> dict[str, Any]:
    """本机 nanobot 必须直连，不能走企业 HTTP_PROXY（否则会 502 Cntlm）。"""
    local = _is_local_service(url)
    proxy = None if local else (
        os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
    )
    verify = os.environ.get("ZHIPU_SSL_VERIFY", "").strip().lower() not in ("0", "false", "no")
    if proxy:
        verify = False
    return {
        "proxy": proxy,
        "verify": verify,
        "trust_env": not local,
        "timeout": httpx.Timeout(300.0, connect=30.0),
    }


def _enabled() -> bool:
    v = os.environ.get("AIDA_CHAT_VIA_NANOBOT", "1").strip().lower()
    return v not in ("0", "false", "no")


async def run_nanobot_chat_async(
    user_text: str,
    *,
    conv_id: str | None = None,
    system: str | None = None,  # noqa: ARG001 — nanobot 用 workspace 模板，此处忽略
) -> AsyncIterator[dict[str, Any]]:
    """流式 yield AIDA 风格事件。"""
    if not _enabled():
        raise RuntimeError("AIDA_CHAT_VIA_NANOBOT 未启用")

    session_id = (conv_id or "").strip() or DEFAULT_SESSION
    # nanobot API 仅支持单条 user message；上下文由 session_key 维护
    payload = {
        "messages": [{"role": "user", "content": user_text}],
        "stream": True,
        "session_id": session_id,
    }

    url = f"{NANOBOT_API_URL}/v1/chat/completions"

    try:
        async with httpx.AsyncClient(**_http_client_kwargs(url)) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    yield {
                        "type": "error",
                        "message": f"nanobot API {resp.status_code}: {body[:300].decode(errors='replace')}",
                    }
                    return

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        yield {"type": "done"}
                        return
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield {"type": "token", "text": content}
                    if choices[0].get("finish_reason") == "stop":
                        yield {"type": "done"}
                        return
        yield {"type": "done"}
    except httpx.ConnectError as e:
        yield {
            "type": "error",
            "message": f"无法连接 nanobot API ({url})，请确认 nanobot serve 已启动: {e}",
        }
    except Exception as e:
        yield {"type": "error", "message": f"{type(e).__name__}: {e}"}
