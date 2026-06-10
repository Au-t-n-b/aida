"""
AIDA Agent · LLM wrapper

智谱 BigModel API（OpenAI 兼容协议）单一接入点。

用法：
    from .llm import get_llm, chat_once
    text = chat_once("帮我总结一下这个工勘前置检查结果...")

配置从 .env 读：
    ZHIPU_API_KEY     - API 密钥（必须）
    ZHIPU_BASE_URL    - 默认 https://open.bigmodel.cn/api/coding/paas/v4
    ZHIPU_MODEL       - 默认 glm-4.5
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# ── 加载 .env（同目录） ──
_ENV_PATH = Path(__file__).parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=False)


def _cfg() -> tuple[str, str, str]:
    api_key = os.environ.get("ZHIPU_API_KEY", "").strip()
    base_url = os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4").strip()
    model = os.environ.get("ZHIPU_MODEL", "glm-4.5").strip()
    if not api_key:
        raise RuntimeError(
            "ZHIPU_API_KEY 未配置。请在 agent/.env 里设置（已加 .gitignore 不会进 git）"
        )
    return api_key, base_url, model


# ── Langfuse 可观测（可选；未配置时退化为无 trace 模式）──

_langfuse_initialized = False
_langfuse_callbacks: list = []


def _init_langfuse_once() -> list:
    """
    初始化 Langfuse 客户端（单例）。
    未配置 LANGFUSE_PUBLIC_KEY/SECRET_KEY → 返回空 callbacks 列表，不阻断启动。
    """
    global _langfuse_initialized, _langfuse_callbacks
    if _langfuse_initialized:
        return _langfuse_callbacks
    _langfuse_initialized = True

    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()
    if not (pk and sk):
        return _langfuse_callbacks  # 空列表

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        Langfuse(public_key=pk, secret_key=sk, host=host)
        _langfuse_callbacks = [CallbackHandler()]
    except Exception as e:
        import sys
        sys.stderr.write(f"[langfuse] init failed: {e}\n")

    return _langfuse_callbacks


def get_langfuse_callbacks() -> list:
    """对外暴露 Langfuse callbacks（用于 LangGraph 顶层 invoke 传入）。"""
    return _init_langfuse_once()


_llm_instance: ChatOpenAI | None = None


def _proxy_url() -> str | None:
    """内网服务器经 HTTP_PROXY/HTTPS_PROXY 访问智谱 API。"""
    return (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or None
    )


def _ssl_verify() -> bool:
    """企业代理 MITM 时需关闭校验；可设 ZHIPU_SSL_VERIFY=true 强制开启。"""
    v = os.environ.get("ZHIPU_SSL_VERIFY", "").strip().lower()
    if v in ("1", "true", "yes"):
        return True
    if v in ("0", "false", "no"):
        return False
    return _proxy_url() is None


def _http_clients() -> tuple[Any | None, Any | None]:
    """显式 httpx 客户端：内网/系统代理 MITM 时需 verify 控制；无代理但 verify=False 时也需自定义。"""
    proxy = _proxy_url()
    verify = _ssl_verify()
    if not proxy and verify:
        return None, None
    import httpx

    return (
        httpx.Client(proxy=proxy, verify=verify, timeout=60.0),
        httpx.AsyncClient(proxy=proxy, verify=verify, timeout=60.0),
    )


def get_llm(temperature: float = 0.2) -> ChatOpenAI:
    """获取 LangChain ChatOpenAI 实例（单例，复用连接）。"""
    global _llm_instance
    if _llm_instance is None:
        api_key, base_url, model = _cfg()
        http_client, http_async_client = _http_clients()
        extra: dict[str, Any] = {}
        if http_client is not None:
            extra["http_client"] = http_client
            extra["http_async_client"] = http_async_client
        else:
            proxy = _proxy_url()
            if proxy:
                extra["openai_proxy"] = proxy
        _llm_instance = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            timeout=60,
            max_retries=2,
            callbacks=_init_langfuse_once(),
            **extra,
        )
    return _llm_instance


def chat_once(prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
    """快速一问一答（无历史）。"""
    llm = get_llm(temperature=temperature)
    messages = []
    if system:
        messages.append(("system", system))
    messages.append(("human", prompt))
    resp = llm.invoke(messages)
    return resp.content if isinstance(resp.content, str) else str(resp.content)


def chat_stream(prompt: str, system: str | None = None, temperature: float = 0.2) -> Iterable[str]:
    """流式输出 (yield chunks)。"""
    llm = get_llm(temperature=temperature)
    messages = []
    if system:
        messages.append(("system", system))
    messages.append(("human", prompt))
    for chunk in llm.stream(messages):
        if chunk.content:
            yield chunk.content if isinstance(chunk.content, str) else str(chunk.content)


def healthcheck() -> dict:
    """快速测试 LLM 连通性（仅在 /healthz 时调用）"""
    try:
        api_key, base_url, model = _cfg()
        # 不真的发请求避免每次 health 都消费 token，仅检查配置完整
        out = {
            "configured": True,
            "base_url": base_url,
            "model": model,
            "api_key_set": bool(api_key),
            "api_key_prefix": api_key[:8] + "..." if len(api_key) > 12 else "(short)",
        }
        pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
        out["langfuse"] = {
            "enabled": bool(pk and sk),
            "host": os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            "public_key_prefix": pk[:10] + "..." if len(pk) > 10 else "",
        }
        return out
    except Exception as e:
        return {"configured": False, "error": str(e)}
