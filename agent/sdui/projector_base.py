"""
SDUI 投影器共享底座 · projector_base

zhgk / guihua / 后续 skill 的投影器（skills/<name>/sdui.py）此前各自复制了一套
「七段式」脚手架（状态映射 / header / stepper / 进度环 / 文件栏 / HITL 卡 / 日志摘要），
近乎逐字重复 —— 新 skill 复制 = 再抄一遍，DRY 债随 skill 数线性增长。

本模块把**与业务无关的通用构件**抽成参数化纯函数：各 skill 的 sdui.py 只保留
「业务 KPI / 告警 / 摘要 bits」三类自有逻辑，通用段一律调这里。

约定（保持纯函数）：
  - 所有函数无副作用、不读磁盘、不调 LLM；给定 state（+ 配置参数）输出确定。
  - 返回 builder 节点对象（未 dump）；各 skill 的 project() 负责组装 + dump_sdui_json。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.sdui.builder import (
    SduiNode,
    SduiCardNode, SduiRowNode, SduiStackNode,
    SduiTextNode, SduiBadgeNode, SduiButtonNode,
    SduiStepperNode, SduiStepperStep,
    SduiDonutChartNode, SduiDonutSegment,
    SduiBarChartNode, SduiBarDatum,
    SduiStatisticRowNode, SduiStatisticRowItem,
    SduiMarkdownNode, SduiArtifactGridNode, SduiArtifactItem,
    SduiFilePickerNode, SduiChoiceCardNode, SduiDividerNode,
    SduiHitlFormNode, SduiHitlFormField,
    SduiAlertNode, SduiNumberCardNode,
    SduiPostUserMessage,
    choice_options,
)

# cta_map 的值：(按钮文案, variant, post_user_message)
CtaSpec = tuple[str, str, str]

_BADGE_TONE = {
    "idle": "default", "running": "success", "paused": "warning",
    "done": "success", "failed": "danger",
}


# ── 纯函数：状态映射 ────────────────────────────────────────────────────────────

def backend_status_to_sdui(status: str) -> str:
    """后端 StepStatus → 前端 SduiStepperStatus。"""
    return {"pending": "waiting", "running": "running", "completed": "done",
            "failed": "error", "hitl": "running"}.get(status, "waiting")


def collect_metrics(state: dict[str, Any]) -> dict[str, Any]:
    """把各 step 的 metrics 聚合成一张扁平表（后写覆盖先写）。

    ⚠️ last-write-wins：若两个 step 写了同名键，后者覆盖前者。
    规避方案：步骤写 metrics 时用 <step_key>_<metric> 前缀命名
    （如 assess_total 而非 total），投影器按前缀读，互不干扰。
    读单步骤的 metrics 请用 collect_metrics_ns(state, "<step_key>")。
    """
    out: dict[str, Any] = {}
    for step in state.get("steps") or []:
        out.update(step.get("metrics") or {})
    return out


def collect_metrics_ns(state: dict[str, Any], namespace: str) -> dict[str, Any]:
    """读取命名空间为 namespace 的 metrics（即 key 以 "<namespace>_" 开头的键）。

    返回**去前缀**后的 dict：namespace="assess" 时，
    "assess_total" → "total"，"assess_满足" → "满足"，便于投影器按短名读取。

    用法：
      m = collect_metrics_ns(state, "assess")
      total = m.get("total", 0)      # 对应 step 写的 assess_total
      satisfied = m.get("满足", 0)   # 对应 step 写的 assess_满足
    """
    prefix = f"{namespace}_"
    flat = collect_metrics(state)
    return {k[len(prefix):]: v for k, v in flat.items() if k.startswith(prefix)}


def artifact_kind(path: str) -> str:
    """从文件路径后缀推断 SduiArtifactItem.kind。"""
    ext = Path(path).suffix.lower().lstrip(".")
    return {"docx": "docx", "xlsx": "xlsx", "pdf": "pdf", "html": "html", "htm": "html",
            "json": "json", "md": "md", "png": "png", "jpg": "png", "jpeg": "png"}.get(ext, "other")


def overall_status(
    state: dict[str, Any], step_order: list[str], *, paused_badge: str = "待确认"
) -> tuple[str, str]:
    """返回 (status_key, badge_text)。status_key ∈ idle/running/paused/done/failed。"""
    if state.get("error"):
        return "failed", "失败"
    if (state.get("hitl") or {}).get("step"):
        return "paused", paused_badge
    steps = state.get("steps") or []
    if not steps:
        return "idle", "未开始"
    statuses = {s.get("status", "pending") for s in steps}
    if "running" in statuses:
        return "running", "执行中"
    if "failed" in statuses:
        return "failed", "失败"
    if all(s == "completed" for s in statuses) and len(steps) >= len(step_order):
        return "done", "已完成"
    return "running", "执行中"


# ── 通用构件 ────────────────────────────────────────────────────────────────────

def build_header(
    state: dict[str, Any], *,
    default_name: str,
    cta_map: dict[str, CtaSpec],
    step_order: list[str],
    paused_badge: str = "待确认",
) -> SduiCardNode:
    """顶部卡：项目名 + 状态徽标 + CTA 按钮（running 态不显示按钮）。
    cta_map: {status_key: (label, variant, post_message)}。"""
    project = state.get("project") or {}
    name = project.get("project_name", default_name) or default_name
    status_key, badge_text = overall_status(state, step_order, paused_badge=paused_badge)

    children: list[SduiNode] = [
        SduiTextNode(content=name, variant="heading"),
        SduiBadgeNode(text=badge_text, tone=_BADGE_TONE.get(status_key, "default")),
    ]
    cta = cta_map.get(status_key)
    if cta and cta[2] and status_key != "running":
        children.append(SduiButtonNode(
            id="cta-btn", label=cta[0], variant=cta[1],  # type: ignore[arg-type]
            action=SduiPostUserMessage(text=cta[2]),
        ))
    return SduiCardNode(
        id="header",
        children=[SduiRowNode(align="center", justify="between", gap="sm", children=children)],
    )


def build_stepper(
    state: dict[str, Any], *,
    step_names: dict[str, str],
    orientation: str | None = None,
    collapsible: bool = False,
    default_collapsed: bool = False,
) -> SduiCardNode:
    """执行进度 Stepper。step_names 是有序 {step_key: 中文名}（顺序即展示顺序）。
    orientation: "horizontal"（默认紧凑头部）/ "vertical"（时间轴竖向，zhgk 用）。
    collapsible: 卡头可折叠（把 micro-step 明细收起，macro-rail/donut 已承载概览）。"""
    by_key = {s.get("key", ""): s for s in (state.get("steps") or [])}
    steps: list[SduiStepperStep] = []
    done = 0
    for key, title in step_names.items():
        rec = by_key.get(key)
        status = backend_status_to_sdui(rec.get("status", "pending")) if rec else "waiting"
        if status == "done":
            done += 1
        lines = [str(l) for l in (rec.get("log_tail") or [])[-3:]] if rec else []
        steps.append(SduiStepperStep(
            id=key, title=title,
            status=status,  # type: ignore[arg-type]
            detail=lines or None,  # 空则 None（不产空数组）
        ))
    title = f"执行明细 · {done}/{len(steps)}" if collapsible else "执行进度"
    return SduiCardNode(id="stepper", title=title,
                        collapsible=collapsible or None,
                        defaultCollapsed=default_collapsed or None,
                        children=[SduiStepperNode(
                            id="steps", steps=steps,
                            orientation=orientation,  # type: ignore[arg-type]
                        )])


def build_stepper_for_intent(
    state: dict[str, Any], *,
    step_names: dict[str, str],
    intent: str | None,
    intent_step_map: dict[str, set[str]] | None = None,
    always_show: set[str] | None = None,
    orientation: str | None = None,
    collapsible: bool = False,
    default_collapsed: bool = False,
) -> SduiCardNode:
    """意图感知 Stepper：只展示当前 intent 涉及的步骤，避免全量 pipeline 淹没用户。

    参数：
      step_names      — {step_key: 中文名}，完整步骤表（顺序即展示顺序）
      intent          — project["intent"]；None 或空时展示全量（preflight 阶段）
      intent_step_map — {step_key: {允许的 intent 集合}}；None 时展示全量
      always_show     — 无论 intent 如何都展示的步骤（如 preflight / intent_select）
      orientation     — "horizontal" / "vertical"

    典型用法（zhgk 风格）：
        from .steps._intent_guard import STEP_INTENTS
        intent = (state.get("project") or {}).get("intent", "")
        nodes.append(build_stepper_for_intent(
            state,
            step_names=ZHGK_STEP_NAMES,
            intent=intent,
            intent_step_map=STEP_INTENTS,
            always_show={"preflight", "intent_select"},
            orientation="vertical",
        ))
    """
    if not intent or intent_step_map is None:
        # 无意图 / 无过滤表：展示全量
        filtered = step_names
    else:
        _always = always_show or set()
        filtered = {
            k: v for k, v in step_names.items()
            if k in _always
            or (intent in (intent_step_map.get(k) or set()))
        }

    return build_stepper(state, step_names=filtered, orientation=orientation,
                         collapsible=collapsible, default_collapsed=default_collapsed)


def build_progress_donut(state: dict[str, Any], *, step_order: list[str]) -> SduiDonutChartNode:
    """进度环（黄金指标卡左半）。overall_progress 优先，否则按已完成步骤比例。"""
    steps = state.get("steps") or []
    overall = state.get("overall_progress", 0) or 0
    total = len(step_order)
    done = sum(1 for s in steps if s.get("status") == "completed")
    pct = overall or (round(done / total * 100) if total else 0)
    return SduiDonutChartNode(
        id="donut",
        segments=[
            SduiDonutSegment(label="已完成", value=pct, color="accent"),
            SduiDonutSegment(label="剩余", value=max(0, 100 - pct), color="subtle"),
        ],
        centerLabel="进度", centerValue=f"{pct}%", flex=1,
    )


def build_metrics_card(
    state: dict[str, Any], *,
    step_order: list[str],
    kpi_items: list[SduiStatisticRowItem],
) -> SduiCardNode | None:
    """黄金指标卡：进度环 + KPI 行。kpi_items 由各 skill 按自己的 metrics 提供；
    为空时回退「已完成步骤 x/total」。无任何 step 时返回 None。"""
    steps = state.get("steps") or []
    if not steps:
        return None
    items = list(kpi_items)
    if not items:
        total = len(step_order)
        done = sum(1 for s in steps if s.get("status") == "completed")
        items.append(SduiStatisticRowItem(title="已完成步骤", value=f"{done}/{total}"))
    return SduiCardNode(
        id="golden-metrics", title="黄金指标",
        children=[SduiRowNode(align="center", gap="lg", children=[
            build_progress_donut(state, step_order=step_order),
            SduiStatisticRowNode(id="kpi-row", items=items, flex=2),
        ])],
    )


def build_artifacts(
    state: dict[str, Any], *, input_file_keys: tuple[str, ...] = (),
    input_paths: list[str] | None = None,
    output_paths: list[str] | None = None,
) -> SduiRowNode | None:
    """产物双栏：「已上传文件」+「作业结果」。两栏皆空 → None。

    路径来源（保持本函数纯·不读盘）：
      - output_paths/input_paths 显式传入 → 直接用（调用方负责采集，可扫盘）。
      - 否则回退默认：output 从已完成 step 的 artifacts 收集；
        input 从 state.files 按 input_file_keys 取。
    """
    show_input = input_paths is not None or bool(input_file_keys)

    if output_paths is None:
        output_paths = []
        for s in state.get("steps") or []:
            if s.get("status") == "completed":
                for p in s.get("artifacts") or []:
                    if p not in output_paths:
                        output_paths.append(p)

    if input_paths is None:
        files = state.get("files") or {}
        input_paths = []
        for key in input_file_keys:
            p = files.get(key)
            if p and isinstance(p, str):
                input_paths.append(p)

    if not input_paths and not output_paths:
        return None

    def _item(path: str, i: int) -> SduiArtifactItem:
        return SduiArtifactItem(id=f"art-{i}", label=Path(path).name, path=path,
                                kind=artifact_kind(path),  # type: ignore[arg-type]
                                status="ready")

    grids: list[SduiNode] = []
    if show_input:
        grids.append(SduiArtifactGridNode(
            id="input-files", title="已上传文件", mode="input",
            artifacts=[_item(p, i) for i, p in enumerate(input_paths)], flex=1))
    grids.append(SduiArtifactGridNode(
        id="output-files", title="作业结果", mode="output",
        artifacts=[_item(p, i) for i, p in enumerate(output_paths)], flex=1))
    return SduiRowNode(gap="md", children=grids)


def build_summary_card(bits: list[str], state: dict[str, Any]) -> SduiCardNode | None:
    """阶段摘要：bits 非空 → 业务摘要卡；否则回退最新日志卡；都无 → None。"""
    if bits:
        return SduiCardNode(id="summary", title="阶段摘要",
                            children=[SduiMarkdownNode(content="· " + "\n· ".join(bits))])
    logs = state.get("logs") or []
    meaningful = [l for l in logs if l and not l.startswith("[start]") and not l.startswith("[resume]")]
    if not meaningful:
        return None
    excerpt = "\n".join(meaningful[-5:])
    return SduiCardNode(id="summary", title="最新日志",
                        children=[SduiMarkdownNode(content=f"```\n{excerpt}\n```")])


def build_number_cards(
    items: list[tuple[str, int | float | str, str]],
    *,
    node_id: str = "number-cards",
) -> SduiRowNode:
    """一行 NumberCard（可换行）。

    items: [(label, value, tone), ...]
      tone ∈ success / warning / error / accent / subtle

    示例（五值评估）：
      build_number_cards([
          ("满足",     45, "success"),
          ("不满足",   8,  "error"),
          ("不涉及",   12, "subtle"),
          ("未勘测",   5,  "warning"),
          ("无法识别", 3,  "warning"),
      ])
    """
    children: list[SduiNode] = [
        SduiNumberCardNode(
            id=f"{node_id}-{i}",
            label=label,
            value=value,
            tone=tone,  # type: ignore[arg-type]
        )
        for i, (label, value, tone) in enumerate(items)
    ]
    return SduiRowNode(id=node_id, gap="sm", wrap=True, children=children)


def build_assessment_panel(
    state: dict[str, Any],
    *,
    total_key: str,
    value_keys: list[tuple[str, str, str]],   # (label, metrics_key, tone)
    node_id: str = "assess-panel",
    title: str = "评估概览",
    rate_label: str = "满足率",
    rate_key: str | None = None,              # 若为 None 取 value_keys 第一项 / total 计算
    alert_keys: list[tuple[str, str, str]] | None = None,  # (metrics_key, tone, msg_tmpl)
) -> SduiCardNode | None:
    """通用「多值评估」面板 — NumberCards + 分布 DonutChart + BarChart + 条件 Alert。

    专为「满足/不满足/不涉及/未勘测/无法识别」类型的评估结果设计，
    但可配置成任何多值分类展示（传不同 value_keys 即可）。

    参数：
      total_key   — 从 collect_metrics(state) 读总数的键
      value_keys  — [(中文标签, metrics 键, tone), ...]  决定 NumberCard + 分布图
      rate_key    — 分子键；None 时用 value_keys[0] 的 metrics 键
      alert_keys  — [(metrics 键, tone, 告警消息模板), ...]，模板中 {count} 会被替换

    返回 None 表示数据未就绪（total 为 0 或不存在）。
    """
    m = collect_metrics(state)
    total: int = int(m.get(total_key, 0) or 0)
    if not total:
        return None

    values: list[tuple[str, int]] = [
        (label, int(m.get(mkey, 0) or 0))
        for label, mkey, _ in value_keys
    ]

    # 满足率（用作 DonutChart 中心值）
    rate_val = int(m.get(rate_key, 0) or 0) if rate_key else values[0][1] if values else 0
    rate_pct = round(rate_val / total * 100) if total else 0

    # ① NumberCard 行
    cards_row = build_number_cards(
        [(label, val, tone) for (label, _, tone), (_, val) in zip(value_keys, values)],
        node_id=f"{node_id}-cards",
    )

    # ② 分布 DonutChart + BarChart
    segments = [
        SduiDonutSegment(label=label, value=val, color=tone)
        for (label, _, tone), (_, val) in zip(value_keys, values)
    ]
    donut = SduiDonutChartNode(
        id=f"{node_id}-donut",
        segments=segments,
        centerLabel=rate_label, centerValue=f"{rate_pct}%", flex=1,
    )
    bar = SduiBarChartNode(
        id=f"{node_id}-bar",
        data=[SduiBarDatum(label=label, value=val, color=tone)
              for (label, _, tone), (_, val) in zip(value_keys, values)],
        valueUnit="项", flex=2,
    )
    chart_row = SduiRowNode(id=f"{node_id}-charts", align="center", gap="lg",
                            children=[donut, bar])

    # ③ 条件 Alert
    children: list[SduiNode] = [cards_row, chart_row]
    if alert_keys:
        for a_mkey, a_tone, a_msg in alert_keys:
            a_count = int(m.get(a_mkey, 0) or 0)
            if a_count:
                children.append(SduiAlertNode(
                    id=f"{node_id}-alert-{a_mkey}",
                    tone=a_tone,  # type: ignore[arg-type]
                    title=f"{a_count} 项「{a_mkey.split('_')[-1]}」",
                    message=a_msg.format(count=a_count),
                ))

    # 卡片基调：取最"严重"的条件
    tone_priority = {"danger": 3, "warning": 2, "success": 1, "default": 0}
    card_tone = "default"
    if alert_keys:
        for a_mkey, a_tone, _ in alert_keys:
            if int(m.get(a_mkey, 0) or 0) > 0:
                if tone_priority.get(a_tone, 0) > tone_priority.get(card_tone, 0):
                    card_tone = a_tone

    return SduiCardNode(
        id=node_id, title=f"{title}（共 {total} 项）",
        tone=card_tone if card_tone != "default" else None,  # type: ignore[arg-type]
        children=children,
    )


def build_data_table(
    state: dict[str, Any],
    *,
    rows_key: str,
    headers: list[str],
    node_id: str = "data-table",
    title: str = "详细清单",
    max_rows: int = 20,
    empty_text: str = "暂无记录",
    tone: str | None = None,
) -> SduiCardNode | None:
    """从 metrics 取一个 list[list[str]] 渲染为 Table 卡片。

    rows_key — collect_metrics(state)[rows_key] 须是 list[list[str]]；不存在/为空 → None。
    """
    from agent.sdui.builder import SduiTableNode
    m = collect_metrics(state)
    rows: list[list[str]] = m.get(rows_key) or []
    if not rows:
        return None
    suffix = f"，仅展示前 {max_rows} 条" if len(rows) > max_rows else ""
    return SduiCardNode(
        id=node_id,
        title=f"{title}（{len(rows)} 条{suffix}）",
        tone=tone,  # type: ignore[arg-type]
        children=[SduiTableNode(id=f"{node_id}-tbl", headers=headers, rows=rows[:max_rows])],
    )


def build_editable_table(state: dict[str, Any]) -> SduiCardNode | None:
    """在线编辑型 HITL（hitl.need_edit）→ 可编辑 DataTable 卡。

    need_edit 契约（由 step.check_inputs 下发）：
      card_title / title / subtitle / columns(list[dict]) / rows(list[dict])
      / rowKey / checkKey / submitLabel / fillLabel / fillRows
      / backLabel / backStepId（表头「返回上一步」→ run-patch go_back）
      / groupKey / groupAsTabs / pageSize / requiredKeys

    提交语义：前端把编辑后的行 POST /resume，payload={"rows": [...]}；
    skill.apply_resume_payload 据 hitl.step 写回 project（dispatch_rows / esn_rows）。
    """
    from agent.sdui.builder import SduiDataTableNode, SduiDataTableColumn

    hitl = state.get("hitl") or {}
    step_key = hitl.get("step")
    spec = hitl.get("need_edit") or {}
    if not step_key or not spec:
        return None

    columns = [SduiDataTableColumn.model_validate(c) for c in (spec.get("columns") or [])]
    subtitle = spec.get("subtitle") or ""
    table = SduiDataTableNode(
        id=f"edit-{step_key}",
        title=spec.get("title"),
        columns=columns,
        rows=spec.get("rows") or [],
        editable=True,
        submitMode="resume",
        stepId=step_key,
        rowKey=spec.get("rowKey"),
        checkKey=spec.get("checkKey"),
        submitLabel=spec.get("submitLabel") or "提交",
        fillLabel=spec.get("fillLabel"),
        deselectLabel=spec.get("deselectLabel"),
        fillRows=spec.get("fillRows"),
        backLabel=spec.get("backLabel"),
        backStepId=spec.get("backStepId"),
        groupKey=spec.get("groupKey"),
        groupAsTabs=spec.get("groupAsTabs"),
        pageSize=spec.get("pageSize"),
        requiredKeys=spec.get("requiredKeys"),
    )
    children: list[SduiNode] = []
    if subtitle:
        children.append(SduiTextNode(content=subtitle, variant="body"))
    children.append(table)
    return SduiCardNode(
        id=f"edit-card-{step_key}",
        title=spec.get("card_title") or "在线编辑",
        children=children,
    )


def build_hitl(
    state: dict[str, Any], *,
    card_title: str = "需要补充",
    default_choice_title: str = "请确认",
) -> SduiCardNode | None:
    """HITL 卡（三形态）：
      - 文件型：hitl.need_files → FilePicker（前端走 /upload/batch）
      - 确认型：hitl.need_inputs → ChoiceCard（前端走 /resume，payload={"choice": value}）
      - 字段型：hitl.need_inputs[type=form] → HitlForm（前端走 /resume，payload={payload_key: ...}）
    options 统一经 builder.choice_options 容错 str/dict。hitl.step 为空 → None。"""
    hitl = state.get("hitl") or {}
    step_key = hitl.get("step")
    if not step_key:
        return None
    reason = hitl.get("reason", "需要人工干预")
    need_files: list[str] = hitl.get("need_files") or []
    need_inputs: list[dict] = hitl.get("need_inputs") or []
    children: list[SduiNode] = [SduiTextNode(content=reason, variant="body", color="warning")]

    if need_files:
        children.append(SduiDividerNode())
        children.append(SduiFilePickerNode(
            id=f"hitl-file-{step_key}", purpose=f"hitl_{step_key}",
            label=f"请上传缺少的文件（{len(need_files)} 项）",
            helpText="· " + "\n· ".join(need_files),
            accept="*/*", multiple=True, hitlRequestId=step_key, stepId=step_key,
        ))
    elif need_inputs:
        inp = need_inputs[0]
        if inp.get("type") == "form" or inp.get("fields"):
            fields = [
                SduiHitlFormField(
                    key=str(f.get("key", "")),
                    label=str(f.get("label", f.get("key", ""))),
                    placeholder=f.get("placeholder"),
                    required=bool(f.get("required", False)),
                    defaultValue=f.get("defaultValue"),
                )
                for f in (inp.get("fields") or [])
                if f.get("key")
            ]
            if fields:
                children.append(SduiDividerNode())
                children.append(SduiHitlFormNode(
                    id=f"hitl-form-{step_key}",
                    title=inp.get("label", default_choice_title),
                    fields=fields,
                    payloadKey=inp.get("payload_key") or inp.get("payloadKey") or inp.get("id"),
                    repeatable=bool(inp.get("repeatable", False)),
                    submitLabel=inp.get("submit_label") or inp.get("submitLabel"),
                    helpText=inp.get("help_text") or inp.get("helpText"),
                    hitlRequestId=step_key,
                    stepId=step_key,
                ))
        else:
            options = choice_options(inp.get("options"))
            if options:
                children.append(SduiDividerNode())
                children.append(SduiChoiceCardNode(
                    id=f"hitl-choice-{step_key}",
                    title=inp.get("label", default_choice_title),
                    options=options, hitlRequestId=step_key, stepId=step_key,
                ))

    if state.get("error"):
        children.append(SduiTextNode(content=f"错误：{state['error']}", variant="caption", color="error"))

    return SduiCardNode(id="hitl-card", title=card_title, children=children)
