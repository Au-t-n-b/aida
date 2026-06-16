"""software_deployment 工作台页签投影 · 项目文档 / 计划 / 调测记录 / 设备总览。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.sdui.builder import (
    SduiArtifactGridNode,
    SduiArtifactItem,
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
from .steps._commission_report_loader import enrich_commission_record
from agent.sdui.projector_base import collect_metrics

_COMMISSION_KEYS = ("connection", "lq_connection", "weak_light", "hccs_weak_light")

# /ui 与 SSE 每次投影都会带上设备表；全量 1.2 万行会导致 JSON ~6MB+、服务器 500。
SDUI_DEVICE_ROWS_CAP = 500
SDUI_DEVICE_PAGE_SIZE = 50

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


def _load_device_tasks_raw() -> list[dict[str, Any]]:
    """设备底表全量（投影时读盘，避免 metrics 只保留前 N 行预览）。"""
    path = _work_root() / "ProjectData/plan/Output/device_base_table.json"
    if not path.is_file():
        return []
    try:
        import json

        raw = json.loads(path.read_text(encoding="utf-8"))
        tasks = raw.get("tasks") if isinstance(raw, dict) else raw
        return [t for t in (tasks or []) if isinstance(t, dict)]
    except Exception:
        return []


def _resolve_device_preview(
    state: dict[str, Any],
    flags: dict[str, bool],
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    from .steps._preview_metrics import device_stats, slim_device_tasks

    disk_rows = _load_device_tasks_raw()
    if disk_rows:
        total = len(disk_rows)
        stats = device_stats(disk_rows)
        preview = slim_device_tasks(
            disk_rows,
            commission_flags=flags,
            limit=SDUI_DEVICE_ROWS_CAP,
        )
        return preview, stats, total

    m = collect_metrics(state)
    preview = _patch_device_commission_cols(m.get("device_tasks_preview") or [], flags)
    stats = m.get("device_stats") if isinstance(m.get("device_stats"), dict) else {}
    return preview, stats, len(preview)


def _pod_label_from_id(pod_id: Any) -> str:
    if pod_id in (None, "", 0, "0"):
        return "超节点 —"
    return f"超节点 {pod_id}"


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


def _commission_detail_nodes(rec: dict[str, Any]) -> list[SduiNode]:
    """单条调测记录的结构化详情（汇报摘要 + 失败明细 + 报告文件）。"""
    err = str(rec.get("errorMessage") or "").strip()
    nodes: list[SduiNode] = []

    if err:
        nodes.append(
            SduiMarkdownNode(content=f"**失败原因**：{err}")
        )

    succ = rec.get("successNum")
    fail = rec.get("failNum")
    total = rec.get("totalNums")
    conclusion = str(rec.get("conclusion") or "—")
    task_id = str(rec.get("taskId") or "—")
    kpi_items = [
        SduiStatisticRowItem(title="结论", value=conclusion, color="success" if conclusion == "通过" else "warning"),
        SduiStatisticRowItem(
            title="通过/失败",
            value=str(rec.get("passFail") or f"{succ if succ is not None else '?'}/{fail if fail is not None else '?'}"),
            color="accent",
        ),
        SduiStatisticRowItem(title="设备数", value=str(rec.get("deviceCount") or "—"), color="accent"),
    ]
    if total is not None:
        kpi_items.append(SduiStatisticRowItem(title="检查项", value=str(total), color="subtle"))
    nodes.append(SduiStatisticRowNode(id=f"sd-task-kpi-{rec.get('stepKey')}", items=kpi_items, density="compact"))

    meta_bits = [f"任务号：`{task_id}`"]
    scope = str(rec.get("scope") or "").strip()
    if scope:
        meta_bits.append(f"范围：{scope}")
    pod_ids = rec.get("podIds")
    if isinstance(pod_ids, list) and pod_ids:
        meta_bits.append(f"POD：{', '.join(str(p) for p in pod_ids)}")
    result_dir = str(rec.get("resultDir") or "").strip()
    if result_dir:
        meta_bits.append(f"目录：`{result_dir}`")
    nodes.append(SduiTextNode(content=" · ".join(meta_bits), variant="caption", color="subtle"))

    failed = rec.get("failedDevices") if isinstance(rec.get("failedDevices"), list) else []
    if failed:
        rows = [[d.get("ip", "—"), d.get("reason", "—")] for d in failed if isinstance(d, dict)]
        nodes.append(
            SduiDataTableNode(
                id=f"sd-task-fail-{rec.get('stepKey')}",
                title="失败明细（节选）",
                columns=["设备 IP", "失败原因"],
                rows=rows[:15],
            )
        )

    markdown_extra = str(rec.get("markdownExtra") or "").strip()
    if markdown_extra:
        nodes.append(SduiMarkdownNode(content=f"**解析摘要**\n\n{markdown_extra}"))

    artifacts = rec.get("artifacts") if isinstance(rec.get("artifacts"), list) else []
    art_items = [
        SduiArtifactItem(
            id=f"art-{rec.get('stepKey')}-{i}",
            label=str(a.get("label") or "报告"),
            path=str(a.get("path") or ""),
            kind=a.get("kind") or "other",
            status="ready",
        )
        for i, a in enumerate(artifacts)
        if isinstance(a, dict) and a.get("path")
    ]
    if art_items:
        nodes.append(
            SduiArtifactGridNode(
                id=f"sd-task-artifacts-{rec.get('stepKey')}",
                title="报告文件",
                mode="output",
                artifacts=art_items,
            )
        )
    elif not err:
        nodes.append(
            SduiTextNode(
                content="报告文件尚未落盘（任务成功后生成 report.zip + receipt.json）",
                variant="caption",
                color="subtle",
            )
        )
    return nodes


def _collect_commission_records(state: dict[str, Any]) -> list[dict[str, Any]]:
    skill_root = _work_root()
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
        records.append(enrich_commission_record(item, skill_root))
    return records


def _task_log_table_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(rec.get("stepKey") or i),
            "taskType": str(rec.get("taskType") or "—"),
            "taskName": str(rec.get("taskName") or "—"),
            "conclusion": str(rec.get("conclusion") or "—"),
            "passFail": str(rec.get("passFail") or "—"),
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
    detail_cards: list[SduiNode] = []
    for rec in records:
        conclusion = str(rec.get("conclusion") or "")
        detail_cards.append(
            SduiCardNode(
                id=f"sd-task-detail-{rec.get('stepKey')}",
                title=f"{rec.get('taskType')} · {rec.get('taskName')}",
                density="compact",
                children=_commission_detail_nodes(rec),
            )
        )

    return [
        SduiCardNode(
            id="sd-tab-task-log",
            title="调测任务记录",
            children=[
                SduiTextNode(
                    content=(
                        f"共 {len(records)} 条命令调测记录 · "
                        "列表为概要，下方卡片含汇报摘要、失败明细与可打开的报告文件"
                    ),
                    variant="caption",
                    color="subtle",
                ),
                SduiDataTableNode(
                    id="sd-task-log-table",
                    title="调测任务记录",
                    dualMode=True,
                    dualModeEditable=False,
                    columns=[
                        SduiDataTableColumn(key="taskType", label="任务类型", width=132),
                        SduiDataTableColumn(key="taskName", label="任务名称", width=148),
                        SduiDataTableColumn(key="conclusion", label="结论", width=72),
                        SduiDataTableColumn(key="passFail", label="通过/失败", width=88),
                        SduiDataTableColumn(key="deviceCount", label="设备数", width=72),
                        SduiDataTableColumn(key="startedAt", label="开始时间", width=140),
                        SduiDataTableColumn(key="endedAt", label="结束时间", width=140),
                        SduiDataTableColumn(key="executor", label="执行人", width=92),
                        SduiDataTableColumn(key="status", label="状态", type="status", width=80),
                    ],
                    rows=table_rows,
                    rowKey="id",
                ),
                *detail_cards,
            ],
        )
    ]


def build_device_table_page(
    *,
    page: int = 1,
    page_size: int = SDUI_DEVICE_PAGE_SIZE,
    pod: str = "",
    commission_flags: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """设备底表分页（供 /devices API；统计仍基于全量）。"""
    from .steps._preview_metrics import device_stats, slim_device_tasks

    disk_rows = _load_device_tasks_raw()
    flags = commission_flags or {}
    if not disk_rows:
        return {"total": 0, "page": page, "pageSize": page_size, "rows": [], "stats": {}}

    slimmed = slim_device_tasks(disk_rows, commission_flags=flags, limit=0)
    if pod:
        slimmed = [r for r in slimmed if str(r.get("pod") or "") == pod]
    total = len(slimmed)
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    start = (page - 1) * page_size
    rows = slimmed[start : start + page_size]
    return {
        "total": total,
        "page": page,
        "pageSize": page_size,
        "pageCount": max(1, (total + page_size - 1) // page_size) if total else 0,
        "rows": rows,
        "stats": device_stats(disk_rows),
    }


def build_devices_tab(state: dict[str, Any]) -> list[SduiNode]:
    try:
        return _build_devices_tab_inner(state)
    except Exception as exc:
        return [
            SduiCardNode(
                id="sd-tab-devices",
                title="设备总览列表",
                children=[
                    SduiEmptyStateNode(
                        id="sd-devices-error",
                        title="设备总览暂不可用",
                        subtitle=f"投影异常：{exc}",
                        icon="⚠️",
                    )
                ],
            )
        ]


def _build_devices_tab_inner(state: dict[str, Any]) -> list[SduiNode]:
    sm = _steps_map(state)
    flags = _commission_flags(sm)
    preview, stats, total_rows = _resolve_device_preview(state, flags)

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

    device_count = stats.get("device_count") or len(preview)
    task_rows = stats.get("task_rows") or len(preview)
    pod_count = stats.get("pod_count") or "—"
    by_status = stats.get("by_status") if isinstance(stats.get("by_status"), dict) else {}
    done = by_status.get("已完成", 0)
    running = by_status.get("进行中", 0)
    pending = by_status.get("未初始化", 0)
    by_pod = stats.get("by_pod") if isinstance(stats.get("by_pod"), dict) else {}

    kpi_items = [
        SduiStatisticRowItem(title="设备", value=str(device_count), color="accent"),
        SduiStatisticRowItem(title="超节点", value=str(pod_count), color="accent"),
        SduiStatisticRowItem(title="底表行", value=str(task_rows), color="subtle"),
        SduiStatisticRowItem(title="已初始化", value=str(done), color="success"),
        SduiStatisticRowItem(title="进行中", value=str(running), color="warning"),
        SduiStatisticRowItem(title="未初始化", value=str(pending), color="subtle"),
    ]

    page_size = SDUI_DEVICE_PAGE_SIZE
    pod_summary = ""
    if by_pod:
        pod_bits = [f"{_pod_label_from_id(k)}×{v}" for k, v in list(by_pod.items())[:6]]
        if len(by_pod) > 6:
            pod_bits.append("…")
        pod_summary = " · ".join(pod_bits)

    meta = f"{device_count} 台 · {pod_count} 个超节点 · 底表 {task_rows} 行"
    if pod_summary:
        meta += f" · {pod_summary}"
    if total_rows > len(preview):
        meta += f" · 界面展示前 {len(preview)} 行（分页 {page_size} 条/页）· 全量 GET /agent/software_deployment/devices"

    table_subtitle = None
    if total_rows > len(preview):
        table_subtitle = (
            f"共 {total_rows} 行 · 当前载入 {len(preview)} 行 · "
            "翻页仅覆盖已载入部分；全量请调 devices 分页接口或导出 device_base_table.json"
        )

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
                    subtitle=table_subtitle,
                    columns=[
                        SduiDataTableColumn(key="deviceIp", label="设备IP", width=132, nowrap=True),
                        SduiDataTableColumn(key="deviceName", label="设备名称", nowrap=True),
                        SduiDataTableColumn(key="pod", label="超节点", width=96, nowrap=True),
                        SduiDataTableColumn(key="deviceType", label="设备类型", width=108),
                        SduiDataTableColumn(key="thirdTaskName", label="三级任务", width=120),
                        SduiDataTableColumn(key="taskStatus", label="任务状态", type="status", width=88),
                        SduiDataTableColumn(key="connection", label="服务器连线", type="status", width=96),
                        SduiDataTableColumn(key="lqConnection", label="灵衢连线", type="status", width=88),
                        SduiDataTableColumn(key="weakLight", label="弱光检查", type="status", width=88),
                        SduiDataTableColumn(key="hccsWeakLight", label="光链路检查", type="status", width=96),
                    ],
                    rows=preview,
                    rowKey="id",
                    filterKeys=["pod"],
                    pageSize=page_size,
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
