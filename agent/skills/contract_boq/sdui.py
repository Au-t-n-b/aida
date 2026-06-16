"""contract_boq · SDUI 投影（最小实现）。"""
from __future__ import annotations

from typing import Any

from agent.sdui.builder import SduiDocument, SduiStackNode, dump_sdui_json
from agent.sdui.projector_base import (
    build_artifacts,
    build_header,
    build_metrics_card,
    build_stepper,
    build_summary_card,
    build_hitl,
    collect_metrics,
)

STEP_NAMES = {
    "preflight": "环境预检",
    "boq_input_check": "BOQ 输入检查",
    "stage1_parse": "Stage1 解析",
    "stage2_device_table": "建模仿真设备表",
    "publish_outputs": "登记产物",
}
STEP_ORDER = list(STEP_NAMES.keys())

CTA = {
    "idle": ("开始 BOQ 解析", "primary", "/start_contract_boq"),
    "paused": ("继续", "primary", "/resume_contract_boq"),
    "done": ("查看产物", "primary", "/view_contract_boq"),
    "failed": ("重试", "primary", "/retry_contract_boq"),
}


def _kpi_items(state: dict[str, Any]):
    m = collect_metrics(state)
    items = []
    if "boq_count" in m:
        from agent.sdui.builder import SduiStatisticRowItem
        items.append(SduiStatisticRowItem(title="BOQ 文件", value=str(m["boq_count"])))
    if "normalized_count" in m:
        from agent.sdui.builder import SduiStatisticRowItem
        items.append(SduiStatisticRowItem(title="normalized", value=str(m["normalized_count"])))
    return items


def project(state: dict[str, Any]) -> dict[str, Any]:
    nodes = [build_header(state, default_name="合同 BOQ 解析", cta_map=CTA, step_order=STEP_ORDER)]
    hitl = build_hitl(state)
    if hitl:
        nodes.append(hitl)
    nodes.append(build_stepper(state, step_names=STEP_NAMES))
    mc = build_metrics_card(state, step_order=STEP_ORDER, kpi_items=_kpi_items(state))
    if mc:
        nodes.append(mc)
    art = build_artifacts(state, input_file_keys=("boq_inputs",))
    if art:
        nodes.append(art)
    summary = build_summary_card([], state)
    if summary:
        nodes.append(summary)
    doc = SduiDocument(
        root=SduiStackNode(id="contract-boq-root", gap="sm", children=nodes),
        meta={"skill": "contract_boq", "run_id": state.get("run_id", "")},
    )
    return dump_sdui_json(doc)
