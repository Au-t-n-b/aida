"""software_deployment 工作台页签投影 · 项目文档 / 计划 / 调测记录 / 设备总览。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.sdui.builder import (
    SduiAccordionItem,
    SduiAccordionNode,
    SduiBadgeNode,
    SduiCardNode,
    SduiDataTableColumn,
    SduiDataTableNode,
    SduiEmptyStateNode,
    SduiMarkdownNode,
    SduiNode,
    SduiRowNode,
    SduiStatisticRowItem,
    SduiStatisticRowNode,
    SduiTextNode,
)
from agent.sdui.projector_base import collect_metrics

_COMMISSION_KEYS = ("connection", "lq_connection", "weak_light", "hccs_weak_light")

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


def _steps_map(state: dict[str, Any]) -> dict[str, str]:
    return {str(s.get("key") or ""): str(s.get("status") or "pending") for s in (state.get("steps") or [])}


def _step_record(state: dict[str, Any], key: str) -> dict[str, Any] | None:
    rec: dict[str, Any] | None = None
    for s in state.get("steps") or []:
        if s.get("key") == key:
            rec = s
    return rec


def _work_root() -> Path:
    from .bridge import get_sd_root

    return get_sd_root()


def _rel_doc_path(raw: str, root: Path) -> str | None:
    text = str(raw or "").strip().replace("\\", "/")
    if not text:
        return None
    if text.startswith("ProjectData/"):
        return text
    if "ProjectData/" in text:
        return text[text.index("ProjectData/") :]
    candidate = root / text
    if candidate.is_file():
        try:
            return str(candidate.relative_to(root)).replace("\\", "/")
        except ValueError:
            return text
    return None


def _collect_disk_doc_rows(seen: set[str]) -> list[list[str]]:
    """deploy_chain + 输入槽位磁盘兜底（rejoin 后内存 artifacts 为空时）。"""
    root = _work_root()
    chain_path = root / "ProjectData/plan/RunTime/deploy_chain.json"
    if not chain_path.is_file():
        return []
    try:
        import json

        chain = json.loads(chain_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    rows: list[list[str]] = []
    chain_slots: list[tuple[str, str, str]] = [
        ("step1_second_tasks_path", "plan_receive", "已生成"),
        ("step2_testcase_path", "plan_split", "已发布"),
        ("step3_lld_path", "plan_dispatch", "已发布"),
        ("step3_checklist_path", "plan_dispatch", "已生成"),
        ("step4_cloudops_output_path", "cloudops_init", "已生成"),
        ("step5_cloudops_manual_path", "cloudops_supplement", "已发布"),
        ("step6_cloudops_full_path", "cloudops_full", "已生成"),
        ("step6_ztp_path", "cloudops_full", "已发布"),
    ]
    for key, agent, pub in chain_slots:
        rel = _rel_doc_path(str(chain.get(key) or ""), root)
        if not rel:
            continue
        name = Path(rel).name
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append(
            [
                _DOC_AGENT_TAG.get(agent, "其他作业类"),
                name,
                _fmt_ts(chain.get("updated_at")),
                "v1.0",
                "—",
                agent,
                pub,
            ]
        )

    static_outputs: list[tuple[str, str, str]] = [
        ("ProjectData/plan/Output/third_level_tasks.json", "plan_split", "已生成"),
        ("ProjectData/plan/Output/plan_display_tree.json", "plan_split", "已生成"),
        ("ProjectData/plan/Output/device_base_table.json", "plan_dispatch", "已生成"),
        ("ProjectData/plan/RunTime/toolkit_executor.json", "toolkit_executor", "已生成"),
        ("ProjectData/plan/RunTime/toolkit_import.json", "toolkit_import", "已生成"),
    ]
    for rel, agent, pub in static_outputs:
        if not (root / rel).is_file():
            continue
        name = Path(rel).name
        if name in seen:
            continue
        seen.add(name)
        rows.append([_DOC_AGENT_TAG.get(agent, "其他作业类"), name, "—", "v1.0", "—", agent, pub])

    try:
        from agent import software_deployment_files as sd_files

        for slot_id, agent in (
            ("testcase", "plan_split"),
            ("lld_design", "plan_dispatch"),
            ("cloudops_manual", "cloudops_supplement"),
            ("check_list", "cloudops_full"),
            ("ztp_bundle", "cloudops_full"),
        ):
            found, fname = sd_files.slot_disk_status(root, slot_id)
            if not found or not fname or fname in seen:
                continue
            seen.add(fname)
            rows.append([_DOC_AGENT_TAG.get(agent, "项目管理类"), fname, "—", "v1.0", "—", agent, "已发布"])
    except Exception:
        pass

    results_root = root / "ProjectData/results"
    if results_root.is_dir():
        for cmd_dir in sorted(results_root.iterdir()):
            if not cmd_dir.is_dir():
                continue
            agent = cmd_dir.name if cmd_dir.name in _COMMISSION_KEYS else "commission_report"
            for child in sorted(cmd_dir.rglob("*")):
                if not child.is_file() or child.name.startswith("~$"):
                    continue
                if child.suffix.lower() not in {".xlsx", ".xls", ".json", ".csv", ".txt"}:
                    continue
                try:
                    rel = str(child.relative_to(root)).replace("\\", "/")
                except ValueError:
                    continue
                name = child.name
                if name in seen:
                    continue
                seen.add(name)
                rows.append([_DOC_AGENT_TAG.get(agent, "其他作业类"), name, "—", "v1.0", "—", agent, "已生成"])
    return rows


def _metric(m: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in m and m[k] is not None and m[k] != "":
            return m[k]
    return default


def _short_batch(state: dict[str, Any], project: dict[str, Any]) -> str:
    batch = str(project.get("batch_id") or state.get("run_id") or "").strip()
    if not batch:
        return "—"
    if len(batch) <= 22:
        return batch
    return f"{batch[:18]}…"

_SCENE_LABELS: dict[str, str] = {
    "product_specification": "产品规格",
    "productSpecification": "产品规格",
    "cooling": "冷却场景",
    "training": "训练场景",
    "pod_scenario": "Pod场景",
    "podScenario": "Pod场景",
}

_DOC_AGENT_TAG: dict[str, str] = {
    "plan_receive": "项目管理类",
    "plan_split": "项目管理类",
    "plan_dispatch": "工勘类",
    "cloudops_init": "项目管理类",
    "cloudops_supplement": "项目管理类",
    "cloudops_full": "项目管理类",
    "toolkit_executor": "其他作业类",
    "toolkit_import": "其他作业类",
    "connection": "其他作业类",
    "lq_connection": "其他作业类",
    "weak_light": "其他作业类",
    "hccs_weak_light": "其他作业类",
    "commission_report": "项目管理类",
}

_PENDING_DOC_SLOTS: list[tuple[str, str, str, str]] = [
    ("cloudops_supplement", "配置文件补充信息.xlsx", "cloudops_supplement", "manual_path"),
    ("cloudops_full", "ZTP文件.zip", "install_done", "ztp_present"),
]


def _fmt_ts(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return "—"
    return text[:19].replace("T", " ")


def _scene_chips(scene: dict[str, Any]) -> list[SduiNode]:
    if not scene:
        return [SduiTextNode(content="场景规格待 plan_split 后展示", variant="caption", color="subtle")]
    badges: list[SduiNode] = []
    seen: set[str] = set()
    for key, val in scene.items():
        label = _SCENE_LABELS.get(key, key)
        if label in seen:
            continue
        seen.add(label)
        badges.append(SduiBadgeNode(text=f"{label} · {val}", tone="default"))
    return [SduiRowNode(id="sd-plan-scene", gap="sm", wrap=True, children=badges)]


def _merge_scene_spec(m: dict[str, Any]) -> dict[str, Any]:
    spec: dict[str, Any] = {}
    for key in ("scene_spec",):
        raw = m.get(key)
        if isinstance(raw, dict):
            spec.update(raw)
    return spec


def _commission_flags(sm: dict[str, str]) -> dict[str, bool]:
    return {k: sm.get(k) == "completed" for k in _COMMISSION_KEYS}


def _patch_device_commission_cols(rows: list[dict[str, Any]], flags: dict[str, bool]) -> list[dict[str, Any]]:
    mapping = {
        "connection": "connection",
        "lq_connection": "lqConnection",
        "weak_light": "weakLight",
        "hccs_weak_light": "hccsWeakLight",
    }
    out: list[dict[str, Any]] = []
    for row in rows:
        patched = dict(row)
        for step_key, col in mapping.items():
            patched[col] = "已通过" if flags.get(step_key) else str(patched.get(col) or "未初始化")
        out.append(patched)
    return out


def _collect_doc_rows(state: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    seen: set[str] = set()
    m = collect_metrics(state)

    for step in state.get("steps") or []:
        key = str(step.get("key") or "")
        if not key:
            continue
        status = str(step.get("status") or "")
        pub = "已生成" if status == "completed" else ("待上传" if status == "hitl" else "草稿")
        if status != "completed" and key == "cloudops_supplement" and not m.get("manual_path"):
            pub = "待上传"
        for path in step.get("artifacts") or []:
            name = Path(str(path)).name
            if not name or name in seen:
                continue
            seen.add(name)
            rows.append(
                [
                    _DOC_AGENT_TAG.get(key, "其他作业类"),
                    name,
                    _fmt_ts(step.get("ended_at") or step.get("started_at")),
                    "v1.0",
                    "driver.py",
                    key,
                    pub if pub != "草稿" else "已生成",
                ]
            )

    if path := m.get("manual_path"):
        name = Path(str(path)).name
        if name not in seen:
            rows.append(
                ["项目管理类", name, "—", "v1.0", "—", "cloudops_supplement", "已发布"]
            )

    for step_key, fname, agent, flag_key in _PENDING_DOC_SLOTS:
        if flag_key == "manual_path" and m.get("manual_path"):
            continue
        if flag_key == "ztp_present" and m.get("ztp_present"):
            continue
        sm = _steps_map(state)
        if sm.get(step_key) == "completed":
            continue
        if fname not in seen:
            rows.append(
                [_DOC_AGENT_TAG.get(agent, "项目管理类"), fname, "—", "—", "—", agent, "待上传"]
            )
    rows.extend(_collect_disk_doc_rows(seen))
    return rows


def build_docs_tab(state: dict[str, Any]) -> list[SduiNode]:
    rows = _collect_doc_rows(state)
    if not rows:
        return [
            SduiCardNode(
                id="sd-tab-docs",
                title="项目文档列表",
                children=[
                    SduiEmptyStateNode(
                        id="sd-docs-empty",
                        title="暂无项目文档",
                        subtitle="执行 plan_receive 后，输入材料与步骤产物将在此汇总。",
                        icon="📄",
                    )
                ],
            )
        ]
    return [
        SduiCardNode(
            id="sd-tab-docs",
            title="项目文档列表",
            children=[
                SduiTextNode(
                    content=f"{len(rows)} 条 · 含输入材料与步骤产物",
                    variant="caption",
                    color="subtle",
                ),
                SduiDataTableNode(
                    id="sd-docs-table",
                    title="项目文档列表",
                    columns=["标签", "文档名称", "上传/生成时间", "版本号", "上传用户", "归属 Agent", "发布状态"],
                    rows=rows,
                ),
            ],
        )
    ]


def build_plan_tab(state: dict[str, Any]) -> list[SduiNode]:
    m = collect_metrics(state)
    scene = _merge_scene_spec(m)
    preview: list[dict[str, Any]] = m.get("third_tasks_preview") or []
    second_count = _metric(m, "second_count", "task_count", default=0)
    third_count = _metric(m, "third_count", default=len(preview))

    children: list[SduiNode] = [
        SduiTextNode(content="场景规格", variant="caption", color="subtle"),
        *_scene_chips(scene),
        SduiTextNode(
            content=f"二级任务 {second_count} 条 · 三级活动 {third_count} 条",
            variant="body",
        ),
    ]

    if preview:
        table_rows: list[list[str | int]] = []
        current_second = ""
        for task in preview:
            second = str(task.get("secondActivityName") or "")
            prefix = ""
            if second and second != current_second:
                current_second = second
                prefix = f"▸ {second}"
            else:
                prefix = "　└"
            pct = task.get("progressPct", 0)
            table_rows.append(
                [
                    f"{prefix} {task.get('thirdActivityName', '')}",
                    str(task.get("managementUnit") or "—"),
                    str(task.get("startDate") or "—"),
                    str(task.get("endDate") or "—"),
                    "—",
                    "—",
                    str(task.get("deviceList") or "—"),
                    str(task.get("taskType") or "—"),
                    str(task.get("principal") or "—"),
                    str(task.get("status") or "—"),
                    f"{pct}%",
                ]
            )
        children.append(
            SduiDataTableNode(
                id="sd-plan-table",
                title="项目计划列表",
                columns=[
                    "活动名称",
                    "机房-POD",
                    "开始日期",
                    "结束日期",
                    "实际开始",
                    "实际结束",
                    "设备型号&数量",
                    "任务类型",
                    "责任人",
                    "任务状态",
                    "进度",
                ],
                rows=table_rows,
            )
        )
    else:
        children.append(
            SduiEmptyStateNode(
                id="sd-plan-empty",
                title="计划尚未拆分",
                subtitle="完成 plan_split 后，将展示二级/三级任务与场景规格。",
                icon="📅",
            )
        )

    return [SduiCardNode(id="sd-tab-plan", title="项目计划列表", children=children)]


def _commission_status_label(rec: dict[str, Any], step_status: str | None) -> str:
    raw = str(rec.get("status") or step_status or "").strip()
    if raw in ("failed", "error"):
        return "失败"
    if raw == "completed":
        return "已完成"
    if raw in ("已完成", "失败", "进行中"):
        return raw
    return raw or "—"


def _commission_detail_body(rec: dict[str, Any]) -> str:
    err = str(rec.get("errorMessage") or "").strip()
    result_dir = str(rec.get("resultDir") or "").strip()
    lines: list[str] = []
    if err:
        lines.append(f"**失败原因**：{err}")
    summary = rec.get("summaryRows") or []
    if summary:
        lines.append("| 是否通过 | 测试光纤(根) | 设备数量 |")
        lines.append("| --- | --- | --- |")
        for row in summary:
            if isinstance(row, (list, tuple)) and len(row) >= 3:
                lines.append(f"| {row[0]} | {row[1]} | {row[2]} |")
    if result_dir:
        lines.append(f"**结果目录**：`{result_dir}`")
        lines.append("（Toolkit 执行成功后落在 `ProjectData/results/<命令>/` 下的报告与明细文件夹）")
    elif not err:
        lines.append("**结果目录**：暂无（任务成功后才会生成）")
    else:
        lines.append("**结果目录**：—（下发失败或未跑完，未生成报告目录）")
    return "\n\n".join(lines)


def _collect_commission_records(state: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key in _COMMISSION_KEYS:
        rec = _step_record(state, key)
        if not rec:
            continue
        metrics = rec.get("metrics") or {}
        raw = metrics.get("commission_record")
        if isinstance(raw, dict):
            item = dict(raw)
        else:
            item = {
                "stepKey": key,
                "taskType": SD_STEP_NAMES.get(key, key),
                "taskName": metrics.get("task_id") or key,
                "description": SD_STEP_NAMES.get(key, ""),
                "deviceCount": "—",
                "status": _commission_status_label({}, str(rec.get("status") or "")),
                "errorMessage": str(rec.get("error") or state.get("error") or ""),
            }
        item["startedAt"] = _fmt_ts(rec.get("started_at"))
        item["endedAt"] = _fmt_ts(rec.get("ended_at") or rec.get("started_at"))
        item.setdefault("executor", "driver.py")
        item["status"] = _commission_status_label(item, str(rec.get("status") or ""))
        if not item.get("errorMessage") and rec.get("error"):
            item["errorMessage"] = str(rec.get("error"))
        records.append(item)
    return records


def _task_log_table_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(rec.get("stepKey") or i),
            "taskType": str(rec.get("taskType") or "—"),
            "taskName": str(rec.get("taskName") or "—"),
            "deviceCount": str(rec.get("deviceCount") or "—"),
            "startedAt": str(rec.get("startedAt") or "—"),
            "endedAt": str(rec.get("endedAt") or "—"),
            "executor": str(rec.get("executor") or "—"),
            "status": _commission_status_label(rec, ""),
        }
        for i, rec in enumerate(records)
    ]


def build_task_log_tab(state: dict[str, Any]) -> list[SduiNode]:
    records = _collect_commission_records(state)
    if not records:
        return [
            SduiCardNode(
                id="sd-tab-task-log",
                title="调测任务记录",
                children=[
                    SduiEmptyStateNode(
                        id="sd-task-log-empty",
                        title="暂无调测任务记录",
                        subtitle="命令调测（init_install 四条）执行后，任务结果将在此展示。",
                        icon="🧪",
                    )
                ],
            )
        ]

    table_rows = _task_log_table_rows(records)
    accordion_items: list[SduiAccordionItem] = []
    for rec in records:
        accordion_items.append(
            SduiAccordionItem(
                title=f"{rec.get('taskType')} · {rec.get('taskName')}",
                body=_commission_detail_body(rec),
            )
        )

    return [
        SduiCardNode(
            id="sd-tab-task-log",
            title="调测任务记录",
            children=[
                SduiTextNode(
                    content=f"共 {len(records)} 条命令调测记录 · 可横向拖动表格 · 搜索/筛选任务类型",
                    variant="caption",
                    color="subtle",
                ),
                SduiDataTableNode(
                    id="sd-task-log-table",
                    title="调测任务记录",
                    dualMode=True,
                    dualModeEditable=False,
                    columns=[
                        SduiDataTableColumn(key="taskType", label="任务类型", width=140),
                        SduiDataTableColumn(key="taskName", label="任务名称", width=120),
                        SduiDataTableColumn(key="deviceCount", label="设备数", width=72),
                        SduiDataTableColumn(key="startedAt", label="开始时间", width=150),
                        SduiDataTableColumn(key="endedAt", label="结束时间", width=150),
                        SduiDataTableColumn(key="executor", label="执行人", width=100),
                        SduiDataTableColumn(key="status", label="状态", type="status", width=88),
                    ],
                    rows=table_rows,
                    rowKey="id",
                ),
                SduiAccordionNode(id="sd-task-log-detail", items=accordion_items),
            ],
        )
    ]


def build_devices_tab(state: dict[str, Any]) -> list[SduiNode]:
    m = collect_metrics(state)
    sm = _steps_map(state)
    flags = _commission_flags(sm)
    preview = _patch_device_commission_cols(m.get("device_tasks_preview") or [], flags)
    stats = m.get("device_stats") if isinstance(m.get("device_stats"), dict) else {}

    if not preview:
        return [
            SduiCardNode(
                id="sd-tab-devices",
                title="设备总览列表",
                children=[
                    SduiEmptyStateNode(
                        id="sd-devices-empty",
                        title="设备底表尚未生成",
                        subtitle="完成 plan_dispatch 后，将展示全量设备底表与各检查项状态。",
                        icon="🖥️",
                    )
                ],
            )
        ]

    device_count = stats.get("device_count") or m.get("device_rows") or len(preview)
    pod_count = stats.get("pod_count") or _metric(m, default="—")
    by_status = stats.get("by_status") if isinstance(stats.get("by_status"), dict) else {}
    done = by_status.get("已完成", 0)
    running = by_status.get("进行中", 0)
    pending = by_status.get("未初始化", 0)

    kpi_items = [
        SduiStatisticRowItem(title="设备行", value=str(device_count), color="accent"),
        SduiStatisticRowItem(title="Pod", value=str(pod_count), color="accent"),
        SduiStatisticRowItem(title="已初始化", value=str(done), color="success"),
        SduiStatisticRowItem(title="进行中", value=str(running), color="warning"),
        SduiStatisticRowItem(title="未初始化", value=str(pending), color="subtle"),
    ]

    table_rows: list[list[str]] = []
    for row in preview[:120]:
        table_rows.append(
            [
                str(row.get("deviceIp") or "—"),
                str(row.get("deviceName") or "—"),
                str(row.get("pod") or "—"),
                str(row.get("deviceType") or "—"),
                str(row.get("thirdTaskName") or "—"),
                str(row.get("taskStatus") or "—"),
                str(row.get("connection") or "—"),
                str(row.get("lqConnection") or "—"),
                str(row.get("weakLight") or "—"),
                str(row.get("hccsWeakLight") or "—"),
            ]
        )

    meta = f"{device_count} 台 · {pod_count} Pod"
    if len(preview) > 120:
        meta += f" · 展示前 120 / {len(preview)} 行"

    return [
        SduiCardNode(
            id="sd-tab-devices",
            title="设备总览列表",
            children=[
                SduiTextNode(content=meta, variant="caption", color="subtle"),
                SduiStatisticRowNode(id="sd-device-kpis", items=kpi_items),
                SduiDataTableNode(
                    id="sd-devices-table",
                    title="设备总览列表",
                    columns=[
                        "设备IP",
                        "设备名称",
                        "POD",
                        "设备类型",
                        "三级任务",
                        "任务状态",
                        "服务器连线",
                        "灵衢连线",
                        "弱光检查",
                        "光链路检查",
                    ],
                    rows=table_rows,
                ),
            ],
        )
    ]


def build_pipeline_tab(state: dict[str, Any]) -> list[SduiNode]:
    sm = _steps_map(state)
    rows: list[list[str]] = []
    for key in SD_STEP_ORDER:
        st = sm.get(key, "pending")
        label = {"completed": "已完成", "running": "执行中", "hitl": "待确认", "failed": "失败"}.get(st, "待开始")
        rec = _step_record(state, key)
        rows.append(
            [
                SD_STEP_NAMES.get(key, key),
                key,
                label,
                _fmt_ts((rec or {}).get("ended_at") or (rec or {}).get("started_at")),
            ]
        )
    return [
        SduiCardNode(
            id="sd-tab-pipeline",
            title="流水线",
            children=[
                SduiTextNode(
                    content=f"批次 {_short_batch(state, state.get('project') or {})} · 当前步 {SD_STEP_NAMES.get(state.get('current_step') or '', state.get('current_step') or '—')}",
                    variant="caption",
                    color="subtle",
                ),
                SduiDataTableNode(
                    id="sd-pipeline-table",
                    title="Skill 步骤流水线",
                    columns=["步骤", "step_key", "状态", "最近时间"],
                    rows=rows,
                ),
            ],
        )
    ]
