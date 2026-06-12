"""
principal_fill · 责任人填报（在线编辑）

command: build 专属

HITL EditableTable：在大盘内逐条编辑「责任人 / 责任主体」。
提交 → apply_resume_payload 写 project["principal_rows"] → run 并入 tasks_state。
放行条件：project 已带 principal_rows（即已提交一次）。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import tasks_state_path, refresh_task_metrics
from ..path_config import get_output_dir, output_rel
from ..services._common import as_str, principal_display_name
from ..services.edit_fill import fill_principal_rows
from ..services.table_builder import generate_principal_table
from ..services.task_store import load_tasks_state, save_tasks_state, get_tasks, iso_now
_COLUMNS = [
    {"key": "activity_name", "label": "活动名称", "width": 220},
    {"key": "unit", "label": "管理单元", "width": 120},
    {"key": "start_date", "label": "计划开始", "width": 110},
    {"key": "end_date", "label": "计划结束", "width": 110},
    {"key": "principal", "label": "责任人", "editable": True, "type": "text", "placeholder": "填写责任人姓名"},
    {"key": "principal_org", "label": "责任主体", "editable": True, "type": "text", "placeholder": "华为 / 分包商"},
]


def _rows_from_tasks(tasks: list[dict]) -> list[dict]:
    return [
        {
            "id": as_str(t.get("id")),
            "activity_name": as_str(t.get("activity_name")),
            "unit": as_str(t.get("unit")),
            "start_date": as_str(t.get("start_date")),
            "end_date": as_str(t.get("end_date")),
            "principal": principal_display_name(t.get("principal") or t.get("owner")),
            "principal_org": as_str(t.get("principal_org")),
        }
        for t in tasks
    ]


class PrincipalFillStep(BaseStep):
    key = "principal_fill"
    name = "责任人填报"
    artifacts_pattern = ["ProjectData/Output/责任人信息表.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if ctx.project.get("principal_rows") is not None:
            return {"ok": True, "missing": []}

        tasks = get_tasks(str(tasks_state_path(ctx)))
        if not tasks:
            return {"ok": False, "missing": ["ProjectData/Input/*任务计划*.xlsx"]}
        # 责任人信息表已在 plan_import 合并且每条均有责任人/责任主体 → 跳过在线编辑
        if all(
            as_str(t.get("principal")) and as_str(t.get("principal_org"))
            for t in tasks
        ):
            return {"ok": True, "missing": []}
        rows = _rows_from_tasks(tasks)
        return {
            "ok": False,
            "missing": [],
            "need_edit": {
                "card_title": "责任人填报",
                "title": "责任人信息表",
                "subtitle": f"共 {len(tasks)} 条安装任务，请填写每条的「责任人 / 责任主体」后提交。",
                "columns": _COLUMNS,
                "rows": rows,
                "fillLabel": "一键填写",
                "fillRows": fill_principal_rows(rows),
                "rowKey": "id",
                "submitLabel": "保存并继续",
            },
            "note": "请在大盘内在线编辑责任人信息后提交。",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        tasks = [t for t in st.get("tasks", []) if isinstance(t, dict)]
        if not tasks:
            raise RuntimeError("principal_fill: 无任务数据，请先完成计划导入")

        rows = ctx.project.get("principal_rows") or []
        edits = {as_str(r.get("id")): r for r in rows if isinstance(r, dict)}
        updated = 0
        for t in tasks:
            r = edits.get(as_str(t.get("id")))
            if not r:
                continue
            principal = as_str(r.get("principal"))
            org = as_str(r.get("principal_org"))
            if principal or org:
                t["principal"] = principal
                t["principal_org"] = org
                updated += 1
        st["tasks"] = tasks
        st["principal_updated_at"] = iso_now()
        save_tasks_state(state_path, st)

        # 落地《责任人信息表.xlsx》：行来自真实任务，责任人/责任主体取已填真实值
        out = get_output_dir(ctx.project) / "责任人信息表.xlsx"
        generate_principal_table(tasks, str(out))
        emit(
            f"[principal_fill] ✓ 已保存 {updated} 条责任人信息，"
            f"生成《责任人信息表》（{len(tasks)} 条）"
        )

        artifacts = [output_rel(ctx.work_root, out)] if out.exists() else []
        metrics = {"principal_updated": updated}
        metrics.update(refresh_task_metrics(ctx))
        return {"artifacts": artifacts, "metrics": metrics}
