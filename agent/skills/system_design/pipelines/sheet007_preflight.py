"""007 sheet 预检 · 对齐 a3 lld_workflow.is_step_eligible 门控。

执行 L3 子 skill 前检查 007 是否含对应端口互联 sheet；
缺失则跳过（不跑 pipeline、不报错），与 Conductor skipped_not_eligible 一致。
执行后若 pipeline 仍报 007 sheet 相关错误，由 is_skippable_007_error 转为 skipped。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 会读取 007 指定 connect sheet 的 args_style
_PREFLIGHT_STYLES = frozenset({
    "dw_007", "connect_resource", "gcm", "l2l3_sheet", "oob_plan", "ni",
})

# 007 sheet 物理缺失 → 可跳过（对齐 Conductor keep_going）
# 注意：sheet 存在但解析/字段不满足（含「可用 sheet:」）不可跳过，应报错以便修复 007 格式。
_SKIPPABLE_MARKERS = (
    "007: 无法在限定平面 sheet 中解析",
    "无法在限定平面 sheet 中解析",
    "Worksheet named",
    " not found",
    "not in workbook",
    "007 sheet 缺失",
)


def _bootstrap_resolver() -> None:
    from .a3_paths import get_subskills_root

    sp = str(get_subskills_root())
    if sp not in sys.path:
        sys.path.insert(0, sp)


def _resolve_required_sheets(command: str, default_sheet: str | None) -> list[str]:
    """命令 → 007 端口互联 sheet 候选（| 分隔多选）。"""
    if default_sheet:
        _bootstrap_resolver()
        from _runtime_shared.sheet007_resolver import split_sheet_alternatives  # noqa: WPS433

        return split_sheet_alternatives(default_sheet)
    try:
        _bootstrap_resolver()
        from _runtime_shared.sheet007_resolver import (  # noqa: WPS433
            connect_sheet_for_command,
            split_sheet_alternatives,
        )

        return split_sheet_alternatives(connect_sheet_for_command(command))
    except KeyError:
        return []


def _sheet_eligible(required: list[str], workbook_sheets: list[str]) -> bool:
    """Mirror lld_workflow.is_step_eligible gate for address/interconnect steps."""
    if not required:
        return True
    wb_set = set(workbook_sheets)
    for item in required:
        if item in wb_set:
            return True
        if item == "互联":
            return True
        if "样本面端口互联" in item and "样本面端口互联" in wb_set:
            return True
        parts = [p.strip() for p in item.split("|") if p.strip()]
        if len(parts) > 1:
            for name in workbook_sheets:
                if all(p in name for p in parts):
                    return True
    return False


def check_connect_sheet_preflight(
    *,
    command: str,
    args_style: str,
    topology: Path | None,
    default_sheet: str | None = None,
) -> tuple[bool, str]:
    """返回 (should_run, skip_reason)。should_run=False 时跳过该 L3 命令。"""
    if args_style not in _PREFLIGHT_STYLES:
        return True, ""
    if topology is None or not Path(topology).is_file():
        return True, ""

    try:
        import pandas as pd

        sheet_names = list(pd.ExcelFile(topology).sheet_names)
    except Exception:
        return True, ""

    required = _resolve_required_sheets(command, default_sheet)
    if not required:
        return True, ""

    if _sheet_eligible(required, sheet_names):
        return True, ""

    display_sheet = (default_sheet or " | ".join(required)).strip()
    avail = "、".join(sheet_names[:12])
    if len(sheet_names) > 12:
        avail += "…"
    reason = (
        f"007 中无「{display_sheet}」sheet（现有：{avail}），"
        f"跳过「{command}」"
    )
    return False, reason


def resolve_default_sheet_for_topology(
    default_sheet: str | None,
    topology: Path | None,
) -> str | None:
    """将 l3_skill_index 中 ``A | B`` 形式 default_sheet 解析为 007 工作簿内实际 sheet 名。"""
    if not default_sheet or "|" not in str(default_sheet):
        return default_sheet
    required = _resolve_required_sheets("", default_sheet)
    if not required:
        return default_sheet
    if topology is None or not Path(topology).is_file():
        return required[0]
    try:
        import pandas as pd

        sheet_names = list(pd.ExcelFile(topology).sheet_names)
    except Exception:
        return required[0]
    wb_set = set(sheet_names)
    for item in required:
        if item in wb_set:
            return item
    for item in required:
        for name in sheet_names:
            if item in name or name in item:
                return name
    if _sheet_eligible(required, sheet_names):
        for item in required:
            if item in wb_set:
                return item
    return required[0]


def is_skippable_007_error(text: str) -> bool:
    """pipeline stderr/异常是否属于 007 sheet 物理缺失（应跳过而非整批失败）。"""
    s = str(text or "")
    if not s.strip():
        return False
    # sheet 在 workbook 中已列出，但数据/格式读失败 → 真实错误，不得当作「sheet 缺失」跳过
    if "可用 sheet:" in s or "可用 sheet：" in s:
        return False
    if "无法读取" in s and ("互联数据" in s or "互联表" in s or "计算参数面" in s):
        return False
    if "指定 sheet" in s and ("无法读取" in s or "互联数据" in s):
        return False
    return any(m in s for m in _SKIPPABLE_MARKERS)


def is_soft_skip_message(text: str) -> bool:
    """007 sheet 缺失 / 命令已跳过类提示 —— 记 warning、不阻断后续 step、UI 不展示「执行失败」。"""
    s = str(text or "").strip()
    if not s:
        return False
    if is_skippable_007_error(s):
        return True
    if "007 缺少对应 sheet" in s:
        return True
    if "007 中无" in s and "跳过" in s:
        return True
    if "已跳过" in s and ("007" in s or "sheet" in s.lower()):
        return True
    return False
