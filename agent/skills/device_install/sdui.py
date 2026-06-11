"""
device_install SDUI 投影器 · SkillState → SduiDocument

通用段（stepper / 进度环 / 产物栏 / HITL / 日志）走 agent.sdui.projector_base；
本文件只保留设备安装自有业务：KPI 指标、任务进展表等。
纯函数：project(state) → dict，无副作用、不读盘（数据来自 state.metrics，由各 step 写入）。

Metrics 键约定（di_ 命名空间，由 task_store.task_summary 写入）：
  di_total / di_done / di_in_progress / di_pending / di_dispatched / di_completion_pct
  di_by_unit_rows（list[list]）/ di_task_rows（list[list]）
其他 step 自有指标：parsed_tasks · dispatched_count · sn_tables · sn_devices · esn_devices · completed_now
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from agent.sdui.builder import (
    SduiNode, SduiStackNode, SduiRowNode, SduiCardNode,
    SduiStatisticRowItem, SduiStatisticRowNode,
    SduiAlertNode,
    SduiDonutChartNode, SduiDonutSegment,
    SduiDataTableNode, SduiDataTableColumn,
    SduiArtifactGridNode, SduiArtifactItem,
    SduiCardHeaderAction, SduiResetSession,
    SduiDashboardLayoutNode,
    dump_sdui_json, SduiDocument,
)
from agent.sdui.projector_base import (
    collect_metrics, overall_status,
    artifact_kind,
    build_header, build_stepper,
    build_artifacts, build_hitl, build_editable_table,
)

from .go_back import can_go_back
from .pipeline import DI_STEP_NAMES, DI_STEP_ORDER


def _build_progress_donut(state: dict[str, Any]) -> SduiDonutChartNode:
    """进度环：有任务指标时用任务完成率（对齐 HTML totalProg），否则用流水线步骤比例。"""
    m = collect_metrics(state)
    if m.get("di_total"):
        pct = int(m.get("di_completion_pct", 0) or 0)
    else:
        steps = state.get("steps") or []
        total = len(DI_STEP_ORDER)
        done = sum(1 for s in steps if s.get("status") == "completed")
        pct = int(round(done / total * 100) if total else 0)
    tone = _donut_progress_color(pct)
    return SduiDonutChartNode(
        id="donut",
        segments=[
            SduiDonutSegment(label="已完成", value=pct, color=tone),
            SduiDonutSegment(label="剩余", value=max(0, 100 - pct), color="subtle"),
        ],
        centerLabel="进度", centerValue=f"{pct}%",
    )


def _kpi_items(state: dict[str, Any]) -> list[SduiStatisticRowItem]:
    m = collect_metrics(state)
    items: list[SduiStatisticRowItem] = []
    if "di_total" in m:
        items.append(SduiStatisticRowItem(title="任务总数", value=f"{m.get('di_total', 0)} 条", color="accent"))
        items.append(SduiStatisticRowItem(title="已下发", value=f"{m.get('di_dispatched', 0)} 条", color="subtle"))
        done = m.get("di_done", 0)
        total = m.get("di_total", 0) or 0
        items.append(SduiStatisticRowItem(
            title="完成率",
            value=f"{m.get('di_completion_pct', 0)}%（{done}/{total}）",
            color="success" if total and done == total else "warning",
        ))
    if m.get("sn_devices"):
        items.append(SduiStatisticRowItem(title="SN设备", value=f"{m['sn_devices']} 台", color="subtle"))
    if m.get("esn_devices"):
        items.append(SduiStatisticRowItem(title="ESN已采集", value=f"{m['esn_devices']} 台", color="accent"))
    return items


def _plan_receive_done(state: dict[str, Any]) -> bool:
    """上游实施计划已接收解析（plan_receive 完成）→ 才展示黄金指标。"""
    for s in state.get("steps") or []:
        if s.get("key") == "plan_receive" and s.get("status") == "completed":
            return True
    return False


def _esn_fill_done(state: dict[str, Any]) -> bool:
    """ESN 已提交且 esn_fill 步完成 → 展示「任务进展」。"""
    for s in state.get("steps") or []:
        if s.get("key") == "esn_fill" and s.get("status") == "completed":
            return True
    return False


def _in_build_until_esn_done(state: dict[str, Any]) -> bool:
    """任务生成确认后、ESN 完工前（含 full_restart 重放间隙）。"""
    if not _plan_receive_done(state):
        return False
    return not _esn_fill_done(state)


def _build_metrics_card(state: dict[str, Any]) -> SduiCardNode | None:
    """黄金指标卡：进度环 + KPI 行。
    全量任务未生成前（含责任人填报 HITL）不展示——此时 KPI 无业务意义。
    宽表 HITL（责任人/任务/下发/ESN）及下发后至 ESN 完工前的重放间隙均不展示。
    KPI 单行时（≤3 项）让进度环与卡片垂直居中；换行时顶端对齐。"""
    hitl = state.get("hitl") or {}
    if hitl.get("step") in ("task_dispatch", "esn_fill"):
        return None
    # 计划下发提交后 → SN/ESN 完工前：避免重跑瞬间闪出黄金指标
    if _in_build_until_esn_done(state):
        return None
    # 任务进展视图（ESN 完工后）已用 DataTable 展示进度，不再叠加黄金指标
    if _show_task_progress(state):
        return None
    if not _plan_receive_done(state):
        return None
    if not (state.get("steps") or []):
        return None
    items = _kpi_items(state)
    if not items:
        total = len(DI_STEP_ORDER)
        done = sum(1 for s in state["steps"] if s.get("status") == "completed")
        items = [SduiStatisticRowItem(title="已完成步骤", value=f"{done}/{total}")]
    align = "center" if len(items) <= 3 else "start"
    return SduiCardNode(
        id="golden-metrics", title="黄金指标",
        children=[SduiRowNode(align=align, gap="md", children=[  # type: ignore[arg-type]
            _build_progress_donut(state),
            SduiStatisticRowNode(id="kpi-row", items=items, flex=2),
        ])],
    )


def _pipeline_done(state: dict[str, Any]) -> bool:
    """主建设流水线全部完成（对齐参考 HTML currentStage > 5）。"""
    status_key, _ = overall_status(state, DI_STEP_ORDER, paused_badge="待补充")
    return status_key == "done"


def _show_task_progress(state: dict[str, Any]) -> bool:
    """ESN 填写完成后展示任务进展表。"""
    return _esn_fill_done(state) or _pipeline_done(state)


def _build_di_stepper(state: dict[str, Any]) -> SduiCardNode:
    """执行进度：Stepper 横向步骤条（组件库 SduiStepper horizontal）。"""
    base = build_stepper(state, step_names=DI_STEP_NAMES, orientation="horizontal")
    return SduiCardNode(
        id="stepper",
        title="执行进度",
        headerAction=SduiCardHeaderAction(
            label="重置会话",
            variant="primary",
            action=SduiResetSession(),
        ),
        children=list(base.children or []),
    )


def _build_completion_banner(state: dict[str, Any]) -> SduiAlertNode | None:
    """主线完成提示（Alert · 组件库标准）。"""
    if not _pipeline_done(state):
        return None
    m = collect_metrics(state)
    total = m.get("di_total", 0)
    done = m.get("di_done", 0)
    return SduiAlertNode(
        id="di-completion-alert",
        tone="success",
        title="设备安装流程已完成",
        message=(
            f"主建设流水线已全部完成，共 {total} 项任务（已完成 {done} 项）。"
            "请在下方「任务进展」表中查看各任务状态。"
        ),
    )


def _donut_progress_color(pct: int) -> Literal["success", "warning", "error"]:
    """圆环进度色：对齐 ProgressBar 语义，不用 accent（蓝）；Donut 用 error 表红。"""
    if pct >= 80:
        return "success"
    if pct >= 40:
        return "warning"
    return "error"


def _build_task_progress_overview(rows: list[dict[str, Any]]) -> SduiRowNode:
    """任务进展概览：DonutChart + StatisticRow（组件库标准组合）。"""
    total = len(rows)
    done = sum(1 for r in rows if str(r.get("status")) == "已完成")
    in_prog = sum(1 for r in rows if str(r.get("status")) == "进行中")
    pct = int(done / total * 100) if total else 0
    tone = _donut_progress_color(pct)
    return SduiRowNode(
        id="task-progress-overview",
        align="center",
        gap="md",
        children=[  # type: ignore[arg-type]
            SduiDonutChartNode(
                id="task-progress-donut",
                segments=[
                    SduiDonutSegment(label="已完成", value=pct, color=tone),
                    SduiDonutSegment(label="剩余", value=max(0, 100 - pct), color="subtle"),
                ],
                centerLabel="完成率", centerValue=f"{pct}%",
            ),
            SduiStatisticRowNode(
                id="task-progress-kpi",
                flex=2,
                items=[
                    SduiStatisticRowItem(title="任务总数", value=f"{total} 条", color="accent"),
                    SduiStatisticRowItem(title="已完成", value=f"{done} 条", color="success"),
                    SduiStatisticRowItem(title="进行中", value=f"{in_prog} 条", color="warning"),
                ],
            ),
        ],
    )


def _build_task_progress_table(state: dict[str, Any]) -> SduiCardNode | None:
    """任务进展：概览环 + KPI + 只读 DataTable（progress/status 列走组件库单元格）。"""
    if not _show_task_progress(state):
        return None
    m = collect_metrics(state)
    rows: list[dict[str, Any]] = list(m.get("di_dispatch_progress_rows") or [])
    if not rows:
        return None
    columns = [
        SduiDataTableColumn(key="unit", label="管理单元", type="text", width=110),
        SduiDataTableColumn(key="activity_id", label="活动ID", type="text", width=80),
        SduiDataTableColumn(key="activity_name", label="活动名称", type="text"),
        SduiDataTableColumn(key="principal", label="责任人", type="text", width=90),
        SduiDataTableColumn(key="end_date", label="结束日期", type="text", width=110),
        SduiDataTableColumn(key="status", label="状态", type="status", width=90),
        SduiDataTableColumn(key="progress", label="进度", type="progress", width=120),
    ]
    children: list[SduiNode] = [_build_task_progress_overview(rows)]
    if _show_go_back_toolbar(state):
        children.append(_build_back_toolbar_dt())
    children.append(SduiDataTableNode(
        id="task-table-dt",
        title=f"计划下发任务明细（{len(rows)} 条）",
        columns=columns,
        rows=rows,
        editable=False,
        rowKey="id",
    ))
    return SduiCardNode(id="task-table", title="任务进展", children=children)


def _build_back_toolbar_dt() -> SduiDataTableNode:
    """返回上一步（skill 内 run-patch · 复用 DataTable 提交通道，不扩展系统 SDUI）。"""
    return SduiDataTableNode(
        id="go-back-toolbar",
        columns=[SduiDataTableColumn(key="_noop", label="", type="text", width=1)],
        rows=[],
        editable=True,
        submitMode="run-patch",
        stepId="go_back",
        submitLabel="返回上一步",
    )


def _strip_edit_card_text_hints(card: SduiCardNode) -> SduiCardNode:
    """去掉编辑卡顶部 Text 说明（reason/subtitle）；计划下发表格标题已自解释。"""
    kept: list[SduiNode] = [
        c for c in (card.children or []) if getattr(c, "type", None) != "Text"
    ]
    if len(kept) == len(card.children or []):
        return card
    return SduiCardNode(id=card.id, title=card.title, children=kept)


def _show_go_back_toolbar(state: dict[str, Any]) -> bool:
    """是否投影「返回上一步」工具条（ESN 填写步 / 流水线完成后不展示）。"""
    if _pipeline_done(state):
        return False
    hitl_step = (state.get("hitl") or {}).get("step")
    if hitl_step == "esn_fill":
        return False
    return can_go_back(state)


def _build_editable_table_di(state: dict[str, Any]) -> SduiCardNode | None:
    """在线编辑 HITL；可回退时在主表工具栏上方追加「返回上一步」条（ESN 填写步除外）。"""
    card = build_editable_table(state)
    if not card:
        return card
    hitl_step = (state.get("hitl") or {}).get("step")
    if hitl_step == "task_dispatch":
        card = _strip_edit_card_text_hints(card)
    if _show_go_back_toolbar(state):
        children: list[SduiNode] = list(card.children or [])
        children.insert(0, _build_back_toolbar_dt())
        return SduiCardNode(id=card.id, title=card.title, children=children)
    return card


def _build_step_result_artifacts(state: dict[str, Any]) -> SduiCardNode | None:
    """HITL 步骤的「作业结果」卡：展示当前步预生成的产物（任务生成→全量任务 / 计划下发→实施计划）。
    路径取自 hitl.need_edit.result_artifacts（由对应 step 在 check_inputs 里预生成后下发）。"""
    hitl = state.get("hitl") or {}
    spec = hitl.get("need_edit") or {}
    paths = [p for p in (spec.get("result_artifacts") or []) if isinstance(p, str) and p]
    if not paths:
        return None
    items = [
        SduiArtifactItem(
            id=f"step-res-{i}", label=Path(p).name, path=p,
            kind=artifact_kind(p),  # type: ignore[arg-type]
            status="ready",
        )
        for i, p in enumerate(paths)
    ]
    return SduiCardNode(
        id="step-result-card", title="作业结果",
        children=[SduiArtifactGridNode(id="step-result-grid", mode="output", artifacts=items)],
    )


def _sdui_meta(state: dict[str, Any]) -> dict[str, Any]:
    """SDUI 文档 meta：前端布局策略（不写死 skillId）。"""
    return {
        "skill": "device_install",
        "run_id": state.get("run_id", ""),
        "route_hitl_edit": "workbench",
        "workbench_class": "di",
    }


def project(state: dict[str, Any]) -> dict[str, Any]:
    """SkillState → SduiDocument（顶栏 header + 横向 Stepper + 主内容区）。"""
    status_key, _ = overall_status(state, DI_STEP_ORDER, paused_badge="待补充")
    is_idle = status_key == "idle"

    if is_idle:
        doc = SduiDocument(
            root=SduiStackNode(id="di-root", gap="sm", children=[]),
            meta={**_sdui_meta(state), "suppress_idle_panel": True},
        )
        return dump_sdui_json(doc)

    # 顶部全宽：项目名 + 状态徽标 · 横向步骤条
    nodes: list[SduiNode] = [
        build_header(
            state,
            default_name="设备安装",
            cta_map={},
            step_order=DI_STEP_ORDER,
            paused_badge="待补充",
        ),
        _build_di_stepper(state),
    ]

    # 文件 / 确认型 HITL（在线编辑型走下方编辑卡）
    hitl = state.get("hitl") or {}
    if hitl.get("step") and not hitl.get("need_edit"):
        hitl_card = build_hitl(state, card_title="需要补充", default_choice_title="请选择")
        if hitl_card:
            nodes.append(hitl_card)

    editable = _build_editable_table_di(state)
    if editable:
        # 在线编辑（计划下发 / ESN 等）：宽表需要全宽，单列呈现
        nodes.append(editable)
    else:
        # 结果 / 进度 / 运行视图：DashboardLayout 5:2 填充横向空间，避免单列稀疏
        main_content = [
            n for n in (
                _build_completion_banner(state),
                _build_task_progress_table(state),
                _build_metrics_card(state),
            ) if n
        ]
        step_result = _build_step_result_artifacts(state)
        side_content = [n for n in (step_result or build_artifacts(state),) if n]
        if main_content and side_content:
            nodes.append(SduiDashboardLayoutNode(
                id="di-dashboard", main=main_content, side=side_content,
            ))
        else:
            combined = main_content + side_content
            if combined:
                nodes.append(SduiStackNode(id="dash-main", gap="sm", children=combined))

    doc = SduiDocument(
        root=SduiStackNode(id="di-root", gap="sm", children=nodes),
        meta=_sdui_meta(state),
    )
    return dump_sdui_json(doc)
