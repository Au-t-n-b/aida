"""数据中心连接配置（读环境变量）。"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


def _load_agent_env() -> None:
    aida_root = Path(__file__).resolve().parents[2]
    env_path = aida_root / "agent" / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_agent_env()


def datacenter_base() -> str:
    url = os.environ.get("DATA_CENTER_BASE_URL") or os.environ.get("AIDA_DATACENTER_BASE")
    if not url:
        raise RuntimeError(
            "DATA_CENTER_BASE_URL 未配置：请在 agent/.env 中设置"
            "（例：DATA_CENTER_BASE_URL=http://10.143.2.231:8000）"
        )
    return url.rstrip("/")


def _is_local_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1")


def http_proxy() -> str | None:
    if _is_local_host(datacenter_base()):
        return None
    return (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("http_proxy")
        or None
    )


def ssl_verify() -> bool:
    v = os.environ.get("ZHIPU_SSL_VERIFY", "").strip().lower()
    if v in ("1", "true", "yes"):
        return True
    if v in ("0", "false", "no"):
        return False
    return http_proxy() is None
