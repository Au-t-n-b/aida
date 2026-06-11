"""
task_dispatch · 计划下发

command: build 专属

run：按用户勾选的实施计划条目下发，更新《设备安装实施计划.xlsx》（仅计划 Sheet），
     将选中且「待下发」的任务标记为「已下发」。
HITL EditableTable（勾选型）：
  展示接收到的实施计划明细，checkKey=selected；
  提交 → apply_resume_payload 写 dispatch_rows + dispatch_confirmed → run 仅下发已勾选项。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import tasks_state_path, refresh_task_metrics
from ..services._common import as_str
from ..services.dispatch_plan_parser import (
    DISPATCH_PLAN_FILENAME,
    resolve_dispatch_plan_path,
    parse_dispatch_plan_with_sn,
    save_sn_pool,
)
from ..services.table_builder import generate_dispatch_plan_xlsx
from ..services.task_store import load_tasks_state, save_tasks_state, get_tasks, iso_now
from ..services.edit_fill import fill_dispatch_select_all

_DISPATCH_COLUMNS = [
    {"key": "unit", "label": "管理单元", "width": 110},
    {"key": "activity_id", "label": "活动ID", "width": 80},
    {"key": "activity_name", "label": "活动名称", "width": 200},
    {"key": "start_date", "label": "计划开始", "width": 100},
    {"key": "end_date", "label": "计划完成", "width": 100},
    {"key": "sla", "label": "SLA", "width": 60},
    {"key": "principal", "label": "责任人", "width": 90},
    {"key": "principal_org", "label": "责任主体", "width": 100},
    {"key": "devices", "label": "设备型号&数量", "width": 180},
    {"key": "status", "label": "状态", "width": 70},
]


def _row_from_task(t: dict, *, selected: bool = True) -> dict:
    return {
        "id": as_str(t.get("id")),
        "unit": as_str(t.get("unit")),
        "activity_id": as_str(t.get("activity_id")),
        "activity_name": as_str(t.get("activity_name")),
        "start_date": as_str(t.get("start_date")),
        "end_date": as_str(t.get("end_date")),
        "sla": as_str(t.get("sla")),
        "principal": as_str(t.get("principal") or t.get("owner")),
        "principal_org": as_str(t.get("principal_org")),
        "devices": as_str(t.get("devices")),
        "status": as_str(t.get("status", "待下发")),
        "selected": selected,
    }


def _dispatch_rows(tasks: list[dict], project: dict) -> list[dict]:
    pending = [t for t in tasks if t.get("status") == "待下发"]
    prior = {
        as_str(r.get("id")): r
        for r in (project.get("dispatch_rows") or [])
        if isinstance(r, dict)
    }
    rows: list[dict] = []
    for t in pending:
        tid = as_str(t.get("id"))
        if tid in prior:
            rows.append(_row_from_task(t, selected=_is_selected(prior[tid])))
        else:
            rows.append(_row_from_task(t, selected=True))
    return rows


def _is_selected(row: dict) -> bool:
    v = row.get("selected")
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes", "on")
    return bool(v)


def _selected_ids(project: dict) -> set[str]:
    return {
        as_str(r.get("id"))
        for r in (project.get("dispatch_rows") or [])
        if isinstance(r, dict) and _is_selected(r) and as_str(r.get("id"))
    }


def _selected_activity_keys(project: dict) -> set[str]:
    keys: set[str] = set()
    for r in project.get("dispatch_rows") or []:
        if not isinstance(r, dict) or not _is_selected(r):
            continue
        unit = as_str(r.get("unit"))
        aid = as_str(r.get("activity_id"))
        if unit and aid:
            keys.add(f"{unit}::{aid}")
    return keys


def _task_matches_selection(t: dict, ids: set[str], act_keys: set[str]) -> bool:
    tid = as_str(t.get("id"))
    if tid and tid in ids:
        return True
    unit = as_str(t.get("unit"))
    aid = as_str(t.get("activity_id"))
    return bool(unit and aid and f"{unit}::{aid}" in act_keys)


def _recover_tasks_from_plan(ctx: SkillContext) -> list[dict]:
    """tasks_state 为空但上游《设备安装实施计划》已在 Input/ → 兜底重解析。

    避免 stale/重放等场景下 tasks_state.json 丢失时，误判为「上游未交付」而弹出
    上传文件 HITL（文件其实已在 Input/），导致右侧出现「请在左侧会话框继续」指引、
    始终看不到下发表格。解析成功即落盘（tasks_state + sn_pool），run/sn_generate 可续。"""
    plan_path = resolve_dispatch_plan_path(ctx.input_dir)
    if not plan_path:
        return []
    try:
        tasks, sn_rows = parse_dispatch_plan_with_sn(plan_path)
    except Exception:  # noqa: BLE001 — 兜底解析失败则回退到原「请接收实施计划」提示
        return []
    if not tasks:
        return []
    save_tasks_state(str(tasks_state_path(ctx)), {
        "loaded_at": iso_now(),
        "source_plan": str(plan_path),
        "tasks": tasks,
    })
    save_sn_pool(ctx.runtime_dir / "sn_pool.json", source=str(plan_path), rows=sn_rows)
    return tasks


def _plan_artifact_rel(ctx: SkillContext) -> str | None:
    """优先展示 Input 中上游交付的合并计划，否则 Output 下发后快照。"""
    inp = ctx.input_dir / DISPATCH_PLAN_FILENAME
    if inp.is_file():
        return ctx.rel(inp)
    out = ctx.output_dir / DISPATCH_PLAN_FILENAME
    return ctx.rel(out) if out.is_file() else None


class TaskDispatchStep(BaseStep):
    key = "task_dispatch"
    name = "计划下发"
    artifacts_pattern = ["ProjectData/Output/设备安装实施计划.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if ctx.project.get("dispatch_confirmed") and (
            _selected_ids(ctx.project) or _selected_activity_keys(ctx.project)
        ):
            return {"ok": True, "missing": []}

        tasks = get_tasks(str(tasks_state_path(ctx)))
        if not tasks:
            tasks = _recover_tasks_from_plan(ctx)  # tasks_state 为空 → 从 Input/ 计划兜底解析
        if not tasks:
            return {
                "ok": False,
                "missing": [f"ProjectData/Input/{DISPATCH_PLAN_FILENAME}"],
                "note": "请先由上游交付实施计划并完成「接收实施计划」。",
            }

        pending = [t for t in tasks if t.get("status") == "待下发"]
        rows = _dispatch_rows(tasks, ctx.project)
        n = len(rows)
        plan_rel = _plan_artifact_rel(ctx)

        if not rows:
            return {
                "ok": False,
                "missing": [],
                "need_edit": {
                    "card_title": "计划下发",
                    "title": "设备安装实施计划",
                    "subtitle": (
                        "当前没有可下发的「待下发」任务（可能上一轮已将任务标记为已下发/已完成）。"
                        "请重新启动主建设流程并确保上游已交付新的实施计划。"
                    ),
                    "columns": _DISPATCH_COLUMNS,
                    "rows": [],
                    "rowKey": "id",
                    "checkKey": "selected",
                    "submitLabel": "确认下发",
                },
                "note": "暂无可下发任务，请重新启动主建设流程。",
            }

        return {
            "ok": False,
            "missing": [],
            "need_edit": {
                "card_title": "计划下发",
                "title": "设备安装实施计划",
                "columns": _DISPATCH_COLUMNS,
                "rows": rows,
                "rowKey": "id",
                "checkKey": "selected",
                "submitLabel": "确认下发",
                "fillLabel": "一键全选",
                "fillRows": fill_dispatch_select_all(rows),
                "result_artifacts": [plan_rel] if plan_rel else [],
            },
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        selected_ids = _selected_ids(ctx.project)
        act_keys = _selected_activity_keys(ctx.project)
        if not selected_ids and not act_keys:
            raise RuntimeError("task_dispatch: 请至少勾选一条实施计划后再下发")

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        tasks = [t for t in st.get("tasks", []) if isinstance(t, dict)]

        out = ctx.output_dir / DISPATCH_PLAN_FILENAME
        generate_dispatch_plan_xlsx(tasks, str(out))

        dispatched = 0
        already = 0
        for t in tasks:
            if not _task_matches_selection(t, selected_ids, act_keys):
                continue
            if t.get("status") == "待下发":
                t["status"] = "已下发"
                dispatched += 1
            elif t.get("status") == "已下发":
                already += 1
        if dispatched == 0 and already == 0:
            raise RuntimeError(
                "task_dispatch: 勾选的条目均非「待下发」状态。"
                "请重新启动主建设流程并接收新的实施计划。"
            )

        selected_tasks = [
            t for t in tasks if _task_matches_selection(t, selected_ids, act_keys)
        ]
        st["tasks"] = tasks
        st["dispatched_at"] = iso_now()
        st["last_dispatch_tasks"] = [
            {
                "id": as_str(t.get("id")),
                "unit": as_str(t.get("unit")),
                "activity_id": as_str(t.get("activity_id")),
                "activity_name": as_str(t.get("activity_name")),
                "devices": as_str(t.get("devices")),
            }
            for t in selected_tasks
        ]
        save_tasks_state(state_path, st)

        sn_meta = ctx.runtime_dir / "sn_tables.json"
        if sn_meta.exists():
            sn_meta.unlink()

        n_sel = max(len(selected_ids), len(act_keys))
        if dispatched:
            emit(f"[task_dispatch] ✓ 已下发 {dispatched} 条计划（勾选 {n_sel} 条）")
        else:
            emit(f"[task_dispatch] ✓ 勾选 {n_sel} 条计划此前已下发（重放幂等）")

        artifacts = [ctx.rel(out)] if out.exists() else []
        metrics = {"dispatched_count": dispatched}
        metrics.update(refresh_task_metrics(ctx))
        return {"artifacts": artifacts, "metrics": metrics}
