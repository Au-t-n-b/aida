"""device_install · 共享小工具（无副作用）。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# 责任人末尾工号：「梁贝 WX616744」「张三(w001234)」等
_PRINCIPAL_ID_TAIL = re.compile(
    r"(?:\s+[A-Za-z]*\d+[A-Za-z0-9]*|\s*[（(]\s*[A-Za-z]*\d+[A-Za-z0-9]*\s*[）)])\s*$",
)


def as_str(v: Any) -> str:
    """单元格值 → 去空白字符串（None → ""）。"""
    if v is None:
        return ""
    return str(v).strip()


def principal_display_name(v: Any) -> str:
    """责任人列展示：只保留姓名，去掉末尾工号。"""
    s = as_str(v)
    if not s:
        return ""
    while True:
        n = _PRINCIPAL_ID_TAIL.sub("", s).strip()
        if n == s:
            break
        s = n
    return s

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
