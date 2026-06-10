"""
guihua SDUI 投影器 · SkillState → SduiDocument（纯函数 · 无副作用 · 可单测）

v2 改进：
  - Idle 状态：显示流程说明引导卡，而非空白
  - device_confirm HITL：在 ChoiceCard 前展示 BOQ 提取的设备清单（Table）
  - topo_confirm HITL：在 ChoiceCard 前展示已创建设备的类别分布
  - BOQ 提取质量（fallback/filenames）时显示 Alert 警告
  - 摘要 bits 补充提取来源说明

依赖 boq_extract step 在 metrics 写入：
  device_list_preview（list[dict{name,type,qty}]，前 10 项）
  device_list_truncated（bool）
  categories（dict[str,int]）
"""
from __future__ import annotations

from typing import Any

from agent.sdui.builder import (
    SduiDocument, SduiNode, SduiStackNode, SduiCardNode,
    SduiAlertNode, SduiTableNode, SduiDividerNode, SduiTextNode,
    SduiMarkdownNode, SduiStatisticRowItem, dump_sdui_json,
)
from agent.sdui.projector_base import (
    collect_metrics, overall_status,
    build_header, build_stepper, build_metrics_card,
    build_artifacts, build_summary_card, build_hitl,
)

GUIHUA_STEP_NAMES: dict[str, str] = {
    "boq_extract":    "BOQ提取",
    "device_confirm": "设备确认",
    "device_create":  "创建设备",
    "topo_confirm":   "拓扑确认",
    "topo_link":      "拓扑连接",
}
GUIHUA_STEP_ORDER = list(GUIHUA_STEP_NAMES.keys())

GUIHUA_CTA: dict[str, tuple[str, str, str]] = {
    "idle":   ("启动规划设计", "primary", "/start_guihua"),
    "paused": ("提交并继续",   "primary", "/resume_guihua"),
    "done":   ("查看结论",     "primary", "/view_report"),
    "failed": ("重试",         "primary", "/retry_guihua"),
}

_EXTRACT_SOURCE_LABEL: dict[str, str] = {
    "llm":       "LLM 自动抽取",
    "cache":     "缓存命中",
    "filenames": "文件名占位（精度较低）",
    "fallback":  "启发式降级（精度较低）",
}


# ── 业务 KPI ──────────────────────────────────────────────────────────────────

def _kpi_items(state: dict[str, Any]) -> list[SduiStatisticRowItem]:
    """黄金指标 KPI：抽出设备 / 创建设备 / 拓扑链路 / 提取来源。"""
    m = collect_metrics(state)
    items: list[SduiStatisticRowItem] = []
    if "device_count" in m:
        items.append(SduiStatisticRowItem(
            title="抽出设备", value=f"{m['device_count']} 项", color="accent"))
    if "created_count" in m:
        items.append(SduiStatisticRowItem(
            title="创建设备", value=f"{m['created_count']} 个", color="accent"))
    if "link_count" in m:
        items.append(SduiStatisticRowItem(
            title="拓扑链路", value=f"{m['link_count']} 条", color="subtle"))
    src = m.get("extract_source", "")
    if src:
        short = {"llm": "LLM", "cache": "缓存", "filenames": "文件名", "fallback": "启发式"}.get(src, src)
        items.append(SduiStatisticRowItem(
            title="提取方式", value=short,
            color="warning" if src in ("filenames", "fallback") else "subtle"))
    return items


# ── 告警与上下文卡 ────────────────────────────────────────────────────────────

def _build_extract_alert(state: dict[str, Any]) -> SduiAlertNode | None:
    """BOQ 提取质量不佳（fallback/filenames 来源）时显示警告横幅。"""
    m = collect_metrics(state)
    src = m.get("extract_source", "")
    if src not in ("filenames", "fallback"):
        return None
    label = _EXTRACT_SOURCE_LABEL.get(src, src)
    return SduiAlertNode(
        id="extract-quality-alert",
        tone="warning",
        title="设备清单精度提示",
        message=(
            f"当前设备清单由「{label}」生成，可能存在遗漏或错误。"
            "建议在「设备确认」步骤仔细核对，如有误可选「重新提取 BOQ」。"
        ),
    )


def _build_device_context_card(state: dict[str, Any]) -> SduiCardNode | None:
    """device_confirm HITL 前：展示 BOQ 提取设备清单供用户核对。
    依赖 boq_extract 在 metrics 写入 device_list_preview（前 10 项）。"""
    hitl = state.get("hitl") or {}
    if hitl.get("step") != "device_confirm":
        return None
    m = collect_metrics(state)
    preview: list[dict] = m.get("device_list_preview") or []
    if not preview:
        # 没有预览数据（旧版 boq_extract）：只显示数量提示
        count = m.get("device_count", 0)
        return SduiCardNode(
            id="device-context-card",
            title="请核对：BOQ 设备清单",
            tone="info",
            children=[SduiAlertNode(
                id="device-no-preview",
                tone="info",
                message=(
                    f"共抽出 {count} 项设备。"
                    "详细清单见工作区 ProjectData/RunTime/device_list.json。"
                ),
            )],
        )

    total = m.get("device_count", len(preview))
    truncated = m.get("device_list_truncated", False)
    suffix = f"（{total} 项，仅展示前 {len(preview)} 项）" if truncated else f"（{total} 项）"

    rows = [
        [d.get("name", "未知"), d.get("type", "其他"), str(d.get("qty", 1))]
        for d in preview
    ]
    children: list[SduiNode] = [
        SduiTableNode(id="device-preview-table", headers=["设备名称", "类别", "数量"], rows=rows),
    ]
    if truncated:
        children.append(SduiTextNode(
            id="truncate-hint",
            content=f"仅展示前 {len(preview)} 项，完整清单见 ProjectData/RunTime/device_list.json",
            variant="caption",
            color="subtle",
        ))

    return SduiCardNode(
        id="device-context-card",
        title=f"请核对：BOQ 设备清单 {suffix}",
        tone="info",
        children=children,
    )


def _build_topo_context_card(state: dict[str, Any]) -> SduiCardNode | None:
    """topo_confirm HITL 前：展示已创建设备的类别分布，帮助用户评估拓扑。"""
    hitl = state.get("hitl") or {}
    if hitl.get("step") != "topo_confirm":
        return None
    m = collect_metrics(state)
    created = m.get("created_count", 0)
    categories: dict[str, int] = m.get("categories") or {}

    children: list[SduiNode] = [
        SduiAlertNode(
            id="topo-hint",
            tone="info",
            message="请确认设备类别与数量分布符合设计意图，确认后将执行拓扑连接。",
        ),
    ]

    if categories:
        children.append(SduiDividerNode())
        rows = [
            [cat, str(cnt)]
            for cat, cnt in sorted(categories.items(), key=lambda x: -x[1])
        ]
        children.append(SduiTableNode(
            id="topo-cat-table",
            headers=["设备类别", f"已创建（台）"],
            rows=rows,
        ))

    return SduiCardNode(
        id="topo-context-card",
        title=f"请核对：已创建设备概览（{created} 台）",
        tone="info",
        children=children,
    )


def _build_intro_card() -> SduiCardNode:
    """Idle 状态引导卡：说明规划设计任务流程与所需输入。"""
    return SduiCardNode(
        id="guihua-intro",
        title="规划设计任务说明",
        children=[SduiMarkdownNode(content=(
            "· 上传含 BOQ 清单的建模仿真资料包（.xlsx）\n"
            "· 系统 LLM 自动抽取设备清单（机柜 / 服务器 / 网络 / 配电等）\n"
            "· 设备确认（HITL）：人工核对清单后，批量在 Nvisual 创建设备\n"
            "· 拓扑确认（HITL）：确认拓扑结构后，完成网络连接\n"
            "· 全流程 5 步，2 处 HITL 门控关键决策节点"
        ))],
    )


# ── 摘要 ──────────────────────────────────────────────────────────────────────

def _build_summary(state: dict[str, Any]) -> SduiCardNode | None:
    """阶段摘要 bits；无 bits 时回退最新日志。"""
    m = collect_metrics(state)
    bits: list[str] = []
    if "device_count" in m:
        src = _EXTRACT_SOURCE_LABEL.get(m.get("extract_source", ""), "")
        bits.append(f"BOQ 抽出设备 {m['device_count']} 项{('（' + src + '）') if src else ''}")
    if m.get("created_count"):
        bits.append(f"已在 Nvisual 创建设备 {m['created_count']} 个")
    if "link_count" in m:
        bits.append(f"拓扑连接 {m['link_count']} 条，已结题")
    return build_summary_card(bits, state)


# ── 顶层入口 ──────────────────────────────────────────────────────────────────

def project(state: dict[str, Any]) -> dict[str, Any]:
    """SkillState → SduiDocument JSON-compatible dict。"""
    status_key, _ = overall_status(state, GUIHUA_STEP_ORDER)
    is_idle = status_key == "idle"

    nodes: list[SduiNode] = [
        build_header(state, default_name="规划设计", cta_map=GUIHUA_CTA,
                     step_order=GUIHUA_STEP_ORDER),
    ]

    # ── Idle：只显示引导卡，不展示空 Stepper ──
    if is_idle:
        nodes.append(_build_intro_card())
        doc = SduiDocument(
            root=SduiStackNode(id="guihua-root", gap="sm", children=nodes),
            meta={"skill": "guihua", "run_id": state.get("run_id", "")},
        )
        return dump_sdui_json(doc)

    # ── 正常执行态 ──
    nodes.append(build_stepper(state, step_names=GUIHUA_STEP_NAMES))

    # 提取质量告警（fallback/filenames 来源）
    extract_alert = _build_extract_alert(state)
    if extract_alert:
        nodes.append(extract_alert)

    # HITL 上下文：让用户看到在确认什么（device_confirm / topo_confirm 之前）
    device_ctx = _build_device_context_card(state)
    if device_ctx:
        nodes.append(device_ctx)
    topo_ctx = _build_topo_context_card(state)
    if topo_ctx:
        nodes.append(topo_ctx)

    for node in (
        build_metrics_card(state, step_order=GUIHUA_STEP_ORDER, kpi_items=_kpi_items(state)),
        build_artifacts(state),
        _build_summary(state),
        build_hitl(state, card_title="需要确认", default_choice_title="请确认"),
    ):
        if node:
            nodes.append(node)

    doc = SduiDocument(
        root=SduiStackNode(id="guihua-root", gap="sm", children=nodes),
        meta={"skill": "guihua", "run_id": state.get("run_id", "")},
    )
    return dump_sdui_json(doc)
