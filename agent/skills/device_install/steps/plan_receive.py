"""
plan_receive · 接收上游《设备安装实施计划》（双 Sheet 解析）

command: build 专属

从 DEVICE_INSTALL_SOURCE_ROOT 读取《设备安装实施计划.xlsx》→ 同步到 Input/
→ 解析 Sheet1 写入 tasks_state.json；Sheet2 写入 sn_pool.json。
"""
from __future__ import annotations

import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import (
    reload_tasks_from_plan,
    should_merge_runtime_on_reparse,
    refresh_task_metrics,
    staged_cold_start_pace,
    PLAN_RECEIVE_PACE_SEC,
)
from ..services.source_files import get_source_dir, sync_dispatch_plan_to_input
from ..services.dispatch_plan_parser import (
    DISPATCH_PLAN_FILENAME,
    resolve_dispatch_plan_path,
)


class PlanReceiveStep(BaseStep):
    key = "plan_receive"
    name = "接收实施计划"
    artifacts_pattern = [f"ProjectData/Input/{DISPATCH_PLAN_FILENAME}"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        staged_cold_start_pace(
            ctx.project, emit,
            total_sec=PLAN_RECEIVE_PACE_SEC,
            stages=[
                "[plan_receive] 正在同步上游实施计划…",
                "[plan_receive] 正在解析计划明细 Sheet…",
                "[plan_receive] 正在解析 SN 设备池 Sheet…",
            ],
        )

        source_dir = get_source_dir(ctx.work_root, ctx.project)
        synced = sync_dispatch_plan_to_input(source_dir, ctx.input_dir)
        if synced:
            verb = "已就绪" if source_dir.resolve() == ctx.input_dir.resolve() else "已同步"
            emit(f"[plan_receive] 源目录 {source_dir}，{verb}《{synced}》")

        plan_path = resolve_dispatch_plan_path(ctx.input_dir)
        if not plan_path:
            raise RuntimeError(
                f"plan_receive: 未找到《{DISPATCH_PLAN_FILENAME}》，"
                "请确认上游已产出并放入 DEVICE_INSTALL_SOURCE_ROOT"
            )

        merge = should_merge_runtime_on_reparse(ctx.project)
        emit(
            f"[plan_receive] 重新解析上游实施计划：{os.path.basename(plan_path)}"
            + ("（保留本 run 下发/进度态）" if merge else "")
        )
        tasks = reload_tasks_from_plan(ctx, merge_runtime=merge)
        if not tasks:
            raise RuntimeError(f"plan_receive: 《{DISPATCH_PLAN_FILENAME}》解析结果为空")
        emit(f"[plan_receive] ✓ 已解析 {len(tasks)} 条实施计划（SN 全量池已同步刷新）")

        metrics = {"parsed_tasks": len(tasks), "received_plan": True}
        metrics.update(refresh_task_metrics(ctx))
        artifacts = [ctx.rel(plan_path)] if plan_path.exists() else []
        return {"artifacts": artifacts, "metrics": metrics}
