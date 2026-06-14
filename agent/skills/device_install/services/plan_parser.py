"""
plan_parser · 解析《交付计划表.xlsx》《任务计划表.xlsx》与《责任人信息表.xlsx》。

- parse_delivery_plan：解析上游《交付计划表》(数据中心导出，英文表头)，提取活动 ID
  以 "7." 开头的三级安装任务（不含 7.0 汇总行）；管理单元含逗号时拆分为多条；
  设备型号&数量取自 RAW_EQUIPMENT_LIST(JSON)；SLA 缺省由计划起止日期推算。
- parse_task_plan：提取活动 ID 以 "7." 开头的三级安装任务（中文表头·历史格式）。
- parse_principal_table：解析责任人信息表，返回 {unit::activity_id / unit::activity_name → {principal, principal_org}}。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from ._common import as_str, col_idx, parse_date_str
from .activity_catalog import canonical_activity_name, third_task_name

# TARGET_AGENT → 环节类型中文标签（用于责任人信息表展示，辅助判断责任主体）
_AGENT_STAGE_LABEL = {
    "installation_agent": "施工安装",
    "deployment_agent":   "部署调测",
    "survey_agent":       "勘测",
    "design_agent":       "设计",
    "simulation_agent":   "仿真",
    "other_assistant":    "其他",
    "manage_agent":       "管理",
}


def stage_label(target_agent: str) -> str:
    return _AGENT_STAGE_LABEL.get(as_str(target_agent), as_str(target_agent))


def _format_devices_from_raw(raw: Any) -> str:
    """RAW_EQUIPMENT_LIST(JSON {"device_list":[{device_model,quantity,unit}]}) → 「型号 数量单位, …」。"""
    s = as_str(raw)
    if not s:
        return ""
    try:
        data = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return ""
    items = data.get("device_list") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return ""
    parts: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        model = as_str(it.get("device_model"))
        if not model:
            continue
        qty = it.get("quantity")
        unit = as_str(it.get("unit"))
        if qty in (None, ""):
            parts.append(model)
        else:
            try:
                qty_s = str(int(qty))
            except (ValueError, TypeError):
                qty_s = as_str(qty)
            parts.append(f"{model} {qty_s}{unit}".strip())
    return ", ".join(parts)


def _compute_sla(start: str, end: str) -> str:
    """由计划起止日期推算 SLA（含首尾，单位：天）；无法解析则空串。"""
    try:
        d0 = datetime.strptime(start, "%Y-%m-%d")
        d1 = datetime.strptime(end, "%Y-%m-%d")
    except (ValueError, TypeError):
        return ""
    days = (d1 - d0).days + 1
    return f"{days}天" if days > 0 else ""


def _split_units(raw_unit: str) -> list[str]:
    """管理单元单元格可能是「B2DH401-POD01,B2DH401-POD02」逗号串 → 拆为多个。"""
    s = as_str(raw_unit)
    if not s:
        return []
    parts = [p.strip() for chunk in s.split(",") for p in chunk.split("，")]
    return [p for p in parts if p]


def parse_delivery_plan(xlsx_path: str) -> list[dict]:
    """解析《交付计划表.xlsx》(英文表头) → 三级安装任务列表（活动 ID 以 "7." 开头，含首列 7.0 汇总行剔除）。

    每条任务为 (管理单元 × 活动) 粒度；管理单元逗号串拆分为多条。
    责任人取 PRINCIPAL，责任主体取 PRINCIPAL_COMPANY（多为「华为」，由用户在线复核可改分包商）。
    设备型号&数量取 RAW_EQUIPMENT_LIST（JSON）；SLA 缺列时由起止日期推算。
    """
    try:
        import openpyxl  # type: ignore
        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception:
        return []

    if not all_rows:
        return []

    header = [as_str(v) for v in all_rows[0]]
    ci_sn    = col_idx(header, "SERIAL_NUMBER", "序列号")
    ci_aid   = col_idx(header, "ACTIVITY_ID", "活动ID", "活动 ID")
    ci_name  = col_idx(header, "ACTIVITY_NAME", "活动名称")
    ci_unit  = col_idx(header, "MANAGEMENT_UNIT", "管理单元")
    ci_unit2 = col_idx(header, "REAL_MANAGEMENT_UNIT")
    ci_owner = col_idx(header, "OWNER")
    ci_start = col_idx(header, "START_DATE", "开始日期", "计划开始")
    ci_end   = col_idx(header, "END_DATE", "结束日期", "计划完成", "计划结束")
    ci_sla   = col_idx(header, "SLA")
    ci_pri   = col_idx(header, "PRINCIPAL", "责任人")
    ci_org   = col_idx(header, "PRINCIPAL_COMPANY", "责任主体")
    ci_raw   = col_idx(header, "RAW_EQUIPMENT_LIST")
    ci_tgt   = col_idx(header, "TARGET_AGENT")

    if ci_aid is None:
        return []

    def _v(row: tuple, idx: int | None) -> Any:
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    tasks: list[dict] = []
    for row in all_rows[1:]:
        aid = as_str(_v(row, ci_aid))
        if not aid.startswith("7."):
            continue
        if is_rollup_activity_id(aid):
            continue

        units = (
            _split_units(as_str(_v(row, ci_unit)))
            or _split_units(as_str(_v(row, ci_unit2)))
            or _split_units(as_str(_v(row, ci_owner)))
            or ["默认"]
        )
        sn    = as_str(_v(row, ci_sn))
        # 活动名称按 activity_id 回查固定映射规范化（有迹可循），回退原表名
        name  = canonical_activity_name(aid, as_str(_v(row, ci_name)))
        start = parse_date_str(_v(row, ci_start))
        end   = parse_date_str(_v(row, ci_end))
        sla   = as_str(_v(row, ci_sla)) or _compute_sla(start, end)
        pri   = as_str(_v(row, ci_pri))
        org   = as_str(_v(row, ci_org))
        devices = _format_devices_from_raw(_v(row, ci_raw))
        tgt   = as_str(_v(row, ci_tgt))

        for unit in units:
            base = f"{aid}:{unit}:{sn or name}"
            tid = sn if (sn and len(units) == 1) else hashlib.sha256(base.encode()).hexdigest()[:10]
            tasks.append({
                "id":            tid,
                "plan_row_id":   f"{unit}::{aid}",
                "activity_id":   aid,
                "unit":          unit,
                "activity_name": name,
                "task_name":     third_task_name(unit, aid, name),
                "start_date":    start,
                "end_date":      end,
                "sla":           sla,
                "dependencies":  "",
                "batch":         "",
                "devices":       devices,
                "target_agent":  tgt,
                "stage_label":   stage_label(tgt),
                "remote_team":   "",
                "local_team":    "",
                "owner":         pri,           # 原始责任人
                "principal":     pri,           # 自动带出（可在线改）
                "principal_org": org,           # 多为「华为」，可改分包商
                "status":        "待下发",
                "progress_records": [],
            })

    return tasks


def is_rollup_activity_id(activity_id: str) -> bool:
    """活动 ID 7.0 为 7.x 的汇总行，不纳入三级安装任务。"""
    aid = as_str(activity_id).replace(" ", "")
    if not aid.startswith("7."):
        return False
    return aid.rstrip("0").rstrip(".") == "7"


def parse_task_plan(xlsx_path: str) -> list[dict]:
    """解析《任务计划表.xlsx》，提取活动 ID 以 "7." 开头的安装任务行（不含 7.0 汇总行）。"""
    try:
        import openpyxl  # type: ignore
        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception:
        return []

    if not all_rows:
        return []

    header = [as_str(v) for v in all_rows[0]]
    ci_sn     = col_idx(header, "序列号")
    ci_aid    = col_idx(header, "活动ID", "级ID", "活动 ID")
    ci_unit   = col_idx(header, "管理单元")
    ci_name   = col_idx(header, "活动名称")
    ci_start  = col_idx(header, "开始日期")
    ci_end    = col_idx(header, "结束日期")
    ci_sla    = col_idx(header, "SLA")
    ci_dep    = col_idx(header, "依赖活动")
    ci_batch  = col_idx(header, "批次")
    ci_dev    = col_idx(header, "设备型号&数量的列表", "设备型号&数量列表", "设备型号")
    ci_remote = col_idx(header, "远程团队")
    ci_local  = col_idx(header, "现场团队", "本地团队")
    ci_owner  = col_idx(header, "责任人")

    if ci_aid is None:
        return []

    def _v(row: tuple, idx: int | None) -> Any:
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    tasks: list[dict] = []
    for row in all_rows[1:]:
        aid = as_str(_v(row, ci_aid))
        if not aid.startswith("7."):
            continue
        if is_rollup_activity_id(aid):
            continue
        sn    = as_str(_v(row, ci_sn))
        unit  = as_str(_v(row, ci_unit)) or "默认"
        name  = as_str(_v(row, ci_name)) or aid
        start = parse_date_str(_v(row, ci_start))
        end   = parse_date_str(_v(row, ci_end))
        tasks.append({
            "id":            sn or hashlib.sha256(f"{aid}:{unit}:{name}".encode()).hexdigest()[:10],
            "activity_id":   aid,
            "unit":          unit,
            "activity_name": name,
            "start_date":    start,
            "end_date":      end,
            "sla":           as_str(_v(row, ci_sla)),
            "dependencies":  as_str(_v(row, ci_dep)),
            "batch":         as_str(_v(row, ci_batch)),
            "devices":       as_str(_v(row, ci_dev)),
            "remote_team":   as_str(_v(row, ci_remote)),
            "local_team":    as_str(_v(row, ci_local)),
            "owner":         as_str(_v(row, ci_owner)),  # 原始责任人（可由责任人信息表覆盖）
            "principal":     "",        # 由责任人信息表填充
            "principal_org": "",        # 由责任人信息表填充
            "status":        "待下发",
            "progress_records": [],
        })

    return tasks


def parse_principal_table(xlsx_path: str) -> dict[str, dict]:
    """解析《责任人信息表.xlsx》。
    返回 {"{unit}::{activity_id}" / "{unit}::{activity_name}" : {principal, principal_org}}。
    """
    try:
        import openpyxl  # type: ignore
        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception:
        return {}

    if not rows:
        return {}

    header = [as_str(v) for v in rows[0]]
    ci_unit  = col_idx(header, "管理单元")
    ci_aid   = col_idx(header, "活动ID")
    ci_name  = col_idx(header, "活动名称")
    ci_owner = col_idx(header, "责任人姓名", "责任人")
    ci_org   = col_idx(header, "责任主体（华为/分包商）", "责任主体")

    result: dict[str, dict] = {}
    for row in rows[1:]:
        def _v(idx: int | None) -> str:
            if idx is None or idx >= len(row):
                return ""
            return as_str(row[idx])

        unit  = _v(ci_unit)
        info  = {"principal": _v(ci_owner), "principal_org": _v(ci_org)}
        aid   = _v(ci_aid)
        aname = _v(ci_name)
        if aid:
            result[f"{unit}::{aid}"] = info
        if aname:
            result[f"{unit}::{aname}"] = info

    return result


def merge_principals(tasks: list[dict], principals: dict[str, dict]) -> int:
    """把责任人信息并入任务列表，返回更新条数。"""
    updated = 0
    for t in tasks:
        unit = as_str(t.get("unit"))
        info = (
            principals.get(f"{unit}::{as_str(t.get('activity_id'))}")
            or principals.get(f"{unit}::{as_str(t.get('activity_name'))}")
        )
        if info and (info.get("principal") or info.get("principal_org")):
            t["principal"] = info.get("principal", "") or t.get("principal", "")
            t["principal_org"] = info.get("principal_org", "") or t.get("principal_org", "")
            updated += 1
    return updated
