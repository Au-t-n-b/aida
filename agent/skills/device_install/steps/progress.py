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
from ..services.task_store import load_tasks_state, save_tasks_state, get_tasks, iso_now

_STATUS_OPTIONS = [
    {"label": "进行中", "value": "进行中"},
    {"label": "已完成", "value": "已完成"},
    {"label": "暂停/受阻", "value": "暂停/受阻"},
]


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
        if should_skip(self.key, ctx.project):
            return {}
        tid = ctx.project.get("reporting_task_id", "")
        if not tid:
            emit("[progress_select] 暂无已下发任务可上报进展")
        else:
            emit(f"[progress_select] 选定任务：{tid}")
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
            return {}
        task_id = ctx.project.get("reporting_task_id", "")
        new_status = ctx.project.get("reporting_status", "")
        if not task_id or not new_status:
            emit("[progress_apply] 无任务/状态可更新，跳过")
            return {"metrics": refresh_task_metrics(ctx)}

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        hit = False
        for t in st.get("tasks", []):
            if isinstance(t, dict) and t.get("id") == task_id:
                t["status"] = new_status
                t.setdefault("progress_records", []).append({"ts": iso_now(), "status": new_status})
                hit = True
                break
        if hit:
            save_tasks_state(state_path, st)
            emit(f"[progress_apply] ✓ 任务 {task_id} 进展更新为「{new_status}」")
        else:
            emit(f"[progress_apply] 未找到任务 {task_id}")
        return {"metrics": refresh_task_metrics(ctx)}
