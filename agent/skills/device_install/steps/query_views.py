"""
query_views · 只读 / 引导类辅助流

  progress_query  · 进展查询（整体完成率 + 按管理单元）
  plan_query      · 计划查询（任务明细表）
  device_overview · 设备总览（按机房分组）
  plan_adjust     · 计划调整（引导用户改表后重新计划导入）

均无 HITL：read 任务状态 → 写汇总指标到 metrics（SDUI 投影器据此渲染只读卡）。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import tasks_state_path, refresh_task_metrics
from ..services.task_store import get_tasks


class _AuxBase(BaseStep):
    artifacts_pattern: list[str] = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": []}

    def _no_tasks(self, ctx: SkillContext) -> bool:
        return not get_tasks(str(tasks_state_path(ctx)))


class ProgressQueryStep(_AuxBase):
    key = "progress_query"
    name = "进展查询"

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}
        if self._no_tasks(ctx):
            emit("[progress_query] 暂无任务数据，请先完成接收实施计划")
            return {"metrics": {"aux_view": "progress_query"}}
        m = refresh_task_metrics(ctx)
        emit(f"[progress_query] 整体完成率 {m.get('di_completion_pct', 0)}%"
             f"（已完成 {m.get('di_done', 0)}/{m.get('di_total', 0)}）")
        m["aux_view"] = "progress_query"
        return {"metrics": m}


class PlanQueryStep(_AuxBase):
    key = "plan_query"
    name = "计划查询"

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}
        if self._no_tasks(ctx):
            emit("[plan_query] 暂无任务数据，请先完成接收实施计划")
            return {"metrics": {"aux_view": "plan_query"}}
        m = refresh_task_metrics(ctx)
        emit(f"[plan_query] 共 {m.get('di_total', 0)} 条安装任务")
        m["aux_view"] = "plan_query"
        return {"metrics": m}


class DeviceOverviewStep(_AuxBase):
    key = "device_overview"
    name = "设备总览"

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}
        if self._no_tasks(ctx):
            emit("[device_overview] 暂无任务数据，请先完成接收实施计划")
            return {"metrics": {"aux_view": "device_overview"}}
        m = refresh_task_metrics(ctx)
        emit(f"[device_overview] {len(m.get('di_by_unit_rows', []))} 个管理单元")
        m["aux_view"] = "device_overview"
        return {"metrics": m}


class PlanAdjustStep(_AuxBase):
    key = "plan_adjust"
    name = "计划调整"

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}
        emit("[plan_adjust] 如需调整实施计划，请由上游模块重新产出《设备安装实施计划》"
             "并放入 DEVICE_INSTALL_SOURCE_ROOT，再以 command=build 重新执行主建设流程。")
        m = refresh_task_metrics(ctx)
        m["aux_view"] = "plan_adjust"
        return {"metrics": m}
