"""
tasks_generate · 任务生成（在线编辑）

command: build 专属

HITL EditableTable：在大盘内复核 / 微调全量任务的「计划开始 / 计划结束 / 责任人 / 责任主体」。
提交 → apply_resume_payload 写 project["tasks_rows"] + tasks_confirmed=True → run 落盘并生成
《设备安装全量任务.xlsx》。
放行条件：project 已带 tasks_confirmed。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import tasks_state_path, refresh_task_metrics
from ..services._common import as_str
from ..services.edit_fill import fill_tasks_rows
from ..services.table_builder import generate_full_tasks_xlsx
from ..services.task_store import load_tasks_state, save_tasks_state, get_tasks, iso_now
_COLUMNS = [
    {"key": "unit", "label": "管理单元", "width": 110},
    {"key": "activity_id", "label": "活动ID", "width": 80},
    {"key": "activity_name", "label": "活动名称", "width": 200},
    {"key": "start_date", "label": "计划开始", "editable": True, "type": "date"},
    {"key": "end_date", "label": "计划结束", "editable": True, "type": "date"},
    {"key": "principal", "label": "责任人", "editable": True, "type": "text"},
    {"key": "principal_org", "label": "责任主体", "editable": True, "type": "text"},
]


def _rows_from_tasks(tasks: list[dict]) -> list[dict]:
    return [
        {
            "id": as_str(t.get("id")),
            "unit": as_str(t.get("unit")),
            "activity_id": as_str(t.get("activity_id")),
            "activity_name": as_str(t.get("activity_name")),
            "start_date": as_str(t.get("start_date")),
            "end_date": as_str(t.get("end_date")),
            "principal": as_str(t.get("principal") or t.get("owner")),
            "principal_org": as_str(t.get("principal_org")),
        }
        for t in tasks
    ]


class TasksGenerateStep(BaseStep):
    key = "tasks_generate"
    name = "任务生成"
    artifacts_pattern = ["ProjectData/Output/设备安装全量任务.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if ctx.project.get("tasks_confirmed"):
            return {"ok": True, "missing": []}

        tasks = get_tasks(str(tasks_state_path(ctx)))
        if not tasks:
            return {"ok": False, "missing": ["ProjectData/Input/*任务计划*.xlsx"]}
        rows = _rows_from_tasks(tasks)
        # 预生成《设备安装全量任务》，作为本步「作业结果」展示（提交后会按编辑结果重生成）
        out = ctx.output_dir / "设备安装全量任务.xlsx"
        generate_full_tasks_xlsx(tasks, str(out))
        return {
            "ok": False,
            "missing": [],
            "need_edit": {
                "card_title": "全量任务复核",
                "title": "设备安装全量任务",
                "subtitle": f"共 {len(tasks)} 条任务，可在线微调「计划日期 / 责任人」，确认后生成全量任务表并进入计划下发。",
                "columns": _COLUMNS,
                "rows": rows,
                "fillLabel": "一键填写",
                "fillRows": fill_tasks_rows(rows),
                "rowKey": "id",
                "submitLabel": "确认并生成",
                "result_artifacts": [ctx.rel(out)] if out.exists() else [],
            },
            "note": "请复核全量任务，必要时在线微调后提交确认。",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        tasks = [t for t in st.get("tasks", []) if isinstance(t, dict)]
        if not tasks:
            raise RuntimeError("tasks_generate: 无任务数据，请先完成计划导入")

        rows = ctx.project.get("tasks_rows") or []
        edits = {as_str(r.get("id")): r for r in rows if isinstance(r, dict)}
        changed = 0
        for t in tasks:
            r = edits.get(as_str(t.get("id")))
            if not r:
                continue
            for key in ("start_date", "end_date", "principal", "principal_org"):
                if key in r:
                    t[key] = as_str(r.get(key))
            changed += 1
        if changed:
            st["tasks"] = tasks
            st["tasks_edited_at"] = iso_now()
            save_tasks_state(state_path, st)

        out = ctx.output_dir / "设备安装全量任务.xlsx"
        generate_full_tasks_xlsx(tasks, str(out))
        emit(f"[tasks_generate] ✓ 已确认全量任务表，共 {len(tasks)} 条（在线微调 {changed} 条）")

        artifacts = [ctx.rel(out)] if out.exists() else []
        metrics = {"full_tasks_rows": len(tasks)}
        metrics.update(refresh_task_metrics(ctx))
        return {"artifacts": artifacts, "metrics": metrics}
