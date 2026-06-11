"""
esn_fill · ESN 信息填写（在线编辑）

command: build 专属

HITL EditableTable：在大盘内逐台在线填写 ESN（设备身份信息只读，仅 ESN 可编辑）。
提交 → apply_resume_payload 写 project["esn_rows"] → check_inputs 校验完整 + 唯一：
  · 不通过（缺填 / 重复）→ 再次呈现编辑表并提示；
  · 通过 → 放行；run 合并 ESN → 标记已下发任务「已完成」→ 生成《完工清单》+《完工报告》。
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import tasks_state_path, refresh_task_metrics
from ..services._common import as_str
from ..services.sn_builder import validate_esn
from ..services.completion_builder import generate_completion_checklist, generate_completion_report
from ..services.edit_fill import fill_esn_rows
from ..services.task_store import load_tasks_state, save_tasks_state, iso_now
_COLUMNS = [
    {"key": "所属机房", "label": "机房", "width": 100},
    {"key": "设备大类", "label": "设备大类", "width": 90},
    {"key": "设备型号", "label": "设备型号", "width": 150},
    {"key": "设备名称", "label": "设备名称", "width": 160},
    {"key": "所属机柜", "label": "机柜", "width": 70},
    {"key": "安装起始U位", "label": "U位", "width": 60},
    {"key": "ESN", "label": "ESN", "editable": True, "type": "text", "placeholder": "扫码 / 填写 ESN"},
]


def _load_sn_tables(ctx: SkillContext) -> list[dict]:
    p = ctx.runtime_dir / "sn_tables.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    tables = data.get("tables") if isinstance(data, dict) else data
    return [t for t in (tables or []) if isinstance(t, dict)]


def _fresh_rows(tables: list[dict]) -> list[dict]:
    """把 sn_tables 展平为可编辑行（每行携带稳定 id = "<table_id>#<idx>"）。"""
    out: list[dict] = []
    for tbl in tables:
        for ri, row in enumerate(tbl.get("rows", [])):
            out.append({
                "id": f"{as_str(tbl.get('id'))}#{ri}",
                "所属机房": as_str(row.get("所属机房")),
                "设备大类": as_str(row.get("设备大类")),
                "设备型号": as_str(row.get("设备型号")),
                "设备名称": as_str(row.get("设备名称")),
                "所属机柜": as_str(row.get("所属机柜")),
                "安装起始U位": as_str(row.get("安装起始U位")),
                "ESN": as_str(row.get("ESN")),
            })
    return out


def _tables_with_filled(tables: list[dict], esn_rows: list[dict]) -> list[dict]:
    """把提交的 ESN 按 id 写回原 sn_tables（保留 厂家 / 设备U高 等列），返回分组表。"""
    esn_map = {as_str(r.get("id")): as_str(r.get("ESN")) for r in esn_rows if isinstance(r, dict)}
    out: list[dict] = []
    for tbl in tables:
        rows: list[dict] = []
        for ri, row in enumerate(tbl.get("rows", [])):
            row = dict(row)
            rid = f"{as_str(tbl.get('id'))}#{ri}"
            if rid in esn_map:
                row["ESN"] = esn_map[rid]
            rows.append(row)
        out.append({
            "id": as_str(tbl.get("id")),
            "room": as_str(tbl.get("room")),
            "device_class": as_str(tbl.get("device_class")),
            "rows": rows,
        })
    return out


class EsnFillStep(BaseStep):
    key = "esn_fill"
    name = "ESN信息填写"
    artifacts_pattern = ["ProjectData/Output/完工清单_*.xlsx", "ProjectData/Output/设备安装完工报告.xlsx"]

    def _need_edit(self, rows: list[dict], n_total: int, note: str = "", ctx: SkillContext | None = None) -> CheckResult:
        subtitle = note or f"共 {n_total} 台设备，请逐台填写 ESN 后提交。"
        return {
            "ok": False,
            "missing": [],
            "need_edit": {
                "card_title": "ESN 信息填写",
                "title": "SN 扫码 · ESN 录入",
                "subtitle": subtitle,
                "columns": _COLUMNS,
                "rows": rows,
                "fillLabel": "一键填写",
                "fillRows": fill_esn_rows(rows),
                "rowKey": "id",
                "submitLabel": "提交 ESN 并完工",
                "requiredKeys": ["ESN"],
                "groupKey": "设备大类",
                "pageSize": 10,
            },
            "note": note or "请在大盘内逐台在线填写 ESN 后提交。",
        }

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        tables = _load_sn_tables(ctx)
        n_total = sum(len(t.get("rows", [])) for t in tables)
        if n_total == 0:
            return {"ok": True, "missing": []}  # 无设备需录 ESN

        submitted = ctx.project.get("esn_rows")
        if submitted is None:
            return self._need_edit(_fresh_rows(tables), n_total, ctx=ctx)

        filled = _tables_with_filled(tables, submitted)
        missing, dup = validate_esn(filled)
        if missing or dup:
            parts: list[str] = []
            if missing:
                parts.append(f"{len(missing)} 台未填写")
            if dup:
                parts.append(f"{len(dup)} 个 ESN 重复")
            note = "ESN 校验未通过（" + "、".join(parts) + "）。请修正后重新提交。"
            return self._need_edit(list(submitted), n_total, note=note, ctx=ctx)
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        tables_meta = _load_sn_tables(ctx)
        if sum(len(t.get("rows", [])) for t in tables_meta) == 0:
            emit("[esn_fill] 无需录入 ESN（未生成 SN 扫码表分组），跳过")
            metrics = {"esn_devices": 0, "esn_tables": 0, "completed_now": 0}
            metrics.update(refresh_task_metrics(ctx))
            return {"metrics": metrics}

        esn_rows = ctx.project.get("esn_rows") or []
        tables = _tables_with_filled(tables_meta, esn_rows)
        n_devices = sum(len(t.get("rows", [])) for t in tables)
        emit(f"[esn_fill] ✓ ESN 校验通过：{len(tables)} 组 / {n_devices} 台设备")

        # 标记已下发任务为已完成（任务级：按「关联计划行ID」核对设备是否齐备填写）
        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        tasks = [t for t in st.get("tasks", []) if isinstance(t, dict)]

        # 收集每条计划行ID 关联的设备 ESN 填写情况（来自本次 SN 表，已含 ESN）
        filled_by_plan: dict[str, list[bool]] = {}
        for tbl in tables:
            for row in tbl.get("rows", []):
                has_esn = bool(as_str(row.get("ESN")))
                for pid in as_str(row.get("关联计划行ID")).split(";"):
                    pid = pid.strip()
                    if pid:
                        filled_by_plan.setdefault(pid, []).append(has_esn)

        done = 0
        skipped: list[str] = []
        for t in tasks:
            if t.get("status") not in ("已下发", "进行中"):
                continue
            pid = as_str(t.get("plan_row_id")) or as_str(t.get("id"))
            linked = filled_by_plan.get(pid)
            # 有对应设备但未全部填写 ESN → 不标完成（任务级对齐，避免空完工）；
            # 无对应设备（线缆/测试类，或未匹配到物理设备）→ 随 ESN 阶段照常完工。
            if linked is not None and not all(linked):
                skipped.append(pid)
                continue
            t["status"] = "已完成"
            t["progress_pct"] = 100
            t.setdefault("progress_records", []).append({"ts": iso_now(), "status": "已完成"})
            done += 1
        if skipped:
            emit(f"[esn_fill] {len(skipped)} 条任务对应设备 ESN 未填写完整，暂不标记完成")
        st["tasks"] = tasks
        st["esn_collected_at"] = iso_now()
        save_tasks_state(state_path, st)

        # 完工清单（按机房+设备大类）+ 完工报告（全项目汇总）
        artifacts: list[str] = []
        for tbl in tables:
            cl = generate_completion_checklist(tbl, str(ctx.output_dir))
            if cl and os.path.isfile(cl):
                artifacts.append(ctx.rel(cl))
        rep = generate_completion_report(tables, str(ctx.output_dir))
        if rep and os.path.isfile(rep):
            artifacts.append(ctx.rel(rep))
        emit(f"[esn_fill] ✓ 已生成完工清单 {len(tables)} 份 + 完工报告，标记 {done} 条任务完成")

        metrics = {"esn_devices": n_devices, "esn_tables": len(tables), "completed_now": done}
        metrics.update(refresh_task_metrics(ctx))
        return {"artifacts": artifacts, "metrics": metrics}
