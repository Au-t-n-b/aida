"""数据中心模块日志配置。"""
from __future__ import annotations

import logging

LOG = logging.getLogger("aida.datacenter")


def mask_token(token: str | None) -> str:
    if not token:
        return "(none)"
    if len(token) <= 12:
        return "***"
    return f"{token[:6]}...{token[-4:]}"
