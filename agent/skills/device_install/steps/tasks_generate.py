"""
tasks_generate · 生成设备安装实施计划（在线展示并编辑）

command: build 专属

主建设流水线第 2 个业务节点（生成责任人信息表之后）：
  以责任人信息表合并后的全量任务为基础，结合《设备位置表》《到货信息表》生成
  **自包含**《设备安装实施计划.xlsx》（Sheet1 实施计划 + Sheet2 SN扫码表），同时落
  sn_pool.json 供后续 SN 扫码表生成。
  HITL EditableTable：在大盘内在线复核 / 微调「计划开始 / 计划完成 / 责任人 / 责任主体」。
提交 → apply_resume_payload 写 project["tasks_rows"] + tasks_confirmed=True → run 落盘重生成。
放行条件：project 已带 tasks_confirmed。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import (
    tasks_state_path,
    refresh_task_metrics,
    find_position_table,
    find_arrival_table,
)
from ..path_config import get_output_dir, output_rel
from ..services._common import as_str, principal_display_name
from ..services.edit_fill import fill_tasks_rows
from ..services.dispatch_plan_parser import DISPATCH_PLAN_FILENAME, save_sn_pool
from ..services.plan_parser import _compute_sla
from ..services.sn_builder import build_sn_rows_for_plan
from ..services.table_builder import generate_dispatch_plan_with_sn_xlsx
from ..services.task_store import load_tasks_state, save_tasks_state, get_tasks, iso_now

_COLUMNS = [
    {"key": "unit", "label": "管理单元", "width": 108},
    {"key": "activity_name", "label": "活动名称", "width": 150, "nowrap": True},
    {"key": "start_date", "label": "计划开始", "editable": True, "type": "date", "width": 134},
    {"key": "end_date", "label": "计划完成", "editable": True, "type": "date", "width": 134},
    {"key": "sla", "label": "SLA", "width": 52},
    {"key": "principal", "label": "责任人", "editable": True, "type": "text", "width": 80},
    {"key": "principal_org", "label": "责任主体", "editable": True, "type": "text", "width": 72},
    {"key": "devices", "label": "设备型号&数量", "width": 150},
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
            "sla": as_str(t.get("sla")),
            "principal": principal_display_name(t.get("principal") or t.get("owner")),
            "principal_org": as_str(t.get("principal_org")),
            "devices": as_str(t.get("devices")),
        }
        for t in tasks
    ]


def _build_plan_file(tasks: list[dict], ctx: SkillContext) -> tuple[str | None, list[dict]]:
    """生成自包含双 Sheet《设备安装实施计划.xlsx》，返回 (artifact_rel, sn_rows)。"""
    position_path = find_position_table(ctx) or ""
    arrival_path = find_arrival_table(ctx) or ""
    out = get_output_dir(ctx.project) / DISPATCH_PLAN_FILENAME
    generate_dispatch_plan_with_sn_xlsx(tasks, position_path, arrival_path, str(out))
    sn_rows = build_sn_rows_for_plan(position_path, arrival_path, tasks)
    rel = output_rel(ctx.work_root, out) if out.exists() else None
    return rel, sn_rows


class TasksGenerateStep(BaseStep):
    key = "tasks_generate"
    name = "生成设备安装实施计划"
    artifacts_pattern = [f"ProjectData/Output/{DISPATCH_PLAN_FILENAME}"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if ctx.project.get("tasks_confirmed"):
            return {"ok": True, "missing": []}

        tasks = get_tasks(str(tasks_state_path(ctx)))
        if not tasks:
            return {
                "ok": False,
                "missing": ["ProjectData/Input/交付计划表.xlsx"],
                "note": "请先完成「生成责任人信息表」。",
            }
        rows = _rows_from_tasks(tasks)
        plan_rel, _sn = self._safe_build(tasks, ctx)
        return {
            "ok": False,
            "missing": [],
            "need_edit": {
                "card_title": "生成设备安装实施计划",
                "title": "设备安装实施计划",
                "subtitle": (
                    f"共 {len(tasks)} 条安装任务，可在线微调「计划开始 / 计划完成 / 责任人」，"
                    "确认后生成自包含《设备安装实施计划》（含 SN 扫码表）并进入计划下发。"
                ),
                "columns": _COLUMNS,
                "rows": rows,
                "fillLabel": "一键同步",
                "fillRows": fill_tasks_rows(rows),
                "rowKey": "id",
                "submitLabel": "确认并生成",
                "filterKeys": ["unit", "activity_name"],
                "result_artifacts": [plan_rel] if plan_rel else [],
            },
            "note": "请复核实施计划，必要时在线微调计划日期后提交确认。",
        }

    @staticmethod
    def _safe_build(tasks: list[dict], ctx: SkillContext) -> tuple[str | None, list[dict]]:
        try:
            return _build_plan_file(tasks, ctx)
        except Exception:  # noqa: BLE001 — 预览生成失败不应阻断编辑界面
            return None, []

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        tasks = [t for t in st.get("tasks", []) if isinstance(t, dict)]
        if not tasks:
            raise RuntimeError("tasks_generate: 无任务数据，请先完成「生成责任人信息表」")

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
            # 日期改动后重算 SLA
            new_sla = _compute_sla(as_str(t.get("start_date")), as_str(t.get("end_date")))
            if new_sla:
                t["sla"] = new_sla
            changed += 1
        if changed:
            st["tasks"] = tasks
            st["tasks_edited_at"] = iso_now()
            save_tasks_state(state_path, st)

        plan_rel, sn_rows = _build_plan_file(tasks, ctx)
        # 落 SN 全量池，供「计划下发」勾选后按管理单元/计划行ID 过滤生成 SN 扫码表
        out = get_output_dir(ctx.project) / DISPATCH_PLAN_FILENAME
        save_sn_pool(ctx.runtime_dir / "sn_pool.json", source=str(out), rows=sn_rows)
        emit(
            f"[tasks_generate] ✓ 已生成《设备安装实施计划》共 {len(tasks)} 条"
            f"（在线微调 {changed} 条），SN 全量池 {len(sn_rows)} 台设备"
        )

        artifacts = [plan_rel] if plan_rel else []
        metrics = {"plan_rows": len(tasks), "sn_pool_devices": len(sn_rows)}
        metrics.update(refresh_task_metrics(ctx))
        return {"artifacts": artifacts, "metrics": metrics}
