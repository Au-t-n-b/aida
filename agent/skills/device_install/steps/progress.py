"""
progress · 进展反馈（command=progress_report）

两段确认型 HITL：
  progress_select → ChoiceCard 选择要上报的任务（已下发/进行中），写 project["reporting_task_id"]
  progress_apply  → ChoiceCard 选择新状态，写回 tasks_state.json
apply_resume_payload 负责把用户选择写入 project（见 skill.py）。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import tasks_state_path, refresh_task_metrics
from ..services._common import as_str
from ..services.task_store import load_tasks_state, save_tasks_state, get_tasks, iso_now

_STATUS_OPTIONS = [
    {"label": "进行中", "value": "进行中"},
    {"label": "已完成", "value": "已完成"},
    {"label": "暂停/受阻", "value": "暂停/受阻"},
]


def _task_by_id(ctx: SkillContext, task_id: str) -> dict | None:
    for t in get_tasks(str(tasks_state_path(ctx))):
        if isinstance(t, dict) and as_str(t.get("id")) == as_str(task_id):
            return t
    return None


def _task_summary_line(task: dict) -> str:
    unit = as_str(task.get("unit"))
    act = as_str(task.get("activity_name"))
    st = as_str(task.get("status"))
    parts = [p for p in (unit, act) if p]
    head = " · ".join(parts) if parts else as_str(task.get("id"))
    return f"{head}（{st}）" if st else head


class ProgressSelectStep(BaseStep):
    key = "progress_select"
    name = "选择上报任务"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if ctx.project.get("reporting_task_id"):
            return {"ok": True, "missing": []}
        tasks = [t for t in get_tasks(str(tasks_state_path(ctx))) if t.get("status") != "待下发"]
        if not tasks:
            # 无可上报任务：放行，run 给出提示
            return {"ok": True, "missing": []}
        options = [
            {"label": f"{t.get('unit','')} · {t.get('activity_name','')}（{t.get('status','')}）",
             "value": t.get("id", "")}
            for t in tasks[:20]
        ]
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [{"id": "report_task", "label": "选择要上报进展的任务", "options": options}],
            "note": "请选择要更新进展的安装任务。",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        tasks = [t for t in get_tasks(str(tasks_state_path(ctx))) if isinstance(t, dict)]
        active = [t for t in tasks if t.get("status") != "待下发"]

        if should_skip(self.key, ctx.project):
            emit("[progress_select] 主建设流水线不包含进展上报环节")
            if tasks:
                done = sum(1 for t in tasks if t.get("status") == "已完成")
                emit(
                    f"[progress_select] 当前任务概况：共 {len(tasks)} 条，"
                    f"已下发/进行中 {len(active)} 条，已完成 {done} 条"
                )
            emit("[progress_select] ✓ 本步已自动跳过（进展反馈请单独启动）")
            return {"metrics": refresh_task_metrics(ctx)}

        tid = as_str(ctx.project.get("reporting_task_id"))
        if not tid:
            emit("[progress_select] 暂无可上报的已下发/进行中任务")
            emit("[progress_select] ✓ 请先完成计划下发后再上报进展")
            return {"metrics": refresh_task_metrics(ctx)}

        task = _task_by_id(ctx, tid)
        if task:
            emit(f"[progress_select] 管理单元：{as_str(task.get('unit'))}")
            emit(f"[progress_select] 活动名称：{as_str(task.get('activity_name'))}")
            emit(f"[progress_select] ✓ 已选定上报任务（当前状态：{as_str(task.get('status'))}）")
        else:
            emit(f"[progress_select] ✓ 已选定任务 ID：{tid}")
        return {"metrics": refresh_task_metrics(ctx)}


class ProgressApplyStep(BaseStep):
    key = "progress_apply"
    name = "更新任务进展"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if not ctx.project.get("reporting_task_id"):
            return {"ok": True, "missing": []}  # 没选到任务，跳过
        if ctx.project.get("reporting_status"):
            return {"ok": True, "missing": []}
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [{"id": "report_status", "label": "更新任务状态", "options": _STATUS_OPTIONS}],
            "note": "请选择该任务的当前状态。",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            emit("[progress_apply] 主建设流水线不包含进展更新环节")
            emit("[progress_apply] ✓ 本步已自动跳过（进展反馈请单独启动）")
            return {"metrics": refresh_task_metrics(ctx)}

        task_id = as_str(ctx.project.get("reporting_task_id"))
        new_status = as_str(ctx.project.get("reporting_status"))
        if not task_id or not new_status:
            emit("[progress_apply] 未选择上报任务或目标状态")
            emit("[progress_apply] ✓ 无可更新项，已跳过")
            return {"metrics": refresh_task_metrics(ctx)}

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        hit_task: dict | None = None
        for t in st.get("tasks", []):
            if isinstance(t, dict) and as_str(t.get("id")) == task_id:
                hit_task = t
                t["status"] = new_status
                if new_status == "已完成":
                    t["progress_pct"] = 100
                t.setdefault("progress_records", []).append({"ts": iso_now(), "status": new_status})
                break
        if hit_task is not None:
            save_tasks_state(state_path, st)
            emit(f"[progress_apply] 任务：{_task_summary_line(hit_task)}")
            emit(f"[progress_apply] ✓ 进展已更新为「{new_status}」")
            if new_status == "已完成":
                emit("[progress_apply] ✓ 任务进度 100%")
        else:
            emit(f"[progress_apply] ✗ 未找到任务 {task_id}")
        return {"metrics": refresh_task_metrics(ctx)}
