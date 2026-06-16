"""
device_install SDUI 投影器 · SkillState → SduiDocument

通用段（stepper / 进度环 / 产物栏 / HITL / 日志）走 agent.sdui.projector_base；
本文件只保留设备安装自有业务：KPI 指标、任务进展表等。
纯函数：project(state) → dict，无副作用；数据来自 state.metrics / state.steps。
ESN 完工后作业结果会补扫 Output 目录（glob 产物），确保完工清单等文件出现在「作业结果」。

Metrics 键约定（di_ 命名空间，由 task_store.task_summary 写入）：
  di_total / di_done / di_in_progress / di_pending / di_dispatched / di_completion_pct
  di_by_unit_rows（list[list]）/ di_task_rows（list[list]）
其他 step 自有指标：parsed_tasks · dispatched_count · sn_tables · sn_devices · esn_devices · completed_now
"""
from __future__ import annotations

import re
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
    SduiTabGroupNode, SduiTabPanel,
    SduiGanttChartNode, SduiGanttRow,
    dump_sdui_json, SduiDocument,
)
from agent.sdui.projector_base import (
    collect_metrics, overall_status,
    artifact_kind,
    build_stepper,
    build_hitl, build_editable_table,
)

from .go_back import can_go_back
from .pipeline import DI_STEP_NAMES, DI_STEP_ORDER
from .bridge import get_device_install_root
from .path_config import get_output_dir, output_rel

# ESN 完工后作业结果扫描（补全 step 记录未携带的 glob 产物，如多张 SN/完工清单）
_OUTPUT_SCAN_PATTERNS = (
    "责任人信息表.xlsx",
    "设备安装实施计划.xlsx",
    "SN扫码表_*.xlsx",
    "完工清单_*.xlsx",
    "设备安装完工报告.xlsx",
)
_ARTIFACT_SORT_PREFIX = (
    "责任人信息表",
    "设备安装实施计划",
    "SN扫码表",
    "完工清单",
    "设备安装完工报告",
)


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
    """实施计划已生成（tasks_generate 完成）→ 才展示黄金指标。"""
    for s in state.get("steps") or []:
        if s.get("key") == "tasks_generate" and s.get("status") == "completed":
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


def _sanitize_preflight_log_line(line: str) -> str | None:
    """环境预检 log_tail：仅保留设计稿 6 行，丢弃历史 LLM 摘要/思考链残留。"""
    s = str(line or "").strip()
    if not s:
        return None
    noise = (
        "redacted_thinking", "说明提到", "用户要求", "不要加标号",
        "已解析任务数", "主建设流程解析", "AI 摘要", "整体状态为",
        "建议下一步", "预检结论", "勾选下发",
    )
    if any(n in s for n in noise):
        return None
    if "正在扫描设备安装环境" in s:
        return "正在扫描设备安装环境…"
    if "正在校验上游交付计划表" in s:
        return "正在校验上游交付计划表…"
    if "LLM 摘要跳过" in s:
        return "LLM 摘要跳过"
    m = re.match(r"^([✓√✗])\s*(交付计划表|设备位置表|到货信息表)[:：]\s*(.+)$", s)
    if m:
        mark = "√" if m.group(1) in ("√", "✓") else "✗"
        return f"{mark} {m.group(2)}：{m.group(3).strip()}"
    return None


def _sanitize_stepper_logs(state: dict[str, Any], stepper_card: SduiCardNode) -> SduiCardNode:
    """设备安装：步骤条不嵌 log_tail（逐节点日志在左栏独立 AIDA 卡片展示）。"""
    children = list(stepper_card.children or [])
    if not children or children[0].type != "Stepper":
        return stepper_card
    stepper = children[0]
    steps = [st.model_copy(update={"detail": None}) for st in (stepper.steps or [])]
    new_stepper = stepper.model_copy(update={"steps": steps})
    return stepper_card.model_copy(update={"children": [new_stepper]})


def _build_di_stepper(state: dict[str, Any]) -> SduiCardNode:
    """执行进度：Stepper 横向步骤条（组件库 SduiStepper horizontal）。"""
    base = build_stepper(state, step_names=DI_STEP_NAMES, orientation="horizontal")
    base = _sanitize_stepper_logs(state, base)
    return SduiCardNode(
        id="stepper",
        title="设备安装 · 执行进度",
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


def _build_task_progress_table(state: dict[str, Any]) -> SduiDataTableNode | None:
    """任务进展：组件库 DataTable（Tier B 展示/编辑双模式 · status/progress 列）。"""
    if not _show_task_progress(state):
        return None
    m = collect_metrics(state)
    rows: list[dict[str, Any]] = list(m.get("di_dispatch_progress_rows") or [])
    if not rows:
        return None
    columns = [
        SduiDataTableColumn(key="unit", label="管理单元", type="text", width=110),
        SduiDataTableColumn(key="activity_name", label="活动名称", type="text", width=168, paddingLeft=16),
        SduiDataTableColumn(key="principal", label="责任人", type="text", width=72),
        SduiDataTableColumn(key="end_date", label="结束日期", type="text", width=110),
        SduiDataTableColumn(key="status", label="状态", type="status", width=90),
        SduiDataTableColumn(key="progress", label="进度", type="progress", width=140),
    ]
    return SduiDataTableNode(
        id="task-table-dt",
        title="任务进展",
        columns=columns,
        rows=rows,
        editable=False,
        dualMode=True,
        patchAction="task_progress",
        rowKey="id",
        pageSize=10,
        backLabel="返回上一步" if _show_go_back_toolbar(state) else None,
        backStepId="go_back",
    )


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


def _flatten_edit_card(card: SduiCardNode) -> SduiNode:
    """去掉外层 Card（如 card_title「指派责任人」），保留 Alert 提示 + DataTable 单层。"""
    hints: list[SduiNode] = []
    table: SduiNode | None = None
    for c in card.children or []:
        t = getattr(c, "type", None)
        if t == "DataTable":
            table = c
        elif t == "Alert":
            hints.append(c)
    if table is None:
        return card
    if not hints:
        return table
    return SduiStackNode(id=f"{card.id}-flat", gap="sm", children=[*hints, table])


def _strip_edit_card_text_hints(card: SduiCardNode) -> SduiCardNode:
    """去掉编辑卡顶部 Text 说明（reason/subtitle）；计划下发表格标题已自解释。"""
    kept: list[SduiNode] = [
        c for c in (card.children or []) if getattr(c, "type", None) != "Text"
    ]
    if len(kept) == len(card.children or []):
        return card
    return SduiCardNode(id=card.id, title=card.title, children=kept)


def _as_row_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _build_gantt_from_rows(rows: list[Any]) -> SduiGanttChartNode | None:
    """need_edit.rows → 只读 GanttChart（按管理单元 group 分组）。"""
    gantt_rows: list[SduiGanttRow] = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        start = _as_row_str(r.get("start_date") or r.get("start"))
        end = _as_row_str(r.get("end_date") or r.get("end"))
        if not start or not end:
            continue
        label = _as_row_str(r.get("activity_name") or r.get("label")) or f"任务 {i + 1}"
        gantt_rows.append(
            SduiGanttRow(
                id=_as_row_str(r.get("id")) or f"gantt-{i}",
                label=label,
                group=_as_row_str(r.get("unit")) or None,
                start=start,
                end=end,
                status=_as_row_str(r.get("status")) or None,
            )
        )
    if not gantt_rows:
        return None
    return SduiGanttChartNode(id="plan-gantt", rows=gantt_rows)


def _wrap_table_gantt_tabs(flat: SduiNode, rows: list[Any], hitl_step: str) -> SduiNode:
    """表格 + 甘特图双页签（甘特只读；编辑/提交仍在表格页）。"""
    gantt = _build_gantt_from_rows(rows)
    if not gantt:
        return flat
    return SduiTabGroupNode(
        id=f"view-tabs-{hitl_step}",
        activeTab="table",
        keepAlive=True,
        tabs=[
            SduiTabPanel(id="table", label="表格", children=[flat]),
            SduiTabPanel(id="gantt", label="甘特图", children=[gantt]),
        ],
    )


def _show_go_back_toolbar(state: dict[str, Any]) -> bool:
    """是否投影独立「返回上一步」工具条（ESN 填写步用表头内嵌按钮；流水线完成后不展示）。"""
    if _pipeline_done(state):
        return False
    hitl_step = (state.get("hitl") or {}).get("step")
    if hitl_step == "esn_fill":
        return False
    return can_go_back(state)


def _build_editable_table_di(state: dict[str, Any]) -> SduiNode | None:
    """在线编辑 HITL；计划下发/ESN 填写仅保留 DataTable 一层；可回退时在主表上方追加工具条。"""
    card = build_editable_table(state)
    if not card:
        return None
    hitl_step = (state.get("hitl") or {}).get("step")
    if hitl_step in ("principal_fill", "tasks_generate", "task_dispatch", "esn_fill"):
        spec = (state.get("hitl") or {}).get("need_edit") or {}
        rows = spec.get("rows") or []
        # 计划下发无待下发条目时保留 Card + subtitle，避免界面「什么都没有」
        keep_hints = hitl_step == "task_dispatch" and not rows
        if not keep_hints:
            card = _strip_edit_card_text_hints(card)
        if keep_hints:
            extras: list[SduiNode] = []
            if _show_go_back_toolbar(state):
                extras.append(_build_back_toolbar_dt())
            if extras:
                return SduiStackNode(id=f"edit-stack-{hitl_step}", gap="sm", children=[*extras, card])
            return card
        flat = _flatten_edit_card(card)
        if hitl_step in ("tasks_generate", "task_dispatch") and rows:
            flat = _wrap_table_gantt_tabs(flat, rows, hitl_step)
        extras: list[SduiNode] = []
        if _show_go_back_toolbar(state):
            extras.append(_build_back_toolbar_dt())
        if not extras:
            return flat
        return SduiStackNode(id=f"edit-stack-{hitl_step}", gap="sm", children=[*extras, flat])
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


def _artifact_sort_key(path: str) -> tuple[int, str]:
    name = Path(path).name
    for i, prefix in enumerate(_ARTIFACT_SORT_PREFIX):
        if name.startswith(prefix):
            return (i, name)
    return (len(_ARTIFACT_SORT_PREFIX), name)


def _norm_artifact_path(path: str) -> str:
    return path.replace("\\", "/")


def _collect_di_artifact_paths(state: dict[str, Any]) -> list[str]:
    """汇总主建设流水线作业产物：已完成 step 记录 + ESN 完工后扫 Output 目录（glob 产物）。"""
    seen: set[str] = set()
    paths: list[str] = []

    def _add(p: str) -> None:
        norm = _norm_artifact_path(p)
        if norm and norm not in seen:
            seen.add(norm)
            paths.append(p)

    # 每步取最后一次 completed 记录（resume 重跑时以最新为准）
    latest: dict[str, dict[str, Any]] = {}
    for rec in state.get("steps") or []:
        if rec.get("status") != "completed":
            continue
        key = str(rec.get("key") or "")
        if key:
            latest[key] = rec
    for rec in latest.values():
        for p in rec.get("artifacts") or []:
            if isinstance(p, str) and p:
                _add(p)

    # ESN 完工后：补扫 Output（step 记录可能缺 glob 产物或路径在外置目录）
    if _esn_fill_done(state) or _pipeline_done(state):
        project = state.get("project") or {}
        work_root = Path(get_device_install_root())
        out_dir = get_output_dir(project)
        for pat in _OUTPUT_SCAN_PATTERNS:
            for f in sorted(out_dir.glob(pat)):
                if not f.is_file():
                    continue
                if "模板" in f.name:
                    continue
                _add(output_rel(work_root, f))

    paths.sort(key=_artifact_sort_key)
    return paths


def _build_di_artifacts(state: dict[str, Any]) -> SduiCardNode | None:
    """设备安装 · 作业结果卡（完工界面展示责任人表/实施计划/SN/完工清单/完工报告等）。"""
    paths = _collect_di_artifact_paths(state)
    if not paths:
        return None
    items = [
        SduiArtifactItem(
            id=f"di-art-{i}", label=Path(p).name, path=p,
            kind=artifact_kind(p),  # type: ignore[arg-type]
            status="ready",
        )
        for i, p in enumerate(paths)
    ]
    return SduiCardNode(
        id="di-artifacts-card", title="作业结果",
        children=[SduiArtifactGridNode(id="di-artifacts-grid", mode="output", artifacts=items)],
    )


def _sdui_meta(state: dict[str, Any]) -> dict[str, Any]:
    """SDUI 文档 meta：前端布局策略（不写死 skillId）。"""
    return {
        "skill": "device_install",
        "run_id": state.get("run_id", ""),
        "route_hitl_edit": "workbench",
        "workbench_class": "di",
    }


def _run_has_started(state: dict[str, Any]) -> bool:
    """run 已启动但 steps 尚未落盘（节点切换 / SSE 重连快照）。"""
    if not state.get("run_id"):
        return False
    logs = state.get("logs") or []
    return any("[start]" in str(l) for l in logs)


def project(state: dict[str, Any]) -> dict[str, Any]:
    """SkillState → SduiDocument（横向 Stepper + 主内容区）。"""
    status_key, _ = overall_status(state, DI_STEP_ORDER, paused_badge="待补充")
    is_idle = status_key == "idle"

    if is_idle:
        if _run_has_started(state):
            doc = SduiDocument(
                root=SduiStackNode(id="di-root", gap="sm", children=[_build_di_stepper(state)]),
                meta=_sdui_meta(state),
            )
            return dump_sdui_json(doc)
        doc = SduiDocument(
            root=SduiStackNode(id="di-root", gap="sm", children=[]),
            meta={**_sdui_meta(state), "suppress_idle_panel": True},
        )
        return dump_sdui_json(doc)

    nodes: list[SduiNode] = [
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
        # 编辑卡下方追加「作业结果」卡（如该步预生成了产物，如责任人信息表模板）
        step_result = _build_step_result_artifacts(state)
        if step_result:
            nodes.append(step_result)
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
        side_content = [n for n in (step_result or _build_di_artifacts(state),) if n]
        if main_content and side_content:
            if _show_task_progress(state):
                # ESN 完工后：任务进展全宽在上，作业结果全宽在下（不用 5:2 侧栏）
                nodes.append(SduiStackNode(
                    id="dash-main", gap="sm", children=main_content + side_content,
                ))
            else:
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
