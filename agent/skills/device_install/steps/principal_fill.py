"""
principal_fill · 生成责任人信息表（在线展示并编辑）

command: build 专属

主建设流水线第 1 个业务节点（环境预检之后）：
  入口解析《交付计划表》→ 按「活动」去重生成责任矩阵；责任人/责任主体**默认留空**，
  由用户手动填写，或点「一键同步」按交付计划表自动带出（责任人取 PRINCIPAL，责任主体默认华为）。
  作业结果区展示《责任人信息表模板》（未填写责任人/责任主体的空模板）。
提交 → apply_resume_payload 写 project["principal_rows"] → run 按活动回填全量任务并落
《责任人信息表.xlsx》（已填写）。放行条件：project 已带 principal_rows（即已提交一次）。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import tasks_state_path, refresh_task_metrics, load_or_parse_delivery_tasks
from .. import dc_io, dc_paths
from ..services._common import as_str, principal_display_name
from ..services.table_builder import generate_principal_table_by_activity
from ..services.task_store import load_tasks_state, save_tasks_state, iso_now

_COLUMNS = [
    {"key": "activity_id", "label": "活动ID", "width": 72},
    {"key": "activity_name", "label": "活动名称", "width": 220, "paddingLeft": 100},
    {"key": "principal", "label": "责任人", "editable": True, "type": "text", "width": 100, "placeholder": "责任人姓名"},
    {"key": "principal_org", "label": "责任主体", "editable": True, "type": "text", "width": 120, "placeholder": "华为/分包商"},
]


def _activity_id_sort_key(aid: str) -> tuple:
    """活动 ID 按段数值排序（如 7.10 < 7.15 < 7.20）。"""
    parts: list[tuple[int, float | str]] = []
    for seg in as_str(aid).split("."):
        if not seg:
            continue
        try:
            parts.append((0, float(seg)))
        except ValueError:
            parts.append((1, seg))
    return tuple(parts)


def _rows_by_activity(tasks: list[dict], *, filled: bool) -> list[dict]:
    """按「活动」去重，每活动一行。

    filled=False：责任人/责任主体留空（界面默认 + 模板内容）。
    filled=True ：责任人取交付计划表 PRINCIPAL、责任主体取来源（多为华为）——供「一键同步」。
    """
    first_by_act: dict[str, dict] = {}
    for t in tasks:
        aid = as_str(t.get("activity_id"))
        if not aid:
            continue
        if aid not in first_by_act:
            first_by_act[aid] = t

    rows: list[dict] = []
    for aid in sorted(first_by_act.keys(), key=_activity_id_sort_key):
        t = first_by_act[aid]
        rows.append({
            "id": aid,  # rowKey = 活动ID
            "activity_id": aid,
            "activity_name": as_str(t.get("activity_name")),
            "principal": principal_display_name(t.get("principal") or t.get("owner")) if filled else "",
            "principal_org": (as_str(t.get("principal_org")) or "华为") if filled else "",
        })
    return rows


def _write_principal_table(rows: list[dict], ctx: SkillContext, filename: str) -> str | None:
    out = dc_io.output_dir(ctx) / filename
    generate_principal_table_by_activity(rows, str(out))
    if not out.exists():
        return None
    # 模板仅预览（scratch 内可解析），正式责任人信息表上传数据中心
    if "模板" in filename:
        return dc_paths.artifact_key(filename)
    return dc_io.publish_output(ctx, out, display_name=filename)


class PrincipalFillStep(BaseStep):
    key = "principal_fill"
    name = "指派责任人"
    artifacts_pattern = [dc_paths.artifact_key("责任人信息表.xlsx")]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        # 已提交一次 → 放行（run 落盘）
        if ctx.project.get("principal_rows") is not None:
            return {"ok": True, "missing": []}

        try:
            tasks = load_or_parse_delivery_tasks(ctx)
        except RuntimeError as e:
            return {"ok": False, "missing": [], "note": str(e)}
        if not tasks:
            loc = dc_paths.delivery_plan_loc()
            return {
                "ok": False,
                "missing": [],
                "note": f"未从《交付计划表》解析到安装任务，请检查 {loc.describe()} 内文件格式。",
            }

        rows = _rows_by_activity(tasks, filled=False)
        fill_rows = _rows_by_activity(tasks, filled=True)
        # 作业结果：未填写责任人/责任主体的《责任人信息表模板》
        tpl_rel = _write_principal_table(rows, ctx, "责任人信息表模板.xlsx")
        return {
            "ok": False,
            "missing": [],
            "need_edit": {
                "title": "责任矩阵",
                "subtitle": (
                    f"已从《交付计划表》解析出 {len(rows)} 个安装活动。"
                    "请在线填写「责任人 / 责任主体（华为/分包商）」。"
                ),
                "subtitleTone": "warning",
                "columns": _COLUMNS,
                "rows": rows,
                "fillLabel": "一键同步",
                "fillRows": fill_rows,
                "rowKey": "id",
                "submitLabel": "保存并继续",
                "requiredKeys": ["principal", "principal_org"],
                "result_artifacts": [tpl_rel] if tpl_rel else [],
            },
            "note": "请在大盘内填写责任人信息后提交（支持一键同步）。",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        tasks = [t for t in st.get("tasks", []) if isinstance(t, dict)]
        if not tasks:
            raise RuntimeError("principal_fill: 无任务数据，请先解析《交付计划表》")

        rows = ctx.project.get("principal_rows") or []
        # 按活动ID 索引编辑结果
        edits = {as_str(r.get("activity_id") or r.get("id")): r for r in rows if isinstance(r, dict)}
        updated = 0
        for t in tasks:
            r = edits.get(as_str(t.get("activity_id")))
            if not r:
                continue
            principal = as_str(r.get("principal"))
            org = as_str(r.get("principal_org"))
            if principal:
                t["principal"] = principal
            t["principal_org"] = org
            updated += 1
        st["tasks"] = tasks
        st["principal_updated_at"] = iso_now()
        save_tasks_state(state_path, st)

        out_rows = _rows_by_activity(tasks, filled=True)
        plan_rel = _write_principal_table(out_rows, ctx, "责任人信息表.xlsx")
        emit(
            f"[principal_fill] ✓ 已保存责任人信息（{len(out_rows)} 个活动），"
            f"回填 {updated} 条任务并生成《责任人信息表》"
        )

        artifacts = [plan_rel] if plan_rel else []
        metrics = {"principal_activities": len(out_rows)}
        metrics.update(refresh_task_metrics(ctx))
        return {"artifacts": artifacts, "metrics": metrics}
