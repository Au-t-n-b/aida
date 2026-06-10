"""
智慧工勘 v4 — 统一日志工具

写入 JSON Lines 格式到 exec_log.json。
（从 smart_survey/services/logger.py 迁移，path_config 改为 aida 本地路径）
"""
from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timezone
from typing import Optional


def log(
    level: str,
    module: str,
    step: str,
    message: str,
    activity_id: str = "",
    project_name: str = "",
    input_summary: str = "",
    output_summary: str = "",
    error_code: Optional[str] = None,
    duration_ms: Optional[int] = None,
    stack_trace: Optional[str] = None,
    log_path: Optional[str] = None,
) -> None:
    """
    写入一条日志到 exec_log.json（JSON Lines 格式，追加写入）。

    参数:
        level: "INFO" | "WARN" | "ERROR"
        module: 模块名称
        step: 当前函数名/步骤名
        message: 人类可读描述
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "module": module,
        "step": step,
        "message": message,
        "activity_id": activity_id,
        "project_name": project_name,
        "input_summary": input_summary[:200] if input_summary else "",
        "output_summary": output_summary[:200] if output_summary else "",
    }
    if error_code:
        entry["error_code"] = error_code
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms
    if stack_trace:
        entry["stack_trace"] = stack_trace

    if log_path is None:
        from ..path_config import get_exec_log_path
        log_path = get_exec_log_path()

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_error(
    module: str,
    step: str,
    error_code: str,
    message: str,
    exc: Optional[Exception] = None,
    **kwargs,
) -> None:
    """ERROR 级别日志快捷方法。"""
    st = traceback.format_exc() if exc else None
    log(
        level="ERROR",
        module=module,
        step=step,
        message=message,
        error_code=error_code,
        stack_trace=st,
        **kwargs,
    )


def log_info(module: str, step: str, message: str, **kwargs) -> None:
    """INFO 级别日志快捷方法。"""
    log(level="INFO", module=module, step=step, message=message, **kwargs)


def log_warn(module: str, step: str, message: str, **kwargs) -> None:
    """WARN 级别日志快捷方法。"""
    log(level="WARN", module=module, step=step, message=message, **kwargs)
