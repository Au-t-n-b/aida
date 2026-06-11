"""
plan_import · 计划导入（从源文件目录读取 + 解析）

command: build 专属

无 HITL：源文件（任务计划表 / 到货信息表 / 建模仿真设备位置表）从
DEVICE_INSTALL_SOURCE_ROOT 指定目录直接读取（见 services/source_files.py；缺文件则失败）。
run：同步源表到 Input/（源目录与 Input 相同时不复制）→ 解析三级安装任务
→ 若有《责任人信息表》则合并责任人 → 落 tasks_state.json。
"""
from __future__ import annotations

import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import find_input, tasks_state_path, refresh_task_metrics
from ..services.source_files import get_source_dir, sync_to_input
from ..services.plan_parser import parse_task_plan, parse_principal_table, merge_principals
from ..services.task_store import save_tasks_state, load_tasks_state, iso_now


class PlanImportStep(BaseStep):
    key = "plan_import"
    name = "计划导入"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        # 源文件从配置目录直接读取，无需用户上传 → 始终放行（同步+解析在 run 内完成）
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        existing = st.get("tasks") or []

        source_dir = get_source_dir(ctx.work_root)
        synced = sync_to_input(source_dir, ctx.input_dir)
        if synced:
            verb = "已就绪" if source_dir.resolve() == ctx.input_dir.resolve() else "已同步"
            emit(f"[plan_import] 源目录 {source_dir}，{verb} {len(synced)} 个源文件：{', '.join(synced)}")

        plan = find_input(ctx, "任务计划")
        # full_restart 重放期间保留已编辑任务；全新启动（project 无 HITL 痕迹）则重新解析计划表
        preserve = bool(
            ctx.project.get("principal_rows")
            or ctx.project.get("tasks_rows")
            or ctx.project.get("tasks_confirmed")
            or ctx.project.get("dispatch_rows")
            or ctx.project.get("dispatch_confirmed")
            or ctx.project.get("esn_rows")
        )
        if preserve and existing:
            tasks = existing
            emit(f"[plan_import] 复用已解析任务：{len(tasks)} 条（resume 重放）")
        elif plan:
            emit(f"[plan_import] 解析任务计划表：{os.path.basename(plan)}")
            tasks = parse_task_plan(plan)
            if not tasks:
                raise RuntimeError("未从《任务计划表》解析到任何 7.x 安装任务，请检查活动ID列。")
            principal_path = find_input(ctx, "责任人")
            merged = 0
            if principal_path:
                principals = parse_principal_table(principal_path)
                merged = merge_principals(tasks, principals)
                emit(
                    f"[plan_import] 已解析《责任人信息表》：{os.path.basename(principal_path)}"
                    f"（合并 {merged} 条责任人）"
                )
            save_tasks_state(state_path, {"loaded_at": iso_now(), "tasks": tasks})
            emit(f"[plan_import] ✓ 解析到 {len(tasks)} 条三级安装任务")
        else:
            raise RuntimeError("plan_import: 源目录未提供任务计划表")

        metrics = {"parsed_tasks": len(tasks)}
        metrics.update(refresh_task_metrics(ctx))
        return {"metrics": metrics}
