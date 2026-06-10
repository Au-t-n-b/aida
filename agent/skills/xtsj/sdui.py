"""
xtsj SDUI 投影器 · SkillState → SduiDocument（纯函数 · 无副作用）

dispatch 模式特点：每次 run 只跑一条命令，投影器按 project["command"] 切换视图：
  - input_check → 输入件状态 PlaneMatrix + 缺件摘要
  - （后续命令在此添加对应的 if 分支）

通用段（header / 日志 / 产物）走 projector_base；平面矩阵是 xtsj 自有节点。
"""
from __future__ import annotations

from typing import Any

from agent.sdui.builder import (
    SduiDocument, SduiNode, SduiStackNode, SduiCardNode,
    SduiTextNode, SduiPlaneMatrixNode, SduiPlaneCell,
    SduiStatisticRowItem, SduiStatisticRowNode,
    dump_sdui_json,
)
from agent.sdui.projector_base import (
    collect_metrics,
    build_header, build_artifacts, build_summary_card,
)

XTSJ_CTA: dict[str, tuple[str, str, str]] = {
    "idle":   ("检查输入件", "primary", "/start_xtsj"),
    "done":   ("查看产物",   "primary", "/view_report"),
    "failed": ("重试",       "primary", "/retry_xtsj"),
}

# ── per-command 视图 ─────────────────────────────────────────────────────────

def _build_input_check_view(state: dict[str, Any]) -> list[SduiNode]:
    """input_check 命令：输入件矩阵 + KPI + 摘要。"""
    m = collect_metrics(state)
    found_tags: list[str] = m.get("found_tags", [])
    missing: list[str]    = m.get("missing_labels", [])
    total = m.get("input_found", 0) + m.get("input_missing", 0)

    # PlaneMatrix：已找到的 ✓ done，缺失的 ○ pending
    from agent.skills.xtsj.pipelines.input_check import FILE_CONFIG
    cells: list[SduiPlaneCell] = []
    for tag, cfg in FILE_CONFIG.items():
        status = "done" if tag in found_tags else "pending"
        group = "必需件"
        cells.append(SduiPlaneCell(label=cfg["label"], status=status, group=group))

    nodes: list[SduiNode] = []

    if cells:
        nodes.append(SduiPlaneMatrixNode(
            id="input-matrix",
            cells=cells,
            columns=3,
        ))

    # 缺件说明卡
    if missing:
        missing_text = "、".join(missing)
        nodes.append(SduiCardNode(
            id="missing-hint",
            title="缺少必需输入件",
            tone="warning",
            children=[SduiTextNode(
                id="missing-text",
                content=f"以下文件未在工作区发现，请放入 ProjectData/Input 后重试：{missing_text}",
            )],
        ))
    elif total > 0:
        nodes.append(SduiCardNode(
            id="ready-hint",
            title="输入件齐备",
            tone="success",
            children=[SduiTextNode(
                id="ready-text",
                content=f"全部 {total} 个必需输入件已就绪，可执行地址规划 / 互联 / LLD 等命令。",
            )],
        ))

    return nodes


def _build_address_plan_view(state: dict[str, Any]) -> list[SduiNode]:
    """address_plan 命令：各平面 PlaneMatrix + KPI + 摘要。"""
    from agent.skills.xtsj.pipelines.address_plan import PLANE_SPECS

    m = collect_metrics(state)
    plane_statuses: dict[str, str] = m.get("plane_statuses", {})
    plane_notes: dict[str, str]    = m.get("plane_notes", {})
    done  = m.get("address_plan_done",    0)
    total = m.get("address_plan_total",   len(PLANE_SPECS))
    err   = m.get("address_plan_error",   0)
    summary_text = m.get("address_plan_summary", "")

    # 按分组 + 状态构建 PlaneMatrix cells
    cells: list[SduiPlaneCell] = []
    for spec in PLANE_SPECS:
        st = plane_statuses.get(spec.key, "pending")
        note = plane_notes.get(spec.key, "")
        cells.append(SduiPlaneCell(
            label=spec.label,
            status=st,
            group=spec.group,
            note=note or None,
        ))

    nodes: list[SduiNode] = []

    # KPI 行
    if total > 0:
        kpi_items = [
            SduiStatisticRowItem(title="待规划", value=str(total), color="subtle"),
            SduiStatisticRowItem(title="已完成", value=str(done),
                                  color="accent" if done > 0 else "subtle"),
        ]
        if err > 0:
            kpi_items.append(SduiStatisticRowItem(title="出错", value=str(err), color="error"))
        nodes.append(SduiStatisticRowNode(id="address-kpi", items=kpi_items))

    if cells:
        nodes.append(SduiPlaneMatrixNode(
            id="address-plane-matrix",
            cells=cells,
            columns=2,
        ))

    if summary_text:
        tone: str = "success" if err == 0 and done > 0 else ("warning" if err > 0 else "default")
        nodes.append(SduiCardNode(
            id="address-summary",
            title="规划摘要",
            tone=tone,          # type: ignore[arg-type]
            children=[SduiTextNode(id="address-summary-text", content=summary_text)],
        ))

    return nodes


# ── 主入口 ────────────────────────────────────────────────────────────────────

def project(state: dict[str, Any]) -> dict[str, Any]:
    """SkillState → SduiDocument JSON-compatible dict。"""
    command = str((state.get("project") or {}).get("command") or "input_check")

    nodes: list[SduiNode] = [
        build_header(state, default_name="系统设计", cta_map=XTSJ_CTA),
    ]

    # 按命令切换内容区
    if command == "input_check":
        nodes.extend(_build_input_check_view(state))
    elif command == "address_plan":
        nodes.extend(_build_address_plan_view(state))

    artifacts_node = build_artifacts(state)
    if artifacts_node:
        nodes.append(artifacts_node)

    summary = build_summary_card([], state)
    if summary:
        nodes.append(summary)

    doc = SduiDocument(
        root=SduiStackNode(id="xtsj-root", gap="sm", children=nodes),
        meta={"skill": "xtsj", "run_id": state.get("run_id", ""), "command": command},
    )
    return dump_sdui_json(doc)
