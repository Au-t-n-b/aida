"""device_install · 共享小工具（无副作用）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def as_str(v: Any) -> str:
    """单元格值 → 去空白字符串（None → ""）。"""
    if v is None:
        return ""
    return str(v).strip()


def col_idx(header: list[str], *names: str) -> int | None:
    """在表头里按候选列名（大小写不敏感）找列下标；找不到返回 None。"""
    for name in names:
        for i, h in enumerate(header):
            if h == name or h.lower() == name.lower():
                return i
    return None


def parse_date_str(v: Any) -> str:
    """各种日期表示 → YYYY-MM-DD 字符串（无法解析则原样返回去空白文本）。"""
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    if not s:
        return ""
    # 形如 2026-04-16 00:00:00 → 取日期段
    for sep in (" ", "T"):
        if sep in s:
            s = s.split(sep, 1)[0]
            break
    return s
