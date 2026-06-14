"""Manager 配置（环境变量 / agent/.env）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


_AIDA_ROOT = _repo_root()
if str(_AIDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AIDA_ROOT))


def _load_agent_env() -> None:
    env_path = _repo_root() / "agent" / ".env"
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
    url = (
        os.environ.get("DATA_CENTER_BASE_URL")
        or os.environ.get("AIDA_DATACENTER_BASE")
    )
    if not url:
        raise RuntimeError(
            "DATA_CENTER_BASE_URL 未配置：请在 agent/.env 中设置远端数据中心 API 地址"
            "（例：DATA_CENTER_BASE_URL=http://10.143.2.231:8000）"
        )
    return url.rstrip("/")


def aida_agent_base() -> str:
    return os.environ.get("AIDA_AGENT_BASE_URL", "http://127.0.0.1:7401").rstrip("/")


def manager_host() -> str:
    return os.environ.get("MANAGER_HOST", "0.0.0.0")


def manager_port() -> int:
    return int(os.environ.get("MANAGER_PORT", "8001"))


def _is_local_host(url: str) -> bool:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1")


def _is_private_datacenter_host(url: str) -> bool:
    """内网数据中心 IP 必须直连；走企业 HTTP_PROXY 常被网关 504。"""
    from urllib.parse import urlparse
    import ipaddress

    host = (urlparse(url).hostname or "").lower()
    if _is_local_host(url):
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def http_proxy() -> str | None:
    base = datacenter_base()
    if _is_private_datacenter_host(base):
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
