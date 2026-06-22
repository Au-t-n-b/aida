"""
preflight · 环境预检（internal=True，豁免 SKILL.md 契约）

检查三个上游目录是否已有《交付计划表》《设备位置表》《到货信息表》，
作为「指派责任人 / 确认实施计划」的输入源。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._io import (
    refresh_task_metrics,
    tasks_state_path,
    find_delivery_plan,
    find_position_table,
    find_arrival_table,
    load_or_parse_delivery_tasks,
)
from .. import dc_paths
from ..services.task_store import get_tasks


class PreflightStep(BaseStep):
    key = "preflight"
    name = "环境预检"
    artifacts_pattern = []
    internal = True

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": [], "found": [], "note": ""}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        reset_info = ctx.project.get("_last_reset")
        if isinstance(reset_info, dict) and reset_info.get("ok"):
            n = reset_info.get("removed_count", 0)
            emit(f"[preflight] 已重置会话：清除 {n} 个历史产物/运行态文件")

        emit("[preflight] 正在扫描设备安装环境…")
        emit("[preflight] 正在校验三个上游输入文件…")

        delivery = find_delivery_plan(ctx)
        position = find_position_table(ctx)
        arrival = find_arrival_table(ctx)
        plan_ok = bool(delivery)
        tasks_n = len(get_tasks(str(tasks_state_path(ctx))))

        delivery_dir = dc_paths.delivery_plan_loc().describe()
        position_dir = dc_paths.position_loc().describe()
        arrival_dir = dc_paths.arrival_loc().describe()

        def _file_line(label: str, ready: bool, directory: str) -> None:
            mark = "√" if ready else "✗"
            status = "已就绪" if ready else "缺失"
            emit(f"{mark} {label}：{status}（{directory}）")

        _file_line("交付计划表", bool(delivery), delivery_dir)
        _file_line("设备位置表", bool(position), position_dir)
        _file_line("到货信息表", bool(arrival), arrival_dir)

        parse_ok = False
        parse_note = ""
        if delivery:
            try:
                tasks_probe = load_or_parse_delivery_tasks(ctx)
                parse_ok = bool(tasks_probe)
                if not parse_ok:
                    parse_note = "《交付计划表》存在但未解析到 7.x 安装任务"
            except RuntimeError as e:
                parse_note = str(e)
            if parse_ok:
                emit(f"√ 交付计划表解析：{len(tasks_probe)} 条安装任务")
            elif parse_note:
                emit(f"✗ 交付计划表解析：{parse_note}")

        # 预检 LLM 摘要仅作展示，约 19s 且会阻塞流水线；统一跳过，与中间对话栏设计稿一致。
        emit("LLM 摘要跳过")

        if not (plan_ok and position and arrival):
            missing = [
                n for n, ok in (
                    ("交付计划表", plan_ok),
                    ("设备位置表", bool(position)),
                    ("到货信息表", bool(arrival)),
                ) if not ok
            ]
            raise RuntimeError(f"上游输入未齐备：{', '.join(missing)}（请由上游模块交付至对应目录）")
        if delivery and not parse_ok:
            raise RuntimeError(parse_note or "《交付计划表》无法解析，请检查文件格式与 ACTIVITY_ID 列")

        metrics: dict = {
            "delivery_plan_dir": str(delivery_dir),
            "position_table_dir": str(position_dir),
            "arrival_input_dir": str(arrival_dir),
            "source_dir": str(delivery_dir),
            "dispatch_plan_ready": plan_ok,
            "parsed_tasks": len(tasks_probe) if parse_ok else tasks_n,
        }
        metrics.update(refresh_task_metrics(ctx))
        return {"metrics": metrics}
