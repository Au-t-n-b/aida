"""
guihua SDUI 投影器 · SkillState → SduiDocument（纯函数 · 无副作用 · 可单测）

建模仿真（规划设计前半段）作业界面：
  - Idle：流程说明引导卡
  - 执行态：右侧「仿真软件 / 设备数据」双页签（EmbeddedWeb iframe + 适配表 Markdown）
  - data_confirm HITL：展示适配信息表供核对
  - cabinet_move HITL：提示刷新 nVisual + 创建概览；执行中显示 162 条落位进度条
  - handoff HITL：展示创建/落位概览（移交设备安装）

依赖 step 写入 metrics：
  adapt_build  → combo_model / device_count / matched_count / compat_table_md / adapt_mode
  combo_create → created_count / pod_count / combo_base / move_total / sim_live / create_ok
  cabinet_move → move_total / move_sent / move_done
"""
from __future__ import annotations

from typing import Any

from agent.sdui.builder import (
    SduiDocument, SduiNode, SduiStackNode, SduiCardNode,
    SduiAlertNode, SduiDividerNode, SduiTextNode, SduiProgressBarNode,
    SduiMarkdownNode, SduiTabGroupNode, SduiTabPanel, SduiEmbeddedWebNode,
    SduiMacroStepRailNode, SduiMacroStep,
    SduiStatisticRowItem, dump_sdui_json,
)
from agent.sdui.projector_base import (
    collect_metrics, overall_status,
    build_header, build_stepper, build_metrics_card,
    build_artifacts, build_summary_card, build_hitl,
)
from .services.sim_api import web_url, is_live

GUIHUA_STEP_NAMES: dict[str, str] = {
    "adapt_build":  "设备适配",
    "data_confirm": "数据确认",
    "combo_create": "创建超节点",
    "cabinet_move": "机柜落位",
    "handoff":      "移交设备安装",
}
GUIHUA_STEP_ORDER = list(GUIHUA_STEP_NAMES.keys())

GUIHUA_CTA: dict[str, tuple[str, str, str]] = {
    "idle":   ("启动建模仿真", "primary", "/start_guihua"),
    "paused": ("提交并继续",   "primary", "/resume_guihua"),
    "done":   ("查看结论",     "primary", "/view_report"),
    "failed": ("重试",         "primary", "/retry_guihua"),
}

# 宏观阶段：把 5 个 micro step 折叠成 4 个用户可感知的大阶段（顶部 MacroStepRail）——
# 与 zhgk 同骨架（P1 统一空间范式）。
GUIHUA_MACRO_PHASES: list[tuple[str, str, str, list[str]]] = [
    ("adapt",   "设备适配", "解析信息表 · 匹配型号", ["adapt_build"]),
    ("confirm", "数据确认", "核对适配表",           ["data_confirm"]),
    ("build",   "创建落位", "超节点 · 162 柜落位",   ["combo_create", "cabinet_move"]),
    ("handoff", "移交安装", "移交设备安装",         ["handoff"]),
]


def _build_macro_rail(state: dict[str, Any]) -> SduiMacroStepRailNode | None:
    """顶部宏观阶段条：5 micro step 折叠成 4 大阶段，让用户始终知道在哪个大阶段。"""
    by_key = {s.get("key", ""): s for s in (state.get("steps") or [])}
    if not by_key:
        return None
    macro_steps: list[SduiMacroStep] = []
    current_id: str | None = None
    for pid, title, hint, micro_keys in GUIHUA_MACRO_PHASES:
        statuses = [(by_key.get(k) or {}).get("status", "pending") for k in micro_keys]
        if any(s in ("running", "hitl", "failed") for s in statuses):
            status, is_current = "running", True
        elif all(s == "completed" for s in statuses):
            status, is_current = "done", False
        elif any(s == "completed" for s in statuses):
            status, is_current = "running", True  # 部分完成 = 进行中
        else:
            status, is_current = "pending", False
        if is_current and current_id is None:
            current_id = pid
        macro_steps.append(SduiMacroStep(
            id=pid, title=title, hint=hint, status=status,  # type: ignore[arg-type]
        ))
    if current_id is None and macro_steps and all(s.status == "done" for s in macro_steps):
        current_id = macro_steps[-1].id
    return SduiMacroStepRailNode(id="macro-rail", steps=macro_steps, currentId=current_id)


# ── 业务 KPI ──────────────────────────────────────────────────────────────────

def _kpi_items(state: dict[str, Any]) -> list[SduiStatisticRowItem]:
    m = collect_metrics(state)
    items: list[SduiStatisticRowItem] = []
    combo = m.get("combo_model") or m.get("combo_base")
    if combo:
        items.append(SduiStatisticRowItem(title="超节点组合", value=str(combo), color="accent"))
    if "device_count" in m:
        items.append(SduiStatisticRowItem(
            title="适配设备", value=f"{m['device_count']} 项", color="subtle"))
    if "created_count" in m:
        items.append(SduiStatisticRowItem(
            title="创建超节点", value=f"{m['created_count']} 组", color="accent"))
    if "move_total" in m:
        sent, total = m.get("move_sent", 0), m.get("move_total", 0)
        items.append(SduiStatisticRowItem(
            title="机柜落位", value=f"{sent}/{total} 柜",
            color="success" if m.get("move_done") else "subtle"))
    # 仿真 API 模式
    if state.get("steps"):
        live = m.get("sim_live", is_live())
        items.append(SduiStatisticRowItem(
            title="仿真接口", value="LIVE" if live else "dry-run",
            color="warning" if not live else "success"))
    return items


# ── 仿真软件 / 设备数据 双页签 ─────────────────────────────────────────────────

def _build_sim_tabs(state: dict[str, Any]) -> SduiTabGroupNode | None:
    """右侧双页签：① 仿真软件（nVisual iframe）② 设备数据（适配信息表）。
    适配表生成后（有 compat_table_md）才出现「设备数据」页。"""
    m = collect_metrics(state)
    compat_md = m.get("compat_table_md") or ""
    offline = not is_live()
    sim_offline_note = None if not offline else (
        "仿真软件访问页（nVisual）。当前为离线/内网不可达环境，已用占位兜底；"
        "到内网后将自动嵌入，或点「新页打开」。"
    )
    tabs: list[SduiTabPanel] = [
        SduiTabPanel(
            id="sim", label="仿真软件",
            children=[SduiEmbeddedWebNode(
                id="sim-iframe", url=web_url(), title="nVisual 仿真软件",
                note=sim_offline_note, height=560, openInNewTab=True,
                offline=offline or None,  # P5：离线时渲染骨架占位而非空白 iframe
            )],
        ),
    ]
    if compat_md:
        truncated = m.get("compat_table_truncated")
        body: list[SduiNode] = [SduiMarkdownNode(id="compat-md", content=compat_md)]
        if truncated:
            body.append(SduiTextNode(
                id="compat-trunc", variant="caption", color="subtle",
                content="表格较长已截断，完整见 ProjectData/RunTime/compat_table.md"))
        tabs.append(SduiTabPanel(id="data", label="设备数据", children=body))

    # HITL 在数据确认时，引导切到「设备数据」页核对
    hitl_step = (state.get("hitl") or {}).get("step")
    active = "data" if (hitl_step == "data_confirm" and compat_md) else "sim"
    return SduiTabGroupNode(id="guihua-tabs", tabs=tabs, activeTab=active)


# ── HITL 上下文卡 ─────────────────────────────────────────────────────────────

def _build_move_context(state: dict[str, Any]) -> SduiCardNode | None:
    """cabinet_move HITL 前：提示刷新 nVisual + 创建概览。"""
    if (state.get("hitl") or {}).get("step") != "cabinet_move":
        return None
    m = collect_metrics(state)
    return SduiCardNode(
        id="move-context-card", title="超节点已创建，准备机柜落位", tone="info",
        children=[
            SduiAlertNode(
                id="refresh-hint", tone="warning",
                title="请先刷新 nVisual",
                message=(
                    f"已创建超节点 {m.get('created_count', 0)} 组 / {m.get('pod_count', 0)} 个 POD。"
                    "请在「仿真软件」页签手动刷新一次，确认超节点已显示，再开始逐机柜落位"
                    f"（共 {m.get('move_total', 0)} 条）。"
                ),
            ),
        ],
    )


def _build_handoff_context(state: dict[str, Any]) -> SduiCardNode | None:
    """handoff HITL 前：创建 + 落位概览（移交设备安装）。"""
    if (state.get("hitl") or {}).get("step") != "handoff":
        return None
    m = collect_metrics(state)
    return SduiCardNode(
        id="handoff-context-card", title="超节点已创建并落位完毕", tone="success",
        children=[SduiAlertNode(
            id="handoff-hint", tone="info",
            message=(
                f"超节点组合「{m.get('combo_base') or m.get('combo_model') or '—'}」，"
                f"创建 {m.get('created_count', 0)} 组，落位 {m.get('move_sent', 0)}/{m.get('move_total', 0)} 柜。"
                "确认后将生成参数面设备并移交「设备安装」模块（建模仿真到此结束）。"
            ),
        )],
    )


def _build_move_progress(state: dict[str, Any]) -> SduiCardNode | None:
    """cabinet_move 执行中/完成：162 条落位进度条。"""
    m = collect_metrics(state)
    total = m.get("move_total")
    if not total or "move_sent" not in m:
        return None
    sent = m.get("move_sent", 0)
    pct = round(100 * sent / total) if total else 0
    done = bool(m.get("move_done"))
    return SduiCardNode(
        id="move-progress-card",
        title=f"机柜落位进度 {sent}/{total}（{pct}%）",
        tone="success" if done else "default",
        children=[SduiProgressBarNode(
            id="move-bar", value=pct, label="batchMoveNodes 逐机柜",
            tone="success" if done else "warning")],
    )


def _build_intro_card() -> SduiCardNode:
    return SduiCardNode(
        id="guihua-intro", title="建模仿真任务说明（规划设计前半段）",
        children=[SduiMarkdownNode(content=(
            "· 解析《建模仿真设备信息表》→ 调仿真 API 匹配设备型号 / 板卡 → 生成**设备适配信息表**\n"
            "· **数据确认（HITL）**：核对适配表「设备数据」无误后开始创建超节点\n"
            "· **创建超节点**：batchCreateCombo ×5（9 个 POD 平铺创建）\n"
            "· **机柜落位（HITL）**：刷新 nVisual 后 batchMoveNodes ×162 逐机柜落位\n"
            "· **移交设备安装（HITL 边界）**：生成参数面设备 → 移交设备安装模块，建模仿真结束\n\n"
            "> 仿真 API 默认 dry-run（离线复用样本兜底）；置 `SIM_API_LIVE=1` 接内网真跑。"
        ))],
    )


# ── 摘要 ──────────────────────────────────────────────────────────────────────

def _build_summary(state: dict[str, Any]) -> SduiCardNode | None:
    m = collect_metrics(state)
    bits: list[str] = []
    if m.get("combo_model") or m.get("combo_base"):
        combo = m.get("combo_model") or m.get("combo_base")
        dc = m.get("device_count")
        bits.append(f"适配组合「{combo}」" + (f"，设备 {dc} 项" if dc else ""))
    if m.get("created_count"):
        bits.append(f"创建超节点 {m['created_count']} 组 / {m.get('pod_count', 0)} 个 POD")
    if "move_total" in m:
        bits.append(f"机柜落位 {m.get('move_sent', 0)}/{m['move_total']} 柜"
                    + ("（完成）" if m.get("move_done") else ""))
    if m.get("handed_off"):
        bits.append("已移交设备安装模块，建模仿真结题")
    return build_summary_card(bits, state)


# ── 顶层入口 ──────────────────────────────────────────────────────────────────

def project(state: dict[str, Any]) -> dict[str, Any]:
    """SkillState → SduiDocument JSON-compatible dict。"""
    status_key, _ = overall_status(state, GUIHUA_STEP_ORDER)
    is_idle = status_key == "idle"

    nodes: list[SduiNode] = [
        build_header(state, default_name="建模仿真", cta_map=GUIHUA_CTA,
                     step_order=GUIHUA_STEP_ORDER),
    ]

    if is_idle:
        nodes.append(_build_intro_card())
        doc = SduiDocument(
            root=SduiStackNode(id="guihua-root", gap="md", children=nodes),
            meta={"skill": "guihua", "run_id": state.get("run_id", "")},
        )
        return dump_sdui_json(doc)

    # ── 执行态（统一信息架构 P1：header → macro-rail → KPI 带 → 可折叠明细 → 工作台 → 分节）──
    #   与 zhgk 同顶部骨架；工作台（宽 nVisual iframe）保持单列全宽，不强塞窄数据栅格。

    # P1：顶部宏观阶段条（4 大阶段，与 zhgk 同款进度模型）
    macro_rail = _build_macro_rail(state)
    if macro_rail:
        nodes.append(macro_rail)

    # P3：KPI 黄金指标通栏扫读带（紧贴 macro-rail，数据焦点）
    metrics_band = build_metrics_card(state, step_order=GUIHUA_STEP_ORDER, kpi_items=_kpi_items(state))
    if metrics_band:
        nodes.append(metrics_band)

    # HITL 置顶通栏（id=hitl-card；前端据此路由到左侧会话）
    hitl_card = build_hitl(state, card_title="需要确认", default_choice_title="请确认")
    if hitl_card:
        nodes.append(hitl_card)

    # P2：micro-step 明细折叠卡（默认收起；macro-rail/donut 已承载概览）
    nodes.append(build_stepper(
        state, step_names=GUIHUA_STEP_NAMES,
        collapsible=True, default_collapsed=True,
    ))

    # 工作台（全宽）：仿真双页签 + 落位进度 + HITL 上下文
    for node in (
        _build_sim_tabs(state),
        _build_move_progress(state),
        _build_move_context(state),
        _build_handoff_context(state),
    ):
        if node:
            nodes.append(node)

    # P3 分节：产出与摘要
    output_group: list[SduiNode] = [
        n for n in (build_artifacts(state), _build_summary(state)) if n
    ]
    if output_group:
        nodes.append(SduiDividerNode(id="grp-output", label="产出与摘要"))
        nodes.extend(output_group)

    doc = SduiDocument(
        root=SduiStackNode(id="guihua-root", gap="md", children=nodes),
        meta={"skill": "guihua", "run_id": state.get("run_id", "")},
    )
    return dump_sdui_json(doc)
