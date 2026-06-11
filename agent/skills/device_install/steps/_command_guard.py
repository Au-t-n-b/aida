"""
_command_guard · 命令路由守卫（单流水线 · 无意图选择卡）

路由字段 project["command"] 由 /start 启动载荷直接给定：
  ""/"build"        → 主建设流水线（接收实施计划→…→ESN 填写）
  "progress_report" → 进展反馈（选任务 + 选状态）
  "progress_query"  → 进展查询（只读）
  "plan_query"      → 计划查询（只读）
  "plan_adjust"     → 计划调整（引导）
  "device_overview" → 设备总览（只读）
"""
from __future__ import annotations

BUILD = "build"

STEP_COMMANDS: dict[str, frozenset[str]] = {
    "plan_receive":    frozenset({BUILD}),
    "task_dispatch":   frozenset({BUILD}),
    "sn_generate":     frozenset({BUILD}),
    "esn_fill":        frozenset({BUILD}),
    "progress_select":  frozenset({"progress_report"}),
    "progress_apply":   frozenset({"progress_report"}),
    "progress_query":   frozenset({"progress_query"}),
    "plan_query":       frozenset({"plan_query"}),
    "plan_adjust":      frozenset({"plan_adjust"}),
    "device_overview":  frozenset({"device_overview"}),
}


def current_command(project: dict) -> str:
    return (project or {}).get("command", "") or BUILD


def should_skip(step_key: str, project: dict) -> bool:
    allowed = STEP_COMMANDS.get(step_key)
    if allowed is None:
        return False
    return current_command(project) not in allowed
