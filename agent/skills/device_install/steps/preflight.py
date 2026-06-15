"""
preflight · 环境预检（internal=True，豁免 SKILL.md 契约）

检查 ProjectData/Input 是否已有上游《交付计划表.xlsx》（+《设备位置表》《到货信息表》），
作为「生成责任人信息表 / 生成设备安装实施计划」的输入源。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._io import (
    refresh_task_metrics,
    tasks_state_path,
    find_delivery_plan,
    find_position_table,
    find_arrival_table,
)
from ..path_config import get_upstream_input_dir
from ..services.task_store import get_tasks


class PreflightStep(BaseStep):
    key = "preflight"
    name = "环境预检"
    artifacts_pattern = []
    internal = True

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": [], "found": [], "note": ""}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        ctx.ensure_dirs()
        reset_info = ctx.project.get("_last_reset")
        if isinstance(reset_info, dict) and reset_info.get("ok"):
            n = reset_info.get("removed_count", 0)
            emit(f"[preflight] 已重置会话：清除 {n} 个历史产物/运行态文件")

        emit("[preflight] 正在扫描设备安装环境…")
        emit("[preflight] 正在校验上游交付计划表…")

        delivery = find_delivery_plan(ctx)
        position = find_position_table(ctx)
        arrival = find_arrival_table(ctx)
        plan_ok = bool(delivery)
        tasks_n = len(get_tasks(str(tasks_state_path(ctx))))

        def _file_line(label: str, ready: bool) -> str:
            mark = "√" if ready else "✗"
            status = "已就绪" if ready else "缺失"
            return f"{mark} {label}：{status}"

        emit(_file_line("交付计划表", bool(delivery)))
        emit(_file_line("设备位置表", bool(position)))
        emit(_file_line("到货信息表", bool(arrival)))

        # 预检 LLM 摘要仅作展示，约 19s 且会阻塞流水线；统一跳过，与中间对话栏设计稿一致。
        emit("LLM 摘要跳过")

        metrics: dict = {
            "source_dir": str(get_upstream_input_dir(ctx.project)),
            "dispatch_plan_ready": plan_ok,
            "parsed_tasks": tasks_n,
        }
        metrics.update(refresh_task_metrics(ctx))
        return {"metrics": metrics}
