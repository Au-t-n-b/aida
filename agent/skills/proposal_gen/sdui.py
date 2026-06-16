"""proposal_gen · SDUI 投影（最小实现）。"""
from __future__ import annotations

from typing import Any

from agent.sdui.builder import SduiDocument, SduiStackNode, SduiStatisticRowItem, dump_sdui_json
from agent.sdui.projector_base import (
    build_artifacts,
    build_header,
    build_hitl,
    build_metrics_card,
    build_stepper,
    build_summary_card,
    collect_metrics,
)

STEP_NAMES = {
    "preflight": "环境预检",
    "ingest_contract": "接入合同解析",
    "parse_tech_proposal": "验收策略提取",
    "parse_testcases": "测试用例提取",
    "assemble_device_table": "设备信息表",
    "assemble_service_maint": "服务维保",
    "table_gen_release": "落盘发布",
}
STEP_ORDER = list(STEP_NAMES.keys())

CTA = {
    "idle": ("生成交付预案", "primary", "/start_proposal_gen"),
    "paused": ("继续", "primary", "/resume_proposal_gen"),
    "done": ("查看预案", "primary", "/view_proposal"),
    "failed": ("重试", "primary", "/retry_proposal_gen"),
}


def _kpi_items(state: dict[str, Any]):
    m = collect_metrics(state)
    items: list[SduiStatisticRowItem] = []
    if "normalized_count" in m:
        items.append(SduiStatisticRowItem(title="BOQ 解析", value=str(m["normalized_count"])))
    if "device_rows" in m:
        items.append(SduiStatisticRowItem(title="设备行", value=str(m["device_rows"])))
    if "acceptance_rows" in m:
        items.append(SduiStatisticRowItem(title="验收项", value=str(m["acceptance_rows"])))
    return items


def project(state: dict[str, Any]) -> dict[str, Any]:
    nodes = [build_header(state, default_name="交付预案生成", cta_map=CTA, step_order=STEP_ORDER)]
    hitl = build_hitl(state)
    if hitl:
        nodes.append(hitl)
    nodes.append(build_stepper(state, step_names=STEP_NAMES))
    mc = build_metrics_card(state, step_order=STEP_ORDER, kpi_items=_kpi_items(state))
    if mc:
        nodes.append(mc)
    art = build_artifacts(state)
    if art:
        nodes.append(art)
    summary = build_summary_card([], state)
    if summary:
        nodes.append(summary)
    doc = SduiDocument(
        root=SduiStackNode(id="proposal-gen-root", gap="sm", children=nodes),
        meta={"skill": "proposal_gen", "run_id": state.get("run_id", "")},
    )
    return dump_sdui_json(doc)
