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
from ._io import tasks_state_path, refresh_task_metrics
from ..services.source_files import get_source_dir, sync_dispatch_plan_to_input
from ..services.dispatch_plan_parser import (
    DISPATCH_PLAN_FILENAME,
    resolve_dispatch_plan_path,
    parse_dispatch_plan_with_sn,
    save_sn_pool,
)
from ..services.task_store import save_tasks_state, load_tasks_state, iso_now


class PlanReceiveStep(BaseStep):
    key = "plan_receive"
    name = "接收实施计划"
    artifacts_pattern = [f"ProjectData/Input/{DISPATCH_PLAN_FILENAME}"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        existing = st.get("tasks") or []

        source_dir = get_source_dir(ctx.work_root)
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

        preserve = bool(
            ctx.project.get("dispatch_rows")
            or ctx.project.get("dispatch_confirmed")
            or ctx.project.get("esn_rows")
        )
        if preserve and existing:
            tasks = existing
            emit(f"[plan_receive] 复用已解析任务：{len(tasks)} 条（resume 重放）")
        else:
            emit(f"[plan_receive] 解析上游实施计划：{os.path.basename(plan_path)}")
            tasks, sn_rows = parse_dispatch_plan_with_sn(plan_path)
            save_tasks_state(state_path, {
                "loaded_at": iso_now(),
                "source_plan": str(plan_path),
                "tasks": tasks,
            })
            pool_path = ctx.runtime_dir / "sn_pool.json"
            save_sn_pool(pool_path, source=str(plan_path), rows=sn_rows)
            emit(
                f"[plan_receive] ✓ 已解析 {len(tasks)} 条实施计划、"
                f"{len(sn_rows)} 条 SN 设备记录（全量池）"
            )

        metrics = {"parsed_tasks": len(tasks), "received_plan": True}
        metrics.update(refresh_task_metrics(ctx))
        artifacts = [ctx.rel(plan_path)] if plan_path.exists() else []
        return {"artifacts": artifacts, "metrics": metrics}
