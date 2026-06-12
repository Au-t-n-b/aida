# -*- coding: utf-8 -*-
"""灵衢健康检查 · 轮询后全失败门禁（failNum == totalNums）。"""
from __future__ import annotations

from typing import Any


def check_all_devices_failed(last_payload: dict[str, Any]) -> str | None:
    """返回非空字符串表示失败原因；None 表示通过。"""
    data = (last_payload.get("data") or {}) if isinstance(last_payload, dict) else {}
    if not isinstance(data, dict):
        return None
    total = int(data.get("totalNums") or 0)
    fail = int(data.get("failNum") or 0)
    if total > 0 and fail == total:
        return "灵衢健康检查执行失败，请检查设备连通情况"
    return None
