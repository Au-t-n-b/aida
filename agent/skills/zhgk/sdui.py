"""
zhgk SDUI 投影器 · SkillState → SduiDocument

通用段（header / stepper / 进度环 / 产物栏 / HITL / 日志摘要）走
agent.sdui.projector_base；本文件只保留 zhgk 自有业务：KPI 指标、风险告警表、摘要 bits。
纯函数：project(state) → dict，无副作用，可单测。

Metrics 键约定（由各 step 写入）：
  assess step      → assess_total · assess_满足/不满足/不涉及/未勘测/无法识别
  determine_gen    → generation_cooling · gen_cooling_source
  filter_build     → filtered_count · sub_scenes
  issue_list       → issue_list_path
  report_gen_run   → risks (list[{level, title, trigger}]) · risk_hit
  report_distribute→ recipients · email_sent
"""
from __future__ import annotations

from typing import Any

from agent.sdui.builder import (
    SduiDocument, SduiNode, SduiStackNode, SduiCardNode, SduiTableNode,
    SduiRowNode, SduiBarChartNode, SduiBarDatum,
    SduiStatisticRowNode, SduiStatisticRowItem,
    SduiAlertNode, SduiMarkdownNode, SduiDividerNode,
    SduiDonutChartNode, SduiDonutSegment,
    SduiNumberCardNode,
    SduiTimelineNode, SduiTimelineEvent,
    dump_sdui_json,
)
from agent.sdui.projector_base import (
    collect_metrics, overall_status,
    build_header, build_stepper, build_progress_donut,
    build_artifacts, build_summary_card, build_hitl,
)

# ── 步骤元数据（顺序即展示顺序）──
ZHGK_STEP_NAMES: dict[str, str] = {
    "preflight":         "环境预检",
    "intent_select":     "意图选择",
    "scene_suggest_run": "场景建议",
    "determine_gen":     "代际制冷识别",
    "filter_build":      "底表过滤建表",
    "method_split":      "勘测方法分流",
    "data_append":       "数据条目追加",
    "confirm_table":     "勘测表确认",
    "wait_survey":       "等待现场上传",
    "assess":            "AI 五值评估",
    "issue_list":        "问题清单生成",
    "resurvey_gate":     "复勘检查门控",
    "supplement_run":    "补充勘测处理",
    "report_gen_run":    "报告生成",
    "report_distribute": "审批与分发",
}
ZHGK_STEP_ORDER = list(ZHGK_STEP_NAMES.keys())

# CTA：{status_key: (label, variant, post_message)}（running 态自动不显示按钮）
ZHGK_CTA: dict[str, tuple[str, str, str]] = {
    "idle":   ("启动工勘", "primary", "/start_zhgk"),
    "paused": ("提交并继续", "primary", "/resume_zhgk"),
    "done":   ("查看报告", "primary", "/view_report"),
    "failed": ("重试", "primary", "/retry_zhgk"),
}

# 风险等级排序（高→中→低）
_RISK_LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2}
_RISK_LEVEL_LABEL  = {"high": "高", "medium": "中", "low": "低"}


# ── zhgk 自有业务段 ──

def _build_idle_intro() -> SduiCardNode:
    """Idle 状态引导卡（v4 意图驱动版）。"""
    return SduiCardNode(
        id="zhgk-intro",
        title="智慧工勘 v4 · 任务说明",
        children=[SduiMarkdownNode(content=(
            "**支持 4 种工作流（启动后选择意图）：**\n\n"
            "1. **全流程工勘** — BOQ → 代际制冷识别 → 建勘测表 → 现场勘测 → AI 评估 → 问题清单 → 复勘\n"
            "2. **生成工勘报告** — 基于已完成的勘测结果表，生成三件套 + 工勘报告.docx\n"
            "3. **场景建议** — 快速给出当前项目的勘测场景推荐\n"
            "4. **补充勘测** — 向已有勘测结果表追加数据类条目\n\n"
            "**所需输入件：**\n"
            "· `Input/BOQ.xlsx` — 用于识别代际（A2/A3/A5）和制冷方式（液冷/风冷）\n"
            "· `Template/入场评估标准表.xlsx` — 勘测条目底表\n"
            "· `Template/新版项目工勘报告模板.docx` — 报告生成模板（仅 report_gen 需要）\n\n"
            "请点击「启动工勘」按钮开始任务。"
        ))],
    )


def _build_risk_alert(state: dict[str, Any]) -> SduiAlertNode | None:
    """高风险 Alert 横幅：有高风险项时显示在告警表上方，强调优先处理。"""
    m = collect_metrics(state)
    risks: list[dict] = m.get("risks") or []
    high = sum(1 for r in risks if r.get("level") == "high")
    if not high:
        return None
    return SduiAlertNode(
        id="risk-top-alert",
        tone="error",
        title=f"发现 {high} 条高风险项",
        message=(
            f"本项目存在 {high} 条高风险，建议在提交审批前优先处理。"
            "详见下方「风险与告警」表。"
        ),
    )




def _kpi_items(state: dict[str, Any]) -> list[SduiStatisticRowItem]:
    """黄金指标 KPI：意图 · 代际制冷 · 条目数 · 评估满足率 · 风险命中 · 分发干系人。"""
    m = collect_metrics(state)
    items: list[SduiStatisticRowItem] = []

    # 意图（intent_select 完成后出现）
    _INTENT_LABEL = {
        "survey_work":    "全流程工勘",
        "report_gen":     "报告生成",
        "scene_suggest":  "场景建议",
        "supplement":     "补充勘测",
    }
    intent = m.get("intent") or (state.get("project") or {}).get("intent", "")
    if intent:
        items.append(SduiStatisticRowItem(
            title="意图", value=_INTENT_LABEL.get(intent, intent), color="accent"
        ))

    # 代际制冷（determine_gen 完成后出现）
    gen_cooling = (
        m.get("generation_cooling")
        or (state.get("project") or {}).get("generation_cooling", "")
    )
    if gen_cooling:
        items.append(SduiStatisticRowItem(
            title="代际制冷", value=gen_cooling, color="subtle"
        ))

    # 底表过滤条目数（filter_build 完成后出现）
    if m.get("filtered_count"):
        items.append(SduiStatisticRowItem(
            title="勘测条目", value=f"{m['filtered_count']} 条", color="subtle"
        ))

    # 细分场景（filter_build 完成后出现）
    sub_scenes = m.get("sub_scenes")
    if sub_scenes:
        items.append(SduiStatisticRowItem(
            title="勘测场景", value=" / ".join(sub_scenes), color="subtle"
        ))

    # v3 兼容：冷却标签/场景
    if m.get("cooling_tag") and not gen_cooling:
        items.append(SduiStatisticRowItem(title="制冷方案", value=m["cooling_tag"], color="subtle"))
    if m.get("scenario"):
        items.append(SduiStatisticRowItem(title="勘测场景", value=m["scenario"], color="subtle"))

    # 勘测汇总阶段
    if "fill_pct" in m:
        items.append(SduiStatisticRowItem(title="勘测填写率", value=f"{m['fill_pct']}%", color="accent"))
    if "todo_client" in m:
        todo_total = (
            (m.get("todo_client") or 0)
            + (m.get("todo_image") or 0)
            + (m.get("todo_supplement") or 0)
        )
        items.append(SduiStatisticRowItem(
            title="待办项合计",
            value=f"{todo_total} 项",
            color="warning" if todo_total else "success",
        ))

    # 评估报告阶段（assess step 写 assess_total / assess_满足 / assess_不满足 等）
    asm_total = m.get("assess_total")
    if asm_total:
        satisfied = m.get("assess_满足", 0)
        满足率 = round(satisfied / asm_total * 100) if asm_total else 0
        items.append(SduiStatisticRowItem(
            title="评估满足率", value=f"{满足率}%（{satisfied}/{asm_total}）", color="accent"))
    if "risk_hit" in m:
        hit = m.get("risk_hit", 0)
        items.append(SduiStatisticRowItem(
            title="风险命中", value=f"{hit} 条",
            color="warning" if hit else "success"))

    # 审批分发阶段
    if "recipients" in m:
        items.append(SduiStatisticRowItem(
            title="分发干系人", value=f"{m['recipients']} 人", color="subtle"))

    return items


def _build_alerts(state: dict[str, Any]) -> SduiCardNode | None:
    """风险与告警表（高→中→低排序，含分级统计行，最多展示 12 条）。"""
    m = collect_metrics(state)
    risks: list[dict] = m.get("risks") or []
    if not risks:
        return None

    # 按等级排序（高→中→低→其他）
    sorted_risks = sorted(
        risks, key=lambda r: _RISK_LEVEL_ORDER.get(r.get("level", ""), 99)
    )

    # 分级统计
    high = sum(1 for r in risks if r.get("level") == "high")
    med  = sum(1 for r in risks if r.get("level") == "medium")
    low  = sum(1 for r in risks if r.get("level") == "low")

    # 截取前 12 条（排序后优先展示高风险）
    rows = []
    for r in sorted_risks[:12]:
        level_label = _RISK_LEVEL_LABEL.get(r.get("level", ""), r.get("level", ""))
        rows.append([level_label, r.get("title", ""), r.get("trigger", "")])

    suffix = "，仅展示前 12 条" if len(risks) > 12 else ""
    return SduiCardNode(
        id="alerts", title=f"风险与告警（{len(risks)} 条{suffix}）",
        tone="danger" if high > 0 else ("warning" if med > 0 else None),
        children=[
            SduiStatisticRowNode(id="risk-stats", items=[
                SduiStatisticRowItem(title="高风险", value=high,
                                     color="error" if high else "subtle"),
                SduiStatisticRowItem(title="中风险", value=med,
                                     color="warning" if med else "subtle"),
                SduiStatisticRowItem(title="低风险", value=low, color="subtle"),
            ]),
            SduiDividerNode(),
            SduiTableNode(id="risk-table", headers=["等级", "风险描述", "触发条件"], rows=rows),
        ],
    )


def _build_summary(state: dict[str, Any]) -> SduiCardNode | None:
    """阶段摘要 bits（随流程推进逐步丰富）；无 bits 时回退最新日志。"""
    m = collect_metrics(state)
    bits: list[str] = []

    # preflight AI 诊断摘要（最先出现）
    if m.get("ai_summary"):
        bits.append(m["ai_summary"])

    # v4: 代际制冷识别结果
    gen_cooling = m.get("generation_cooling") or (state.get("project") or {}).get("generation_cooling", "")
    if gen_cooling and not m.get("cooling_tag"):
        src = m.get("gen_cooling_source", "")
        bits.append(f"代际制冷 {gen_cooling}" + (f"（{src}）" if src else ""))

    # v4: 底表过滤结果
    if m.get("filtered_count"):
        sub = "/".join(m.get("sub_scenes", []))
        bits.append(f"底表过滤: {m['filtered_count']} 条（{gen_cooling} · {sub}）")

    # v3 兼容: 场景筛选结果
    if m.get("cooling_tag") and m.get("scenario"):
        bits.append(f"场景「{m['scenario']}」· 制冷「{m['cooling_tag']}」")

    # 勘测汇总结果
    if "fill_pct" in m:
        bits.append(
            f"勘测填写率 {m['fill_pct']}%"
            f"（{m.get('filled', '?')}/{m.get('total', '?')} 项）"
        )
        tc = m.get("todo_client") or 0
        ti = m.get("todo_image")  or 0
        ts = m.get("todo_supplement") or 0
        if tc + ti + ts:
            bits.append(f"待办：客户确认 {tc} · 拍摄图片 {ti} · 补充勘测 {ts}")

    # 评估报告结果（assess_total / assess_满足 等由 assess step 写入）
    if m.get("assess_total"):
        satisfied = m.get("assess_满足", 0)
        unsat = m.get("assess_不满足", 0)
        unrecog = m.get("assess_无法识别", 0)
        bits.append(
            f"评估 {m['assess_total']} 项："
            f"满足 {satisfied} · 不满足 {unsat}"
            + (f" · 无法识别 {unrecog}" if unrecog else "")
        )
    if "risk_hit" in m:
        bits.append(f"识别风险 {m['risk_hit']} 条")

    # 审批分发结果
    if "recipients" in m:
        bits.append(f"已生成审批包，干系人 {m['recipients']} 人")
        if not m.get("email_sent"):
            bits.append("⚠️ 审批邮件未发送（设置 ZHGK_SEND_EMAIL=1 启用）")

    return build_summary_card(bits, state)


def _build_metrics_card(state: dict[str, Any]) -> SduiCardNode | None:
    """黄金指标卡（zhgk 定制版）：
      左  进度环（DonutChart）
      右  评估分布 BarChart（report_gen 后出现）+ KPI 行（StatisticRow，始终展示）
    """
    steps = state.get("steps") or []
    if not steps:
        return None

    m = collect_metrics(state)
    donut = build_progress_donut(state, step_order=ZHGK_STEP_ORDER)
    kpi_items = _kpi_items(state)

    right_children: list[SduiNode] = []

    # 评估分布 BarChart（assess step 完成后出现，使用 assess_* 键）
    if m.get("assess_total"):
        bar_data = [
            SduiBarDatum(label="满足",    value=m.get("assess_满足",    0) or 0, color="success"),
            SduiBarDatum(label="不满足",  value=m.get("assess_不满足",  0) or 0, color="error"),
            SduiBarDatum(label="未勘测",  value=m.get("assess_未勘测",  0) or 0, color="warning"),
            SduiBarDatum(label="无法识别",value=m.get("assess_无法识别",0) or 0, color="warning"),
            SduiBarDatum(label="不涉及",  value=m.get("assess_不涉及",  0) or 0, color="subtle"),
        ]
        right_children.append(SduiBarChartNode(id="asm-bar", data=bar_data, valueUnit="项"))

    # KPI 行（始终展示；无数据时降级为步骤进度）
    if kpi_items:
        right_children.append(SduiStatisticRowNode(id="kpi-row", items=kpi_items))
    else:
        total = len(ZHGK_STEP_ORDER)
        done  = sum(1 for s in steps if s.get("status") == "completed")
        right_children.append(SduiStatisticRowNode(id="kpi-row", items=[
            SduiStatisticRowItem(title="已完成步骤", value=f"{done}/{total}"),
        ]))

    right_col = SduiStackNode(id="metrics-right", gap="sm", children=right_children, flex=2)

    return SduiCardNode(
        id="golden-metrics", title="黄金指标",
        children=[SduiRowNode(id="metrics-row", align="center", gap="lg", children=[
            donut, right_col,
        ])],
    )


# ── zhgk 自有业务段（续）──

def _build_assessment_panel(state: dict[str, Any]) -> SduiCardNode | None:
    """AI 五值评估面板（assess step 完成后出现）。

    布局（参照智慧工勘 workbench HTML）：
      ① 5 个 NumberCard — 满足 / 不满足 / 不涉及 / 未勘测 / 无法识别
      ② Row[DonutChart 满足度分布 ＋ BarChart 条目分布]
      ③ 条件 Alert — 不满足 > 0 → warning · 无法识别 > 0 → error
    """
    m = collect_metrics(state)
    total: int = m.get("assess_total", 0) or 0
    if not total:
        return None

    满足    = int(m.get("assess_满足",    0) or 0)
    不满足  = int(m.get("assess_不满足",  0) or 0)
    不涉及  = int(m.get("assess_不涉及",  0) or 0)
    未勘测  = int(m.get("assess_未勘测",  0) or 0)
    无法识别= int(m.get("assess_无法识别",0) or 0)
    满足率  = round(满足 / total * 100) if total else 0

    # ① 5 大数字卡
    cards_row = SduiRowNode(
        id="assess-cards", gap="sm", wrap=True,
        children=[
            SduiNumberCardNode(id="nc-满足",    value=满足,    label="满足",    tone="success"),
            SduiNumberCardNode(id="nc-不满足",  value=不满足,  label="不满足",  tone="error"),
            SduiNumberCardNode(id="nc-不涉及",  value=不涉及,  label="不涉及",  tone="subtle"),
            SduiNumberCardNode(id="nc-未勘测",  value=未勘测,  label="未勘测",  tone="warning"),
            SduiNumberCardNode(id="nc-无法识别",value=无法识别,label="无法识别",tone="warning"),
        ],
    )

    # ② 分布环 + 条形图
    donut = SduiDonutChartNode(
        id="assess-donut",
        segments=[
            SduiDonutSegment(label="满足",    value=满足,    color="success"),
            SduiDonutSegment(label="不满足",  value=不满足,  color="error"),
            SduiDonutSegment(label="不涉及",  value=不涉及,  color="subtle"),
            SduiDonutSegment(label="未勘测",  value=未勘测,  color="warning"),
            SduiDonutSegment(label="无法识别",value=无法识别,color="warning"),
        ],
        centerLabel="满足率", centerValue=f"{满足率}%", flex=1,
    )
    bar = SduiBarChartNode(
        id="assess-dist-bar",
        data=[
            SduiBarDatum(label="满足",    value=满足,    color="success"),
            SduiBarDatum(label="不满足",  value=不满足,  color="error"),
            SduiBarDatum(label="不涉及",  value=不涉及,  color="subtle"),
            SduiBarDatum(label="未勘测",  value=未勘测,  color="warning"),
            SduiBarDatum(label="无法识别",value=无法识别,color="warning"),
        ],
        valueUnit="项", flex=2,
    )
    chart_row = SduiRowNode(id="assess-charts", align="center", gap="lg", children=[donut, bar])

    # ③ 条件告警
    children: list[SduiNode] = [cards_row, chart_row]
    if 无法识别 > 0:
        children.append(SduiAlertNode(
            id="assess-unrecog-alert", tone="error",
            title=f"{无法识别} 项「无法识别」",
            message=(
                f"存在 {无法识别} 项结论无法识别（数据缺失或图片不清晰），"
                "建议安排复勘后重新评估。"
            ),
        ))
    if 不满足 > 0:
        children.append(SduiAlertNode(
            id="assess-unsat-alert", tone="warning",
            title=f"{不满足} 项「不满足」",
            message=(
                f"存在 {不满足} 项机房条件不满足评估标准，"
                "请参见问题清单，制定整改方案后再行分发。"
            ),
        ))

    tone: str = "danger" if 无法识别 > 0 else ("warning" if 不满足 > 0 else "success")
    return SduiCardNode(
        id="assess-panel",
        title=f"AI 五值评估（共 {total} 项）",
        tone=tone,   # type: ignore[arg-type]
        children=children,
    )


def _build_intent_step_names(state: dict[str, Any]) -> dict[str, str]:
    """意图感知步骤过滤：survey_work 显示全量15步；其他意图只显示本意图涉及的步骤。
    无意图（preflight 未完成）时返回全量步骤名（便于展示进度）。"""
    intent = (state.get("project") or {}).get("intent", "")
    if not intent:
        return ZHGK_STEP_NAMES  # preflight / intent_select 阶段：显示全部

    # survey_work 意图：全量15步都有意义，全部展示
    if intent == "survey_work":
        return ZHGK_STEP_NAMES

    # 其他意图：始终保留 preflight + intent_select，再加本意图专属步骤
    from .steps._intent_guard import STEP_INTENTS
    always = {"preflight", "intent_select"}
    intent_keys = {k for k, intents in STEP_INTENTS.items() if intent in intents}
    return {k: v for k, v in ZHGK_STEP_NAMES.items() if k in always or k in intent_keys}


def _build_activity_timeline(state: dict[str, Any]) -> SduiCardNode | None:
    """右侧数据面板 · 执行动态（取最近有意义日志，最新在上）。
    与 nanobot workbench 右栏「执行动态」对齐，把零散日志可视化为时间轴。"""
    logs = state.get("logs") or []
    meaningful = [
        l for l in logs
        if l and not l.startswith("[start]") and not l.startswith("[resume]")
    ]
    if not meaningful:
        return None
    recent = meaningful[-10:][::-1]  # 最新在上
    events: list[SduiTimelineEvent] = []
    for line in recent:
        tone = "default"
        if any(k in line for k in ("✓", "完成", "成功")):
            tone = "success"
        elif any(k in line for k in ("❌", "失败", "异常", "错误")):
            tone = "error"
        elif any(k in line for k in ("⏸", "HITL", "等待", "缺")):
            tone = "warning"
        events.append(SduiTimelineEvent(label=line, tone=tone))  # type: ignore[arg-type]
    return SduiCardNode(
        id="activity", title="执行动态",
        children=[SduiTimelineNode(id="activity-tl", events=events)],
    )


# ── 顶层入口 ──

def project(state: dict[str, Any]) -> dict[str, Any]:
    """SkillState → SduiDocument JSON-compatible dict。

    布局（执行态 · 双栏仪表盘，对齐 nanobot workbench）：
      ┌ header（项目名 · 状态徽标 · CTA）              ── 通栏
      ├ [HITL 卡]  ← 置顶通栏（前端可路由到左侧会话，见 survey-agent #4）
      └ Row：
          中间主区(flex 5)：黄金指标 · AI五值评估 · 风险告警 · 产物 · 阶段摘要
          右侧数据面板(flex 2)：意图感知 Stepper(竖向) · 执行动态时间轴

    通栏放置 HITL 卡（root 的直接子节点，id=hitl-card），便于前端提取/路由。
    """
    status_key, _ = overall_status(state, ZHGK_STEP_ORDER, paused_badge="待补充")
    is_idle = status_key == "idle"

    nodes: list[SduiNode] = [
        build_header(state, default_name="智慧工勘", cta_map=ZHGK_CTA,
                     step_order=ZHGK_STEP_ORDER, paused_badge="待补充"),
    ]

    # ── Idle：只显示引导卡，不展示空 Stepper ──
    if is_idle:
        nodes.append(_build_idle_intro())
        doc = SduiDocument(
            root=SduiStackNode(id="zhgk-root", gap="sm", children=nodes),
            meta={"skill": "zhgk", "run_id": state.get("run_id", "")},
        )
        return dump_sdui_json(doc)

    # ── 正常执行态 ──

    # HITL 置顶通栏：待确认第一时间呈现（id=hitl-card；前端 #4 据此路由到左侧会话）
    hitl_card = build_hitl(state, card_title="需要补充", default_choice_title="请选择")
    if hitl_card:
        nodes.append(hitl_card)

    # 中间主区：业务数据卡（各段自行判断有无数据，None 跳过）
    risk_alert = _build_risk_alert(state)
    center_children: list[SduiNode] = [
        n for n in (
            _build_metrics_card(state),
            _build_assessment_panel(state),
            risk_alert,
            _build_alerts(state),
            build_artifacts(state, input_file_keys=("boq_xlsx", "presets_docx")),
            _build_summary(state),
        ) if n
    ]

    # 右侧数据面板：意图感知 Stepper（竖向）+ 执行动态时间轴
    intent_step_names = _build_intent_step_names(state)
    right_children: list[SduiNode] = [
        build_stepper(state, step_names=intent_step_names, orientation="vertical"),
    ]
    activity = _build_activity_timeline(state)
    if activity:
        right_children.append(activity)

    nodes.append(SduiRowNode(
        id="dashboard-row", gap="md", align="start", wrap=True,
        children=[
            SduiStackNode(id="dash-center", gap="sm", flex=5, children=center_children),
            SduiStackNode(id="dash-right", gap="sm", flex=2, children=right_children),
        ],
    ))

    doc = SduiDocument(
        root=SduiStackNode(id="zhgk-root", gap="sm", children=nodes),
        meta={"skill": "zhgk", "run_id": state.get("run_id", "")},
    )
    return dump_sdui_json(doc)
