"""
模板 · SDUI 投影器。复制为 agent/skills/<name>/sdui.py 后按 ✏️ 注释改造。

通用段（header / stepper / 进度环 / 产物栏 / HITL / 日志摘要）全部走
agent.sdui.projector_base —— 不用抄。你只需改：
  ① 步骤名表 XXX_STEP_NAMES + CTA 指令 XXX_CTA
  ② _kpi_items（按 step 写进 metrics 的键填黄金指标）
  ③ _summary_bits（按 metrics 合成摘要句）
  ④ 选用下方示例添加业务专属面板（评估面板 / 告警 / 清单表 / 时间轴）

接入三步：① 改本文件 ② skill.py 设 sdui_projector = staticmethod(project) ③ 前端零改动。
规范见 agent/docs/SDUI.md（§3.3 投影器只能读 step 真写进 metrics/state 的键）。

HITL 置顶模式（推荐）：
  有 HITL 挂起时第一时间呈现确认卡，不让用户先滚过 Stepper 才发现。
  见下方 project() 注释。
"""
from __future__ import annotations
from typing import Any

from agent.sdui.builder import (
    SduiDocument, SduiNode, SduiStackNode, SduiCardNode,
    SduiStatisticRowItem, SduiAlertNode,
    dump_sdui_json,
)
from agent.sdui.projector_base import (
    collect_metrics, overall_status,
    build_header, build_stepper, build_metrics_card,
    build_artifacts, build_summary_card, build_hitl,
    # ── 选用型辅助构件 ─────────────────────────────────────
    # build_number_cards,      # Row of NumberCard — 突出单值 KPI
    # build_assessment_panel,  # 五值评估专用：NumberCards + Donut + Bar + Alert
    # build_data_table,        # 从 metrics 里取 rows_key 渲染 Table 卡片
)

# ✏️ 替换为你的 step key 和中文名（顺序即展示顺序）
XXX_STEP_NAMES: dict[str, str] = {
    "example_step": "示例步骤",
    # "step_2": "第二步",
}
XXX_STEP_ORDER = list(XXX_STEP_NAMES.keys())

# ✏️ CTA：{status_key: (按钮文案, variant, 指令)}；running 态自动不显示按钮
XXX_CTA: dict[str, tuple[str, str, str]] = {
    "idle":   ("启动", "primary", "/start_xxx"),
    "paused": ("提交并继续", "primary", "/resume_xxx"),
    "done":   ("查看结果", "primary", "/view_result"),
    "failed": ("重试", "primary", "/retry_xxx"),
}


def _kpi_items(state: dict[str, Any]) -> list[SduiStatisticRowItem]:
    """✏️ 按你的 step metrics 键填 KPI（为空时黄金指标卡回退「已完成步骤 x/total」）。"""
    m = collect_metrics(state)
    items: list[SduiStatisticRowItem] = []
    # 示例：fill_pct 由某 step 的 metrics 写入
    # if "fill_pct" in m:
    #     items.append(SduiStatisticRowItem(title="填写率", value=f"{m['fill_pct']}%", color="accent"))
    return items


def _summary_bits(state: dict[str, Any]) -> list[str]:
    """✏️ 按 metrics 合成阶段摘要句（为空时回退最新日志）。"""
    m = collect_metrics(state)
    bits: list[str] = []
    # 示例：
    # if "fill_pct" in m:
    #     bits.append(f"填写率 {m['fill_pct']}%（{m.get('filled','?')}/{m.get('total','?')} 项）")
    return bits


# ── 示例：业务专属面板（选用 / 删除不需要的）─────────────────────────────────────

# ── 示例 A：条件告警横幅（SduiAlertNode）────────────────────────────
# def _build_warn_banner(state: dict[str, Any]) -> SduiAlertNode | None:
#     """有错误/警告时显示 Alert 横幅，紧迫感优先于其他内容。"""
#     m = collect_metrics(state)
#     err_count = m.get("error_count", 0) or 0
#     if not err_count:
#         return None
#     return SduiAlertNode(
#         id="warn-banner", tone="warning",
#         title=f"{err_count} 处警告",
#         message=f"发现 {err_count} 处异常，请查看下方清单。",
#     )
#
# ── 示例 B：五值评估面板（build_number_cards + DonutChart + BarChart）───────────
# 以智慧工勘为例，metrics 里有 assess_total / assess_满足 / assess_不满足 等：
#
# def _build_assessment(state: dict[str, Any]) -> SduiCardNode | None:
#     """引用 projector_base.build_assessment_panel 完成五值面板。"""
#     from agent.sdui.projector_base import build_assessment_panel
#     return build_assessment_panel(
#         state,
#         total_key="assess_total",
#         value_keys=[
#             ("满足",    "assess_满足",    "success"),
#             ("不满足",  "assess_不满足",  "error"),
#             ("不涉及",  "assess_不涉及",  "subtle"),
#             ("未勘测",  "assess_未勘测",  "warning"),
#             ("无法识别","assess_无法识别","warning"),
#         ],
#         alert_keys=[
#             ("assess_无法识别", "error",   "存在 {count} 项无法识别，建议复勘。"),
#             ("assess_不满足",  "warning",  "存在 {count} 项不满足，请制定整改方案。"),
#         ],
#         title="AI 五值评估",
#         rate_label="满足率",
#     )
#
# ── 示例 C：明细表（build_data_table / SduiTableNode）────────────────────────
# step 需把 rows 写进 metrics：metrics={"issue_rows": [["高", "空调故障", "运行中"], ...]}
#
# def _build_issue_table(state: dict[str, Any]) -> SduiCardNode | None:
#     from agent.sdui.projector_base import build_data_table
#     return build_data_table(
#         state,
#         rows_key="issue_rows",
#         headers=["等级", "问题描述", "整改建议"],
#         title="问题清单",
#         max_rows=15,
#         tone="warning",
#     )
#
# ── 示例 D：Timeline（执行日志时间轴）──────────────────────────────────────────
# step 需写 metrics={"timeline_events": [{"label":"步骤A完成","time":"14:03","tone":"success"},...]}
#
# def _build_timeline(state: dict[str, Any]) -> SduiCardNode | None:
#     from agent.sdui.builder import SduiTimelineNode, SduiTimelineEvent
#     m = collect_metrics(state)
#     events_raw: list[dict] = m.get("timeline_events") or []
#     if not events_raw:
#         return None
#     events = [SduiTimelineEvent(**e) for e in events_raw]
#     return SduiCardNode(
#         id="exec-timeline", title="执行动态",
#         children=[SduiTimelineNode(id="timeline", events=events)],
#     )


def project(state: dict[str, Any]) -> dict[str, Any]:
    """SkillState → SduiDocument JSON-compatible dict（纯函数 · 无副作用 · 可单测）。

    推荐布局顺序（按信息优先级）：
      1. header           — 项目名 + 状态 + CTA
      2. [HITL]           — 置顶：有挂起时第一时间呈现（不要放最后）
      3. stepper          — 进度时间轴
      4. metrics_card     — 黄金指标（进度环 + KPI 行）
      5. [业务专属面板]   — 评估面板 / 告警表 / 清单表（各段自判断是否有数据）
      6. artifacts        — 已上传文件 + 作业结果产物
      7. summary          — 阶段摘要 / 最新日志
    """
    nodes: list[SduiNode] = [
        build_header(state, default_name="xxx 模块", cta_map=XXX_CTA, step_order=XXX_STEP_ORDER),
    ]

    # HITL 置顶（有挂起时立刻呈现）
    hitl = build_hitl(state)
    if hitl:
        nodes.append(hitl)

    nodes.append(build_stepper(state, step_names=XXX_STEP_NAMES))

    for node in (
        build_metrics_card(state, step_order=XXX_STEP_ORDER, kpi_items=_kpi_items(state)),
        # _build_warn_banner(state),   # 示例 A（Alert）
        # _build_assessment(state),    # 示例 B（五值面板）
        # _build_issue_table(state),   # 示例 C（Table 清单）
        # _build_timeline(state),      # 示例 D（Timeline）
        build_artifacts(state),          # ✏️ 有输入文件栏：input_file_keys=("boq_xlsx",)
        build_summary_card(_summary_bits(state), state),
    ):
        if node:
            nodes.append(node)

    doc = SduiDocument(
        root=SduiStackNode(id="xxx-root", gap="sm", children=nodes),   # ✏️ 改 id
        meta={"skill": "xxx", "run_id": state.get("run_id", "")},      # ✏️ 改 skill 名
    )
    return dump_sdui_json(doc)
