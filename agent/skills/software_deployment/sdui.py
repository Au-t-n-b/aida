"""software_deployment SDUI 投影器 · 仅右侧业务工作台（不含左导航 / 中栏对话）。

布局（对齐 UI设计/UI/app.jsx）：
  TabGroup(subnav) → 作业空间 | 项目文档 | 项目计划 | 调测任务记录 | 设备总览 | 流水线
  作业空间：ctx-bar → 执行进度(FlowSteps) → KPI → 步骤详情 → 材料 → 时间轴 → 产物 → HITL
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.sdui.builder import (
    SduiAlertNode,
    SduiButtonNode,
    SduiCardNode,
    SduiContextBarGroup,
    SduiContextBarNode,
    SduiDividerNode,
    SduiDocument,
    SduiEmptyStateNode,
    SduiFlowStepCard,
    SduiFlowStepChip,
    SduiFlowStepsNode,
    SduiHitlTextInputNode,
    SduiInputSlot,
    SduiInputSlotListNode,
    SduiMarkdownNode,
    SduiNode,
    SduiStackNode,
    SduiStatisticRowItem,
    SduiStatisticRowNode,
    SduiTabGroupNode,
    SduiTabPanel,
    SduiTextNode,
    SduiTimelineEvent,
    SduiTimelineNode,
    SduiArtifactGridNode,
    SduiArtifactItem,
    SduiOpenPreview,
    SduiPostUserMessage,
    dump_sdui_json,
)
from .steps._sd_ops import COMMAND_LABELS
from agent.sdui.projector_base import (
    build_artifacts,
    build_hitl,
    build_summary_card,
    collect_metrics,
)
from .sdui_tabs import (
    build_devices_tab,
    build_docs_tab,
    build_pipeline_tab,
    build_plan_tab,
    build_task_log_tab,
)

SD_STEP_NAMES: dict[str, str] = {
    "plan_receive": "接收二级任务",
    "plan_split": "拆分调测计划",
    "plan_dispatch": "下发设备底表",
    "cloudops_init": "CloudOps 初配",
    "cloudops_supplement": "CloudOps 补充",
    "cloudops_full": "CloudOps 完整配置",
    "toolkit_executor": "配置调测设备",
    "toolkit_import": "导入 Toolkit",
    "connection": "服务器连线检查",
    "lq_connection": "灵衢连线检查",
    "weak_light": "服务器弱光检查",
    "hccs_weak_light": "灵衢光链路检查",
    "commission_report": "调测报告汇总",
}
SD_STEP_ORDER = list(SD_STEP_NAMES.keys())

_COMMISSION_KEYS = ("connection", "lq_connection", "weak_light", "hccs_weak_light")

# 主线 FlowSteps（10 卡）· ⑨ 合并四条 init_install 为「命令调测」
_SD_FLOW_DEFS: list[dict[str, Any]] = [
    {
        "id": "m1",
        "num": 1,
        "title": "接收任务",
        "keys": ["plan_receive"],
        "chips": [("作业管理已下发任务", "plan_receive")],
    },
    {
        "id": "m2",
        "num": 2,
        "title": "拆分计划",
        "keys": ["plan_split"],
        "chips": [("项目验收用例", "plan_split")],
    },
    {
        "id": "m3",
        "num": 3,
        "title": "下发计划",
        "keys": ["plan_dispatch"],
        "chips": [("LLD文件", "plan_dispatch")],
    },
    {
        "id": "m4",
        "num": 4,
        "title": "生成CloudOps初始配置",
        "keys": ["cloudops_init"],
        "chips": [],
    },
    {
        "id": "m5",
        "num": 5,
        "title": "CloudOps配置上传补充",
        "keys": ["cloudops_supplement"],
        "chips": [("手工补充表", "cloudops_supplement")],
    },
    {
        "id": "m6",
        "num": 6,
        "title": "生成完整配置文件",
        "keys": ["cloudops_full"],
        "chips": [("完工清单", "cloudops_full"), ("ZTP文件（可选）", "ztp")],
    },
    {
        "id": "m7",
        "num": 7,
        "title": "配置执行机",
        "keys": ["toolkit_executor"],
        "chips": [("IP / SK", "toolkit_executor")],
    },
    {
        "id": "m8",
        "num": 8,
        "title": "导入Toolkit配置",
        "keys": ["toolkit_import"],
        "chips": [],
    },
    {
        "id": "m9",
        "num": 9,
        "title": "命令调测",
        "keys": list(_COMMISSION_KEYS),
        "chips": [
            ("服务器连线检查", "connection"),
            ("灵衢连线检查", "lq_connection"),
            ("服务器弱光检查", "weak_light"),
            ("灵衢光链路检查", "hccs_weak_light"),
        ],
    },
    {
        "id": "m10",
        "num": 10,
        "title": "调测报告汇总",
        "keys": ["commission_report"],
        "chips": [],
    },
]

def _steps_map(state: dict[str, Any]) -> dict[str, str]:
    return {str(s.get("key") or ""): str(s.get("status") or "pending") for s in (state.get("steps") or [])}


def _step_record(state: dict[str, Any], key: str) -> dict[str, Any] | None:
    for s in state.get("steps") or []:
        if s.get("key") == key:
            return s
    return None


def _metric(m: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in m and m[k] is not None and m[k] != "":
            return m[k]
    return default


def _commission_passed(m: dict[str, Any]) -> int:
    return sum(1 for k in _COMMISSION_KEYS if m.get(f"{k}_ok"))


def _current_step_key(state: dict[str, Any]) -> str:
    explicit = str(state.get("current_step") or "").strip()
    if explicit:
        return explicit
    sm = _steps_map(state)
    for key in SD_STEP_ORDER:
        if sm.get(key) == "running":
            return key
    hitl_step = str((state.get("hitl") or {}).get("step") or "").strip()
    return hitl_step


def _chip_status(chip_key: str, sm: dict[str, str], m: dict[str, Any]) -> str:
    if chip_key == "ztp":
        if m.get("ztp_present"):
            return "ok"
        if m.get("requires_ztp") is False:
            return "idle"
        return "idle"
    st = sm.get(chip_key, "pending")
    if st == "completed":
        return "ok"
    if st in ("running", "hitl"):
        return "pending"
    return "idle"


def _flow_card_status(keys: list[str], sm: dict[str, str], current_key: str) -> str:
    statuses = [sm.get(k, "pending") for k in keys]
    if current_key in keys or any(s in ("running", "hitl") for s in statuses):
        return "current"
    if all(s == "completed" for s in statuses):
        return "done"
    return "future"


def _flow_id_for_step(step_key: str) -> str | None:
    for spec in _SD_FLOW_DEFS:
        if step_key in spec["keys"]:
            return str(spec["id"])
    return None


def _build_context_bar(state: dict[str, Any]) -> SduiContextBarNode | None:
    if not state.get("steps"):
        return None
    project = state.get("project") or {}
    m = collect_metrics(state)
    batch = str(project.get("batch_id") or state.get("run_id") or "—")
    if len(batch) > 24:
        batch = f"{batch[:20]}…"
    start = str(project.get("planned_start") or project.get("window_start") or "—")
    end = str(project.get("planned_end") or project.get("deadline") or "—")
    owner = str(project.get("owner") or "—")
    pods = project.get("pods")
    devices = project.get("devices") or _metric(m, "device_rows", default=None)
    if pods and devices:
        scale = f"{pods} Pod · {devices} 台"
    elif devices:
        scale = f"{devices} 台"
    else:
        scale = "—"
    remaining = project.get("remaining_days")
    end_group = SduiContextBarGroup(label="预计截止", value=end)
    if isinstance(remaining, int):
        if remaining < 0:
            end_group.badge = f"逾期 {abs(remaining)} 天"
        elif remaining == 0:
            end_group.badge = "今日截止"
        else:
            end_group.badge = f"剩 {remaining} 天"
    return SduiContextBarNode(
        id="sd-ctx-bar",
        showTimelineArrow=True,
        groups=[
            SduiContextBarGroup(label="批次", value=batch),
            SduiContextBarGroup(label="开始", value=start),
            end_group,
            SduiContextBarGroup(label="负责人", value=owner),
            SduiContextBarGroup(label="规模", value=scale),
        ],
    )


def _build_execution_progress(state: dict[str, Any]) -> SduiCardNode | None:
    if not state.get("steps"):
        return None
    sm = _steps_map(state)
    current_key = _current_step_key(state)
    current_flow_id = _flow_id_for_step(current_key) if current_key else None
    m = collect_metrics(state)
    cards: list[SduiFlowStepCard] = []
    for spec in _SD_FLOW_DEFS:
        keys: list[str] = list(spec["keys"])
        status = _flow_card_status(keys, sm, current_key)
        chips = [
            SduiFlowStepChip(
                text=text,
                status=_chip_status(chip_key, sm, m),  # type: ignore[arg-type]
            )
            for text, chip_key in spec.get("chips", [])
        ]
        primary_key = keys[0] if len(keys) == 1 else (current_key if current_key in keys else keys[0])
        cards.append(
            SduiFlowStepCard(
                id=str(spec["id"]),
                num=int(spec["num"]),
                title=str(spec["title"]),
                status=status,  # type: ignore[arg-type]
                chips=chips or None,
                stepKey=primary_key,
            )
        )
    return SduiCardNode(
        id="sd-execution-progress",
        title="执行进度",
        children=[
            SduiFlowStepsNode(
                id="sd-flow-steps",
                steps=cards,
                currentId=current_flow_id,
            )
        ],
    )


def _build_kpi_strip(state: dict[str, Any]) -> SduiCardNode | None:
    if not state.get("steps"):
        return None
    m = collect_metrics(state)
    progress = state.get("overall_progress", 0) or 0
    passed = _commission_passed(m)
    items: list[SduiStatisticRowItem] = [
        SduiStatisticRowItem(
            title="二级任务",
            value=str(_metric(m, "task_count", default="—")),
            color="accent",
        ),
        SduiStatisticRowItem(
            title="三级活动",
            value=str(_metric(m, "third_count", default="—")),
            color="accent",
        ),
        SduiStatisticRowItem(
            title="设备底表",
            value=str(_metric(m, "device_rows", default="—")),
            color="accent",
        ),
        SduiStatisticRowItem(
            title="Toolkit",
            value=str(_metric(m, "refreshed_devices", default="—")),
            color="accent",
        ),
        SduiStatisticRowItem(
            title="命令调测",
            value=f"{passed}/4",
            color="success" if passed == 4 else "warning",
        ),
        SduiStatisticRowItem(
            title="调测报告",
            value="已生成" if m.get("report_generated") else "—",
            color="success" if m.get("report_generated") else "subtle",
        ),
        SduiStatisticRowItem(
            title="总进度",
            value=f"{progress}%",
            color="accent",
        ),
    ]
    return SduiCardNode(
        id="sd-kpi-strip",
        title="关键指标",
        children=[SduiStatisticRowNode(id="sd-kpis", items=items)],
    )


def _build_step_detail(state: dict[str, Any]) -> SduiCardNode | None:
    key = _current_step_key(state)
    if not key:
        return None
    rec = _step_record(state, key)
    if not rec and not (state.get("hitl") or {}).get("step"):
        return None
    title = SD_STEP_NAMES.get(key, key)
    if key in _COMMISSION_KEYS:
        title = f"命令调测 · {title}"
    lines: list[str] = [f"**步骤**：{title} (`{key}`)"]
    if rec:
        lines.append(f"**状态**：{rec.get('status', 'pending')}")
        metrics = rec.get("metrics") or {}
        if metrics:
            pairs = [f"- `{k}`: {v}" for k, v in metrics.items() if v not in (None, "", [])]
            if pairs:
                lines.append("**本步指标**\n" + "\n".join(pairs))
        tail = [str(x) for x in (rec.get("log_tail") or [])[-5:]]
        if tail:
            lines.append("**最近日志**\n" + "\n".join(f"- {t}" for t in tail))
    hitl = state.get("hitl") or {}
    if hitl.get("step") == key:
        reason = hitl.get("reason") or hitl.get("note") or "等待确认或补料"
        lines.append(f"**待处理**：{reason}")
    return SduiCardNode(
        id="sd-step-detail",
        title="当前步骤",
        children=[SduiMarkdownNode(id="sd-step-detail-md", content="\n\n".join(lines))],
    )


def _basename(path: str) -> str | None:
    text = str(path or "").strip()
    if not text:
        return None
    return Path(text).name


def _work_root() -> Path:
    from .skill import _get_software_deployment_root

    return _get_software_deployment_root()


def _disk_slot(slot_id: str) -> tuple[bool, str | None]:
    try:
        from agent import software_deployment_files as sd_files

        return sd_files.slot_disk_status(_work_root(), slot_id)
    except Exception:
        return False, None


def _build_input_slots(state: dict[str, Any]) -> SduiCardNode | None:
    """材料槽位展示：优先读磁盘匹配情况，并结合步骤完成态。"""
    if not state.get("steps"):
        return None
    m = collect_metrics(state)
    sm = _steps_map(state)

    def done(step_key: str) -> bool:
        return sm.get(step_key) == "completed"

    sl2_found, sl2_name = _disk_slot("second_level_tasks")
    tc_found, tc_name = _disk_slot("testcase")
    lld_found, lld_name = _disk_slot("lld_design")

    slots: list[SduiInputSlot] = [
        SduiInputSlot(
            label="二级任务列表",
            source="manual",
            required=True,
            ready=sl2_found or bool(_metric(m, "task_count", default=0)),
            fileName=(
                "second_level_tasks.json"
                if done("plan_receive")
                else (sl2_name if sl2_found else None)
            ),
        ),
        SduiInputSlot(
            label="验收用例 Word",
            source="manual",
            required=True,
            ready=tc_found or done("plan_split") or bool(_metric(m, "third_count", default=0)),
            fileName=tc_name if tc_found and not done("plan_split") else None,
        ),
        SduiInputSlot(
            label="LLD 设计文件",
            source="manual",
            required=True,
            ready=lld_found or done("plan_dispatch") or bool(_metric(m, "device_rows", default=0)),
            fileName=lld_name if lld_found and not done("plan_dispatch") else None,
        ),
        SduiInputSlot(
            label="CloudOps 手工补充",
            source="manual",
            required=True,
            ready=done("cloudops_supplement") or bool(m.get("manual_path")),
            fileName=_basename(str(m.get("manual_path") or "")),
        ),
        SduiInputSlot(
            label="设备安装完工清单",
            source="manual",
            required=True,
            ready=bool(m.get("checklist_present")) or done("cloudops_full"),
        ),
        SduiInputSlot(
            label="ZTP 文件包",
            source="manual",
            required=bool(m.get("requires_ztp", True)),
            ready=bool(m.get("ztp_present")),
        ),
        SduiInputSlot(
            label="CloudOps 测试参数",
            source="manual",
            required=False,
            ready=bool(m.get("params_present")),
        ),
    ]
    return SduiCardNode(
        id="sd-materials",
        title="输入材料",
        children=[SduiInputSlotListNode(id="sd-input-slots", title="槽位就绪情况", slots=slots)],
    )


def _build_timeline(state: dict[str, Any]) -> SduiCardNode | None:
    events: list[SduiTimelineEvent] = []
    for key in SD_STEP_ORDER:
        rec = _step_record(state, key)
        if not rec or rec.get("status") != "completed":
            continue
        ended = str(rec.get("ended_at") or rec.get("started_at") or "")
        time_label = ended[:16].replace("T", " ") if ended else None
        label = SD_STEP_NAMES.get(key, key)
        if key in _COMMISSION_KEYS:
            label = f"命令调测 · {label}"
        events.append(
            SduiTimelineEvent(
                label=label,
                time=time_label,
                tone="success",
            )
        )
    if not events:
        for line in (state.get("logs") or [])[-6:]:
            text = str(line).strip()
            if text:
                events.append(SduiTimelineEvent(label=text[:120], tone="default"))
    if not events:
        return None
    return SduiCardNode(
        id="sd-timeline",
        title="执行动态",
        children=[SduiTimelineNode(id="sd-timeline-node", events=events[-12:])],
    )


def _summary_bits(state: dict[str, Any]) -> list[str]:
    m = collect_metrics(state)
    bits: list[str] = []
    if tc := _metric(m, "task_count"):
        bits.append(f"已接收 {tc} 条二级任务")
    if third := _metric(m, "third_count"):
        bits.append(f"拆分三级 {third} 条")
    if devices := _metric(m, "refreshed_devices"):
        bits.append(f"Toolkit 已刷新 {devices} 台设备")
    if ip := _metric(m, "executor_ip"):
        bits.append(f"调测执行机 {ip}")
    passed = _commission_passed(m)
    if passed:
        bits.append(f"命令调测 {passed}/4 已完成")
    if m.get("report_generated"):
        name = m.get("report_name") or "调测报告汇总"
        bits.append(f"{name} 已生成")
    if m.get("ztp_present") is False and m.get("requires_ztp"):
        bits.append("提示：ZTP 文件尚未上传（不阻塞后续步骤）")
    if m.get("params_present") is False:
        bits.append("提示：CloudOps 测试参数未上传（可选）")
    return bits


def _build_sd_hitl(state: dict[str, Any]) -> SduiCardNode | None:
    hitl = state.get("hitl") or {}
    step_key = hitl.get("step")
    if not step_key:
        return None
    if step_key != "toolkit_executor":
        return build_hitl(state)
    reason = hitl.get("reason") or "请填写调测设备 IP/SK"
    return SduiCardNode(
        id="hitl-card",
        title="需要补充",
        tone="warning",
        children=[
            SduiTextNode(content=str(reason), variant="body", color="warning"),
            SduiDividerNode(),
            SduiHitlTextInputNode(
                id="hitl-text-toolkit-executor",
                purpose="toolkit_executor_configure",
                title="调测设备配置",
                label="IP/SK JSON",
                placeholder='{ "base_url_ip": "100.100.166.137", "secret_key": "...", "base_url_port": "28880" }',
                rows=5,
                submitLabel="提交配置",
                helpText="base_url_port 可省略，默认 28880；也支持 key=value 多行格式。",
                hitlRequestId=step_key,
                stepId=step_key,
            ),
        ],
    )


def _commission_hub_ready(state: dict[str, Any]) -> bool:
    sm = _steps_map(state)
    if sm.get("toolkit_import") == "completed":
        return True
    m = collect_metrics(state)
    return bool(m.get("refreshed_devices"))


def _report_artifact_rel(m: dict[str, Any]) -> str | None:
    raw = str(m.get("report_path") or "").strip().replace("\\", "/")
    if "ProjectData/" in raw:
        return raw[raw.index("ProjectData/") :]
    name = str(m.get("report_name") or "").strip()
    if name:
        return f"ProjectData/results/{name}"
    return "ProjectData/results/调测报告汇总_latest.xlsx"


def _format_commission_scope(project: dict[str, Any] | None) -> str:
    scope = str((project or {}).get("scope") or "all").strip() or "all"
    if scope.lower() == "all":
        return "全量（all）"
    return scope.upper()


def _build_commission_command_panel(state: dict[str, Any]) -> SduiCardNode | None:
    """命令调测调度区：对话框指令 / 按钮均可触发；同命令可反复执行。"""
    if not _commission_hub_ready(state):
        return None
    project = state.get("project") or {}
    scope_text = _format_commission_scope(project)
    m = collect_metrics(state)
    sm = _steps_map(state)
    buttons: list[SduiNode] = []
    for cmd in _COMMISSION_KEYS:
        label = COMMAND_LABELS.get(cmd, cmd)
        done = bool(m.get(f"{cmd}_ok")) or sm.get(cmd) == "completed"
        verb = "重新执行" if done else "执行"
        buttons.append(
            SduiButtonNode(
                id=f"sd-cmd-{cmd}",
                label=f"{verb} · {label}",
                variant="secondary" if done else "outline",
                action=SduiPostUserMessage(
                    text=f"/run_step_{cmd}{'_rerun' if done else ''}",
                ),
            )
        )
    report_ready = bool(m.get("report_generated")) or sm.get("commission_report") == "completed"
    chain_ok = all(m.get(f"{k}_ok") for k in _COMMISSION_KEYS)
    buttons.append(
        SduiButtonNode(
            id="sd-cmd-report",
            label="重新生成调测报告" if report_ready else "生成调测报告",
            variant="primary",
            action=SduiPostUserMessage(text="/run_step_commission_report"),
        )
    )
    report_nodes: list[SduiNode] = []
    if report_ready:
        rel = _report_artifact_rel(m)
        if rel:
            fname = Path(rel).name
            report_nodes.extend([
                SduiArtifactGridNode(
                    id="sd-report-artifact",
                    title="调测报告",
                    mode="output",
                    artifacts=[
                        SduiArtifactItem(
                            id="sd-report-file",
                            label=fname,
                            path=rel,
                            kind="xlsx",
                            status="ready",
                        )
                    ],
                ),
                SduiButtonNode(
                    id="sd-report-download",
                    label=f"下载 · {fname}",
                    variant="secondary",
                    action=SduiPostUserMessage(text=f"/download_{rel}"),
                ),
                SduiButtonNode(
                    id="sd-report-preview",
                    label=f"预览 · {fname}",
                    variant="outline",
                    action=SduiOpenPreview(path=rel),
                ),
                SduiTextNode(
                    id="sd-report-hint",
                    content="点击文件名可预览；「下载」将保存 xlsx 到本地。",
                    variant="caption",
                    color="subtle",
                ),
            ])
    hint = (
        "四条 init_install 均已执行，可生成报告汇总。"
        if chain_ok
        else "可按需执行各调测命令（支持重复测试）；四条均完成后建议生成报告。"
    )
    return SduiCardNode(
        id="sd-commission-panel",
        title="命令调测 · 调度",
        tone="info",
        children=[
            SduiTextNode(
                id="sd-commission-scope",
                content=(
                    f"当前调测范围：**{scope_text}**。"
                    "按钮默认按此范围下发；按 Pod 请在左侧对话写明，如「灵衢连线检查POD1」。"
                ),
                variant="caption",
                color="accent",
            ),
            SduiTextNode(
                id="sd-commission-hint",
                content=hint,
                variant="caption",
                color="subtle",
            ),
            SduiDividerNode(),
            SduiStackNode(id="sd-commission-btns", gap="sm", children=buttons),
            *report_nodes,
        ],
    )


def _build_workspace_tab(state: dict[str, Any]) -> list[SduiNode]:
    nodes: list[SduiNode] = []
    for builder in (
        _build_context_bar,
        _build_execution_progress,
        _build_kpi_strip,
        _build_commission_command_panel,
        _build_step_detail,
        _build_input_slots,
        _build_timeline,
        lambda s: build_artifacts(s),
        lambda s: build_summary_card(_summary_bits(s), s),
        _build_sd_hitl,
    ):
        node = builder(state)
        if node:
            nodes.append(node)
    return nodes


def _build_workbench_tabs(state: dict[str, Any]) -> SduiTabGroupNode | None:
    if not state.get("steps"):
        return None
    workbench_tabs: list[tuple[str, str, Any]] = [
        ("workspace", "作业空间", _build_workspace_tab),
        ("docs", "项目文档", build_docs_tab),
        ("plan", "项目计划", build_plan_tab),
        ("task-log", "调测任务记录", build_task_log_tab),
        ("devices", "设备总览", build_devices_tab),
        ("pipeline", "流水线", build_pipeline_tab),
    ]
    tabs: list[SduiTabPanel] = []
    for tab_id, label, builder in workbench_tabs:
        children = builder(state) if callable(builder) else []
        tabs.append(SduiTabPanel(id=tab_id, label=label, children=children))
    return SduiTabGroupNode(
        id="sd-workbench",
        variant="subnav",
        activeTab="workspace",
        tabs=tabs,
    )


def project(state: dict[str, Any]) -> dict[str, Any]:
    nodes: list[SduiNode] = []

    if state.get("error"):
        nodes.append(
            SduiAlertNode(
                id="sd-error-banner",
                tone="error",
                title="执行失败",
                message=str(state.get("error")),
            )
        )

    workbench = _build_workbench_tabs(state)
    if workbench:
        nodes.append(workbench)
    elif not state.get("steps"):
        nodes.append(
            SduiEmptyStateNode(
                id="sd-idle",
                title="软件部署与调测",
                subtitle="在左侧对话启动任务后，此处将展示作业空间工作台。",
                icon="🚀",
            )
        )

    project = state.get("project") or {}
    scope = str(project.get("scope") or "all").strip() or "all"
    doc = SduiDocument(
        root=SduiStackNode(id="sd-root", gap="sm", children=nodes),
        meta={
            "skill": "software_deployment",
            "run_id": state.get("run_id", ""),
            "commission_scope": scope,
        },
    )
    return dump_sdui_json(doc)
