"""
zhgk SDUI 投影器 · SkillState → SduiDocument

通用段（header / stepper / 进度环 / 产物栏 / HITL / 日志摘要）走
agent.sdui.projector_base；本文件只保留 zhgk 自有业务：KPI 指标、风险告警表、摘要 bits。
纯函数：project(state) → dict，无副作用，可单测。

Metrics 键约定（由各 step 写入）：
  assess step      → assess_total · assess_满足/不满足/不涉及/未勘测/无法识别
  determine_gen    → generation_cooling · gen_cooling_source
  filter_build     → filtered_count · sub_scenes · preview_rows
  method_split     → customer_feedback_count · customer_feedback_emailed
  task_dispatch    → gkclaw_task_id · gkclaw_state · gkclaw_dry_run · gkclaw_items · gkclaw_web_url
  wait_survey      → survey_round · survey_round_history (list[{round,filled,total}])
  issue_list       → issue_list_path · issue_count · issue_rows (list[{序号,问题描述,状态,整改建议}])
  report_gen_run   → risks (list[{level, title, trigger}]) · risk_hit
  report_distribute→ recipients · email_sent
"""
from __future__ import annotations

from typing import Any

from agent.sdui.builder import (
    SduiDocument, SduiNode, SduiStackNode, SduiCardNode,
    SduiRowNode,
    SduiStatisticRowNode, SduiStatisticRowItem,
    SduiAlertNode, SduiMarkdownNode,
    SduiTimelineNode, SduiTimelineEvent,
    SduiBannerNode,
    SduiLogStreamNode, SduiLogLine,
    SduiStatusBannerNode, SduiStatusItem,
    SduiMacroStepRailNode, SduiMacroStep,
    SduiRiskListNode, SduiRiskItem,
    SduiDataTableNode,
    dump_sdui_json,
)
from agent.sdui.projector_base import (
    collect_metrics, overall_status,
    build_header, build_stepper, build_stepper_for_intent, build_progress_donut,
    build_artifacts, build_summary_card, build_hitl,
    build_assessment_panel,
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
    "task_dispatch":     "任务下发",
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
# metrics 的 level 词表 → RiskList 节点 level（注意 RiskList 用 "mid" 非 "medium"）
_RISK_LEVEL_TO_NODE = {"high": "high", "medium": "mid", "low": "low"}

# 宏观阶段：把 15 个 micro step 折叠成 4 个用户可感知的大阶段（顶部 MacroStepRail）
# 阶段名取「跨意图通用」口径：survey_work 走 4 阶段完整版（报告阶段为空时自动隐藏，
# 因 survey_work 止于问题清单）；report_gen 4 阶段全亮；scene_suggest/supplement 仅前两段。
ZHGK_MACRO_PHASES: list[tuple[str, str, str, list[str]]] = [
    ("prep",   "环境准备", "预检 · 选意图",         ["preflight", "intent_select"]),
    ("plan",   "方案识别", "代际制冷 · 建勘测表",   ["scene_suggest_run", "determine_gen", "filter_build", "method_split"]),
    ("survey", "勘测评估", "数据汇总 · AI 评估 · 复勘", ["data_append", "confirm_table", "task_dispatch", "wait_survey", "assess", "issue_list", "resurvey_gate", "supplement_run"]),
    ("report", "报告分发", "出报告 · 审批分发",     ["report_gen_run", "report_distribute"]),
]


def _log_level(line: str) -> str:
    """日志行 → LogStream 语义级别（ok / warn / error / info）。"""
    if any(k in line for k in ("✓", "完成", "成功")):
        return "ok"
    if any(k in line for k in ("❌", "失败", "异常", "错误")):
        return "error"
    if any(k in line for k in ("⏸", "HITL", "等待", "缺")):
        return "warn"
    return "info"


def _meaningful_logs(state: dict[str, Any]) -> list[str]:
    """剔除 [start]/[resume] 噪声后的日志行（时序原样保留）。"""
    return [
        l for l in (state.get("logs") or [])
        if l and not l.startswith("[start]") and not l.startswith("[resume]")
    ]


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

    # 客户反馈分流（method_split 完成后出现 · v4 自动邮件）
    cf_count = m.get("customer_feedback_count")
    if cf_count:
        emailed = m.get("customer_feedback_emailed")
        suffix = "已通知" if emailed else "待通知"
        items.append(SduiStatisticRowItem(
            title="客户反馈项", value=f"{cf_count} 条·{suffix}",
            color="success" if emailed else "warning"))

    # 复勘轮次（wait_survey/resurvey 写 survey_round）
    if m.get("survey_round"):
        items.append(SduiStatisticRowItem(
            title="勘测轮次", value=f"第 {m['survey_round']} 轮", color="subtle"))

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
    """风险与告警（高→中→低排序，分级统计 + 语义化 RiskList，最多 12 条）。"""
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

    # 截取前 12 条（排序后优先展示高风险）→ 语义化 RiskList 项（左色带 + 等级 badge）
    risk_items = [
        SduiRiskItem(
            title=r.get("title", ""),
            level=_RISK_LEVEL_TO_NODE.get(r.get("level", ""), "low"),  # type: ignore[arg-type]
            detail=r.get("trigger") or None,
        )
        for r in sorted_risks[:12]
    ]
    suffix = "，仅展示前 12 条" if len(risks) > 12 else ""

    children: list[SduiNode] = []
    # 高风险内联提示（合并原 _build_risk_alert，避免重复卡片）
    if high > 0:
        children.append(SduiAlertNode(
            id="risk-top-alert", tone="error",
            title=f"发现 {high} 条高风险项",
            message="建议在提交审批前优先处理。",
        ))
    children.extend([
        SduiStatisticRowNode(id="risk-stats", items=[
            SduiStatisticRowItem(title="高风险", value=high,
                                 color="error" if high else "subtle"),
            SduiStatisticRowItem(title="中风险", value=med,
                                 color="warning" if med else "subtle"),
            SduiStatisticRowItem(title="低风险", value=low, color="subtle"),
        ]),
        SduiRiskListNode(id="risk-list", items=risk_items),
    ])
    return SduiCardNode(
        id="alerts", title=f"风险与告警（{len(risks)} 条{suffix}）",
        tone="danger" if high > 0 else ("warning" if med > 0 else None),
        children=children,
    )


def _build_summary(state: dict[str, Any]) -> SduiCardNode | None:
    """阶段摘要 bits（随流程推进逐步丰富）；无 bits 时回退最新日志。"""
    m = collect_metrics(state)
    bits: list[str] = []

    # preflight AI 诊断摘要（最先出现）
    if m.get("ai_summary"):
        bits.append(m["ai_summary"])

    # 代际制冷识别结果
    gen_cooling = m.get("generation_cooling") or (state.get("project") or {}).get("generation_cooling", "")
    if gen_cooling:
        src = m.get("gen_cooling_source", "")
        bits.append(f"代际制冷 {gen_cooling}" + (f"（{src}）" if src else ""))

    # 底表过滤结果
    if m.get("filtered_count"):
        sub = "/".join(m.get("sub_scenes", []))
        bits.append(f"底表过滤: {m['filtered_count']} 条（{gen_cooling} · {sub}）")

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
    """黄金指标卡（zhgk 定制版）：左 进度环（DonutChart）+ 右 KPI 行（StatisticRow）。

    职责单一：只做「全局进度 + 文字指标摘要」；评估分布图归 AI 五值评估面板独占，
    不再在此重复 BarChart（曾与评估面板的同源数据重复两次）。
    """
    steps = state.get("steps") or []
    if not steps:
        return None

    donut = build_progress_donut(state, step_order=ZHGK_STEP_ORDER)
    kpi_items = _kpi_items(state)

    if not kpi_items:
        total = len(ZHGK_STEP_ORDER)
        done  = sum(1 for s in steps if s.get("status") == "completed")
        kpi_items = [SduiStatisticRowItem(title="已完成步骤", value=f"{done}/{total}")]

    right_col = SduiStackNode(
        id="metrics-right", gap="sm", flex=2,
        children=[SduiStatisticRowNode(id="kpi-row", items=kpi_items)],
    )

    return SduiCardNode(
        id="golden-metrics", title="黄金指标",
        children=[SduiRowNode(id="metrics-row", align="center", gap="lg", children=[
            donut, right_col,
        ])],
    )


# ── zhgk 自有业务段（续）──

def _build_assessment_panel(state: dict[str, Any]) -> SduiCardNode | None:
    """AI 五值评估面板（assess step 完成后出现）——委托给 projector_base 通用版。"""
    return build_assessment_panel(
        state,
        total_key="assess_total",
        value_keys=[
            ("满足",     "assess_满足",     "success"),
            ("不满足",   "assess_不满足",   "error"),
            ("不涉及",   "assess_不涉及",   "subtle"),
            ("未勘测",   "assess_未勘测",   "warning"),
            ("无法识别", "assess_无法识别", "warning"),
        ],
        node_id="assess-panel",
        title="AI 五值评估",
        rate_label="满足率",
        rate_key="assess_满足",
        alert_keys=[
            ("assess_无法识别", "error",
             "存在 {count} 项结论无法识别（数据缺失或图片不清晰），建议安排复勘后重新评估。"),
            ("assess_不满足", "warning",
             "存在 {count} 项机房条件不满足评估标准，请参见问题清单，制定整改方案后再行分发。"),
        ],
    )



def _build_filter_preview(state: dict[str, Any]) -> SduiCardNode | None:
    """勘测条目预览表（B 场景2 · filter_build 完成后出现）。
    展示前 N 条勘测条目（细分场景 / 勘测要素 / 项目 / 勘测方法）。"""
    m = collect_metrics(state)
    rows = m.get("preview_rows") or []
    if not rows:
        return None
    total = m.get("filtered_count", len(rows))
    cols = ["细分场景", "勘测要素", "项目", "勘测方法"]
    table_rows = [[str(r.get(c, "")) for c in cols] for r in rows]
    suffix = f"（共 {total} 条，预览前 {len(rows)} 条）" if total > len(rows) else f"（共 {total} 条）"
    return SduiCardNode(
        id="filter-preview", title=f"勘测条目预览{suffix}",
        children=[SduiDataTableNode(id="filter-preview-table", columns=cols, rows=table_rows)],
    )


def _build_issue_table(state: dict[str, Any]) -> SduiCardNode | None:
    """问题清单表（B 场景2 · issue_list 完成后出现）。
    展示「不满足 / 无法识别」项的问题描述 + 整改建议（前 N 条）。"""
    m = collect_metrics(state)
    rows = m.get("issue_rows") or []
    if not rows:
        return None
    total = m.get("issue_count", len(rows))
    cols = ["序号", "问题描述", "状态", "整改建议"]
    table_rows = [[str(r.get(c, "")) for c in cols] for r in rows]
    suffix = f"（共 {total} 项，预览前 {len(rows)} 项）" if total > len(rows) else f"（共 {total} 项）"
    return SduiCardNode(
        id="issue-table", title=f"问题清单{suffix}",
        tone="warning" if total else None,
        children=[SduiDataTableNode(id="issue-table-data", columns=cols, rows=table_rows)],
    )


def _build_resurvey_history(state: dict[str, Any]) -> SduiCardNode | None:
    """多轮复勘历史（B 场景5 · 第 2 轮及以后出现）。
    逐轮展示本轮填写条目数 / 填写率 / 较上轮新增，体现多轮之间的改进。"""
    m = collect_metrics(state)
    history = m.get("survey_round_history") or []
    if len(history) < 2:  # 仅单轮时无「历史」可言，由 KPI「勘测轮次」承载
        return None
    cols = ["轮次", "本轮填写", "表内条目", "填写率", "较上轮"]
    table_rows: list[list[str]] = []
    prev_filled: int | None = None
    for h in history:
        rnd = h.get("round", 0)
        filled = h.get("filled", 0)
        total = h.get("total", 0)
        pct = f"{round(filled / total * 100)}%" if total else "—"
        delta = "—" if prev_filled is None else (f"+{filled - prev_filled}" if filled >= prev_filled else str(filled - prev_filled))
        table_rows.append([f"第 {rnd} 轮", str(filled), str(total), pct, delta])
        prev_filled = filled
    return SduiCardNode(
        id="resurvey-history", title=f"多轮复勘历史（共 {len(history)} 轮）",
        children=[SduiDataTableNode(id="resurvey-history-table", columns=cols, rows=table_rows)],
    )


def _build_gkclaw_card(state: dict[str, Any]) -> SduiCardNode | None:
    """GKCLAW 任务下发状态卡（task_dispatch 后出现）。
    展示 task_id / 链路状态 / dry-run 提示 / 现场 Web 入口 / 合并告警。"""
    m = collect_metrics(state)
    tid = m.get("gkclaw_task_id")
    if not tid:
        return None
    labels = {"planned": "已编排", "dispatched": "已下发", "accepted": "对端已导入",
              "staged_returned": "已收阶段回传", "completed": "已完成",
              "failed": "失败", "superseded": "已被新任务取代"}
    st = str(m.get("gkclaw_state", ""))
    badge = {"completed": "done", "failed": "fail"}.get(st, "run")
    children: list[SduiNode] = [
        SduiStatusBannerNode(id="gkclaw-banner", items=[
            SduiStatusItem(status=badge, text=f"{tid} · {labels.get(st, st)}"),  # type: ignore[arg-type]
        ]),
    ]
    bits: list[str] = []
    if m.get("gkclaw_dry_run"):
        bits.append("dry-run：任务包已生成未发送（设 AIDA_SEND_EMAIL=1 真发）")
    if m.get("gkclaw_items") is not None:
        bits.append(f"下发现场条目 {m['gkclaw_items']} 条")
    if m.get("gkclaw_web_url"):
        bits.append(f"现场 Web 入口：{m['gkclaw_web_url']}")
    if m.get("gkclaw_message"):
        bits.append(str(m["gkclaw_message"]))
    if bits:
        children.append(SduiAlertNode(id="gkclaw-info", tone="info",
                                      title="GKCLAW 邮件链路", message="；".join(bits)))
    return SduiCardNode(id="gkclaw-card", title="任务下发（GKCLAW）", children=children)


def _build_approval_card(state: dict[str, Any]) -> SduiCardNode | None:
    """审批流程状态卡（B6 · report_distribute 决策后出现）。
    通过→分发闭环 / 驳回→引导补勘 / 暂存→待处理。"""
    m = collect_metrics(state)
    status = m.get("approval_status")
    if not status:
        return None

    project_name = m.get("project_name", "")
    email_sent = m.get("email_sent")
    recipients = m.get("recipients", 0)

    if status == "approved":
        tone, badge_status = "success", "done"
        headline = "审批通过 · 已分发干系人"
        send_txt = (
            f"四件套已邮件分发给 {recipients} 位干系人，流程闭环。" if email_sent
            else f"审批通过，{recipients} 位干系人就绪（dry-run，设 AIDA_SEND_EMAIL=1 真发）。"
        )
        children: list[SduiNode] = [
            SduiStatusBannerNode(id="approval-banner", items=[
                SduiStatusItem(status=badge_status, text=f"{project_name} · {headline}"),  # type: ignore[arg-type]
            ]),
            SduiAlertNode(id="approval-msg", tone="success", title="流程闭环", message=send_txt),
        ]
    elif status == "rejected":
        tone = "danger"
        children = [
            SduiStatusBannerNode(id="approval-banner", items=[
                SduiStatusItem(status="fail", text=f"{project_name} · 审批驳回"),
            ]),
            SduiAlertNode(
                id="approval-msg", tone="warning", title="需补充勘测",
                message="评审驳回：请发起「补充勘测」意图，补齐缺失/不满足项的数据后重新生成报告再提交审批。",
            ),
        ]
    else:  # held
        tone = "warning"
        children = [
            SduiStatusBannerNode(id="approval-banner", items=[
                SduiStatusItem(status="pause", text=f"{project_name} · 审批暂存"),
            ]),
            SduiAlertNode(
                id="approval-msg", tone="info", title="暂未分发",
                message="四件套已保留，未分发。后续可随时再次触发审批分发。",
            ),
        ]

    return SduiCardNode(
        id="approval-card", title="审批与分发",
        tone=tone,  # type: ignore[arg-type]
        children=children,
    )


def _build_activity_timeline(state: dict[str, Any]) -> SduiCardNode | None:
    """右侧数据面板 · 执行动态（里程碑事件流，最新在上）。
    与中间「当前执行」LogStream 区分：此处是历史事件轴，那里是运行中实时尾巴。"""
    meaningful = _meaningful_logs(state)
    if not meaningful:
        return None
    recent = meaningful[-10:][::-1]  # 最新在上
    events: list[SduiTimelineEvent] = []
    for line in recent:
        lvl = _log_level(line)
        tone = {"ok": "success", "error": "error", "warn": "warning"}.get(lvl, "default")
        events.append(SduiTimelineEvent(label=line, tone=tone))  # type: ignore[arg-type]
    return SduiCardNode(
        id="activity", title="执行动态",
        children=[SduiTimelineNode(id="activity-tl", events=events)],
    )


def _build_macro_rail(state: dict[str, Any]) -> SduiMacroStepRailNode | None:
    """顶部宏观阶段条：把 15 个 micro step 折叠成 4 个大阶段（环境准备 / 方案识别 /
    现场勘测 / 报告分发），让用户始终知道「我在哪个大阶段」。意图感知：与当前意图
    无关的阶段（其所有 micro step 都不属于本意图）自动隐藏。"""
    by_key = {s.get("key", ""): s for s in (state.get("steps") or [])}
    if not by_key:
        return None

    # 当前意图涉及的 micro step 集合（与 build_stepper_for_intent 同口径）。
    # 注意：survey_work 也要过滤——scene_suggest_run 仅属 scene_suggest 意图，
    # 若按「全量」算会让「方案识别」阶段因它永不完成而卡在进行中。
    from .steps._intent_guard import STEP_INTENTS
    intent = (state.get("project") or {}).get("intent", "")
    if intent:
        relevant: set[str] | None = {"preflight", "intent_select"} | {
            k for k, ints in STEP_INTENTS.items() if intent in ints
        }
    else:
        relevant = None  # 还没选意图 → 全量展示

    macro_steps: list[SduiMacroStep] = []
    current_id: str | None = None
    for pid, title, hint, micro_keys in ZHGK_MACRO_PHASES:
        keys = [k for k in micro_keys if (relevant is None or k in relevant)]
        if not keys:
            continue  # 本意图不涉及该阶段 → 隐藏
        statuses = [
            (by_key.get(k) or {}).get("status", "pending") for k in keys
        ]
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

    if not macro_steps:
        return None
    # 无进行中阶段且全部完成 → 高亮最后一个阶段
    if current_id is None and macro_steps and all(s.status == "done" for s in macro_steps):
        current_id = macro_steps[-1].id

    return SduiMacroStepRailNode(id="macro-rail", steps=macro_steps, currentId=current_id)


def _build_status_banner(state: dict[str, Any]) -> SduiStatusBannerNode | None:
    """需要用户注意时的醒目状态条：HITL 等待 / 执行失败。
    运行中与已完成态不展示（header 徽标 + MacroStepRail 已足够），避免状态指示泛滥。"""
    if state.get("error"):
        return SduiStatusBannerNode(id="status-banner", items=[
            SduiStatusItem(status="fail", text=f"执行失败：{state['error']}"),
        ])
    hitl = state.get("hitl") or {}
    step = hitl.get("step")
    if step:
        name = ZHGK_STEP_NAMES.get(step, step)
        reason = (hitl.get("reason") or "").strip()
        text = f"等待你的操作 · {name}" + (f" — {reason}" if reason else "")
        return SduiStatusBannerNode(id="status-banner", items=[
            SduiStatusItem(status="pause", text=text),
        ])
    return None


def _build_running_card(state: dict[str, Any]) -> SduiCardNode | None:
    """运行中实时反馈卡：填补「某步正在跑但中间区一片空白」的信息真空。
    仅在有 step 处于 running（非 HITL）时出现：品牌横幅 + 最近 8 行日志尾巴。"""
    steps = state.get("steps") or []
    running = next((s for s in steps if s.get("status") == "running"), None)
    if not running:
        return None
    name = ZHGK_STEP_NAMES.get(running.get("key", ""), "执行中")
    tail = _meaningful_logs(state)[-8:]
    lines = [SduiLogLine(text=l, level=_log_level(l)) for l in tail]  # type: ignore[arg-type]
    children: list[SduiNode] = [
        SduiBannerNode(id="running-banner", message=f"正在执行 · {name}", tone="brand"),
    ]
    if lines:
        children.append(SduiLogStreamNode(id="running-log", lines=lines))
    return SduiCardNode(id="running-card", children=children)


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

    # 顶部宏观阶段条：4 大阶段导航，让用户始终知道在哪个阶段（micro 细节看右侧 Stepper）
    macro_rail = _build_macro_rail(state)
    if macro_rail:
        nodes.append(macro_rail)

    # 醒目状态条：HITL 等待 / 失败时强提示（运行/完成态不显示，避免泛滥）
    status_banner = _build_status_banner(state)
    if status_banner:
        nodes.append(status_banner)

    # HITL 置顶通栏：待确认第一时间呈现（id=hitl-card；前端 #4 据此路由到左侧会话）
    hitl_card = build_hitl(state, card_title="需要补充", default_choice_title="请选择")
    if hitl_card:
        nodes.append(hitl_card)

    # 中间主区：业务数据卡（各段自行判断有无数据，None 跳过）
    #   运行中实时卡置顶 → 填补「正在跑但中间空白」的信息真空
    center_children: list[SduiNode] = [
        n for n in (
            _build_running_card(state),
            _build_metrics_card(state),
            _build_filter_preview(state),
            _build_assessment_panel(state),
            _build_issue_table(state),
            _build_resurvey_history(state),
            _build_gkclaw_card(state),
            _build_alerts(state),
            _build_approval_card(state),
            build_artifacts(state, input_file_keys=("boq_xlsx", "presets_docx")),
            _build_summary(state),
        ) if n
    ]

    # 右侧数据面板：意图感知 Stepper（竖向）+ 执行动态时间轴
    from .steps._intent_guard import STEP_INTENTS
    intent = (state.get("project") or {}).get("intent", "")
    right_children: list[SduiNode] = [
        build_stepper_for_intent(
            state,
            step_names=ZHGK_STEP_NAMES,
            intent=intent,
            intent_step_map=STEP_INTENTS,
            always_show={"preflight", "intent_select"},
            orientation="vertical",
        ),
    ]
    activity = _build_activity_timeline(state)
    if activity:
        right_children.append(activity)

    nodes.append(SduiRowNode(
        id="dashboard-row", gap="md", align="start", wrap=True,
        children=[
            # 5:3（≈62/38）—— 右栏从原 29% 加宽到 38%，缓解 15 步竖向 Stepper 被挤压
            SduiStackNode(id="dash-center", gap="sm", flex=5, children=center_children),
            SduiStackNode(id="dash-right", gap="sm", flex=3, children=right_children),
        ],
    ))

    doc = SduiDocument(
        root=SduiStackNode(id="zhgk-root", gap="sm", children=nodes),
        meta={"skill": "zhgk", "run_id": state.get("run_id", "")},
    )
    return dump_sdui_json(doc)
