# -*- coding: utf-8 -*-
"""工作台 SDUI 同步：十一步 Stepper、摘要、分步产物（可点击 openPreview）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deploy_chain import load_chain, sync_step3_from_state
from guidance_actions import sd_dashboard_intent_text
from paths import (
    cloudops_input_dir,
    load_plan_runtime_step,
    plan_action_for_step,
    plan_dispatch_input_dir,
    plan_receive_dir,
    plan_runtime_action_name,
    plan_split_input_dir,
    resolve_slot,
)
from resume_router import recommended_next_action, step_done_flags
from step_ui import STEP_TITLES, TOTAL_STEPS
from toolkit_executor import load_executor_config, mask_secret

DASHBOARD_DOC_ID = "dashboard:software-deployment"
DASHBOARD_SYNTHETIC = "skill-ui://SduiView?dataFile=data/dashboard.json"

_STEPPER_STEPS: list[dict[str, str]] = [
    {"id": "sd:s1", "title": "① 接收", "tabId": "s1"},
    {"id": "sd:s2", "title": "② 拆分", "tabId": "s2"},
    {"id": "sd:s3", "title": "③ 下发", "tabId": "s3"},
    {"id": "sd:s4", "title": "④ 初配", "tabId": "s4"},
    {"id": "sd:s5", "title": "⑤ 补充", "tabId": "s5"},
    {"id": "sd:s6", "title": "⑥ 完整", "tabId": "s6"},
    {"id": "sd:s7", "title": "⑦ 调测设备", "tabId": "s7"},
    {"id": "sd:s8", "title": "⑧ 导入", "tabId": "s8"},
    {"id": "sd:s9", "title": "⑨ 部署测试", "tabId": "s9"},
    {"id": "sd:s10", "title": "⑩ 子系统", "tabId": "s10"},
    {"id": "sd:s11", "title": "⑪ 集群", "tabId": "s11"},
]

_HYDRATE_NODE_IDS = frozenset(
    {
        "sd-overview-card",
        "sd-actions-primary",
        "sd-toolbar",
        "stepper-main",
        "summary-text",
        "sd-stage-tabs",
        *(f"sd-kv-{i}" for i in range(1, TOTAL_STEPS + 1)),
        *(f"sd-art-{i}" for i in range(1, TOTAL_STEPS + 1)),
    }
)

_RUNTIME_ACTION_LABELS: dict[str, str] = {
    "plan_receive": "接收二级任务",
    "plan_split": "拆分调测计划",
    "plan_dispatch": "下发设备底表",
    "plan_regenerate": "一键重算",
    "cloudops_init_start": "CloudOps 初配",
    "cloudops_supplement_start": "CloudOps 补充",
    "cloudops_full_start": "CloudOps 完整配置",
    "cloudops_material_check": "检查 ZTP / 测试参数",
    "cloudops_ztp_upload_done": "上传 / 刷新 ZTP",
    "cloudops_params_upload_done": "上传 / 刷新测试参数",
    "toolkit_executor_configure": "配置调测设备",
    "toolkit_import_start": "导入 Toolkit（步骤 8）",
    "sd_continue": "继续（执行推荐步骤）",
    "sd_start": "查看进度说明",
    "sd_resume": "查看进度说明",
    "upstream_check": "检查材料",
    "sd_reset": "演示重置",
}


def _latest_run_for(skill_root: Path, task_type: str) -> dict[str, Any]:
    """读 results/index.json 取某 task_type 最近一次运行（含 receipt 的通过/失败）。"""
    idx_path = skill_root / "ProjectData" / "results" / "index.json"
    if not idx_path.is_file():
        return {}
    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    runs = idx.get("runs") if isinstance(idx, dict) else None
    if not isinstance(runs, list):
        return {}
    for entry in reversed(runs):
        if isinstance(entry, dict) and entry.get("taskType") == task_type:
            data = dict(entry)
            receipt_path = str(entry.get("receiptPath") or "")
            try:
                if receipt_path and Path(receipt_path).is_file():
                    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
                    rd = receipt.get("lastQuery", {}).get("data", {})
                    if isinstance(rd, dict):
                        data["successNum"] = rd.get("successNum")
                        data["failNum"] = rd.get("failNum")
                        data["totalNums"] = rd.get("totalNums")
                    data["deviceCount"] = receipt.get("deviceCount")
            except Exception:
                pass
            return data
    return {}


def _result_kv(label: str, run: dict[str, Any], done_at: Any) -> list[tuple[str, str]]:
    if not done_at:
        return [(label, "未执行")]
    succ = run.get("successNum")
    fail = run.get("failNum")
    if succ is not None or fail is not None:
        return [(label, f"通过 {succ if succ is not None else '?'} / 失败 {fail if fail is not None else '?'}")]
    return [(label, "已完成")]


def _ws(path: Path, skill_root: Path) -> str:
    ws_root = skill_root.resolve().parent.parent
    rel = path.resolve().relative_to(ws_root)
    return f"workspace/{rel.as_posix()}"


def _artifact(*, aid: str, label: str, path: Path, kind: str, skill_root: Path) -> dict[str, Any]:
    exists = path.is_file()
    return {
        "id": aid,
        "label": label,
        "path": _ws(path, skill_root) if exists else "",
        "kind": kind,
        "status": "ready" if exists else "missing",
    }


def _glob_artifacts(dir_path: Path, pattern: str, *, prefix: str, skill_root: Path, kind: str) -> list[dict[str, Any]]:
    if not dir_path.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(dir_path.glob(pattern))[:8]:
        if p.is_file():
            out.append(_artifact(aid=f"{prefix}-{p.name}", label=p.name, path=p, kind=kind, skill_root=skill_root))
    return out


def _step_statuses(skill_root: Path) -> list[str]:
    from plan_chain import migrate_chain_from_state

    step = load_plan_runtime_step(skill_root)
    chain = migrate_chain_from_state(skill_root)
    done = step_done_flags(chain, step)

    statuses: list[str] = []
    cur_set = False
    for d in done:
        if d:
            statuses.append("completed")
        elif not cur_set:
            statuses.append("running")
            cur_set = True
        else:
            statuses.append("waiting")
    return statuses


def _recommended_runtime_action(skill_root: Path) -> str:
    """与 ``runtime/resume_router.py`` / driver 入口一致。"""
    return recommended_next_action(skill_root)


def _dashboard_button(
    *,
    btn_id: str,
    label: str,
    action: str,
    variant: str = "secondary",
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "Button",
        "id": btn_id,
        "label": label,
        "variant": variant,
        "action": {
            "kind": "post_user_message",
            "text": sd_dashboard_intent_text(action, extra_payload=extra_payload),
        },
    }


def _build_primary_actions_row() -> dict[str, Any]:
    return {
        "type": "Row",
        "id": "sd-actions-primary",
        "gap": "md",
        "align": "center",
        "wrap": True,
        "children": [
            _dashboard_button(
                btn_id="btn-start-skill",
                label="开始部署调测",
                action="sd_start",
                variant="primary",
            ),
            _dashboard_button(btn_id="btn-check-materials", label="检查材料", action="upstream_check"),
            _dashboard_button(
                btn_id="btn-toolkit-import",
                label="导入 Toolkit（步骤 8）",
                action="toolkit_import_start",
            ),
        ],
    }


def _build_step8_commands_row(skill_root: Path) -> dict[str, Any] | None:
    """步骤 8 完成后，露出步骤 9 测试命令按钮（连线检查/灵衢连线检查）。"""
    chain = load_chain(skill_root)
    if not chain.get("step8_toolkit_import_at"):
        return None
    return {
        "type": "Row",
        "id": "sd-step9-cmds",
        "gap": "sm",
        "align": "center",
        "wrap": True,
        "children": [
            _dashboard_button(
                btn_id="btn-conn-check",
                label="服务器连线检查",
                action="connection_check_start",
            ),
            _dashboard_button(
                btn_id="btn-lq-conn-check",
                label="灵衢连线检查（全量）",
                action="lq_connection_check",
                extra_payload={"scope": "all"},
            ),
            _dashboard_button(
                btn_id="btn-lq-config-check",
                label="灵衢配置检查",
                action="commission_run",
                extra_payload={"command": "lq_config_check", "scope": "all"},
            ),
            _dashboard_button(
                btn_id="btn-lq-health-check",
                label="灵衢健康检查",
                action="commission_run",
                extra_payload={"command": "lq_health_check", "scope": "all"},
            ),
            _dashboard_button(
                btn_id="btn-hccs-weak-light",
                label="灵衢光链路检查",
                action="commission_run",
                extra_payload={"command": "hccs_weak_light", "scope": "all"},
            ),
        ],
    }


def _build_toolbar_row(skill_root: Path) -> dict[str, Any]:
    next_action = _recommended_runtime_action(skill_root)
    try:
        cur = next(i for i, s in enumerate(_step_statuses(skill_root)) if s == "running") + 1
    except StopIteration:
        cur = TOTAL_STEPS
    children: list[dict[str, Any]] = [
        _dashboard_button(
            btn_id="btn-continue-next",
            label="继续",
            action=next_action,
            variant="primary",
        ),
        _dashboard_button(btn_id="btn-refresh-workbench", label="流程说明", action="sd_start"),
        _dashboard_button(btn_id="btn-plan-regenerate", label="一键重算", action="plan_regenerate"),
        _dashboard_button(
            btn_id="btn-demo-reset",
            label="演示重置",
            action="sd_reset",
            extra_payload={"from_step": cur, "reset_scope": "all"},
        ),
    ]
    return {
        "type": "Row",
        "id": "sd-toolbar",
        "gap": "sm",
        "align": "center",
        "wrap": True,
        "children": children,
    }


def _summary_text(skill_root: Path, statuses: list[str]) -> str:
    step = load_plan_runtime_step(skill_root)
    try:
        cur = next(i for i, s in enumerate(statuses) if s == "running") + 1
    except StopIteration:
        cur = TOTAL_STEPS if statuses and statuses[-1] == "completed" else 1
    title = STEP_TITLES.get(cur, "")
    done_n = sum(1 for s in statuses if s == "completed")
    return (
        f"当前进度：**步骤 {cur}/{TOTAL_STEPS} · {title}**（已完成 {done_n}/{TOTAL_STEPS}）。"
        f" plan 状态 `{step}`；点击 Stepper 芯片或下方 Tab 查看本步输入/输出件。"
    )


def _kv_items_for_step(skill_root: Path, step_n: int) -> list[dict[str, str]]:
    step = load_plan_runtime_step(skill_root)
    chain = load_chain(skill_root)
    plan = skill_root / "ProjectData" / "plan"
    ex = load_executor_config(skill_root)
    rows: list[tuple[str, str]] = []

    if step_n == 1:
        rows.append(("运行状态", step))
        slot = resolve_slot("second_level_tasks", skill_root=skill_root)
        rows.append(("收件箱", "有文件" if not slot.get("missing") else "待上传"))
    elif step_n == 2:
        rows.append(("运行状态", step))
        tc = resolve_slot("testcase", skill_root=skill_root)
        rows.append(("验收用例", (str(tc.get("primary") or "待上传"))[-48:]))
        sp = plan / "RunTime" / "scene.json"
        rows.append(("scene.json", "已生成" if sp.is_file() else "未生成"))
    elif step_n == 3:
        rows.append(("运行状态", step))
        lld = resolve_slot("lld_design", skill_root=skill_root)
        rows.append(("LLD", "已就绪" if not lld.get("missing") else "待上传"))
        rec = plan / "Output" / "dispatch_record.json"
        if rec.is_file():
            try:
                raw = json.loads(rec.read_text(encoding="utf-8"))
                stats = raw.get("dispatchStats") or {}
                rows.append(("展开行数", str(stats.get("rows", "—"))))
            except Exception:
                pass
    elif step_n == 4:
        rows.append(("初配时间", str(chain.get("step4_cloudops_init_at") or "未完成")))
        rows.append(("LLD 来源", (str(chain.get("step4_cloudops_lld_source") or "—"))[-48:]))
    elif step_n == 5:
        rows.append(("补充时间", str(chain.get("step5_cloudops_supplement_at") or "未完成")))
        rows.append(("完工清单", "已检测" if chain.get("step5_checklist_detected") else "待放入 input/cloudops"))
    elif step_n == 6:
        rows.append(("完整配置时间", str(chain.get("step6_cloudops_full_at") or "未完成")))
        rows.append(("材料检查", str(chain.get("step6_materials_checked_at") or "未检查")))
        rows.append(("ZTP", "已上传" if chain.get("step6_ztp_at") else "未上传（可后补）"))
        rows.append(("测试参数", "已上传" if chain.get("step6_params_at") else "未上传（可后补）"))
    elif step_n == 7:
        rows.append(("执行机 IP", str(ex.get("base_url_ip") or "未配置")))
        rows.append(("端口", str(ex.get("base_url_port") or "28880")))
        rows.append(("SK", mask_secret(str(ex.get("secret_key") or "")) or "未配置"))
        rows.append(("网关服务", "默认已启动（现场）" if ex.get("gateway_service_ack", True) else "待确认"))
        rows.append(("配置时间", str(chain.get("step7_executor_config_at") or "未完成")))
    elif step_n == 8:
        rows.append(("导入 Toolkit", str(chain.get("step8_toolkit_import_at") or "待步骤 8")))
        rows.append(("说明", "对接 deployment_cloudops_workbench"))
    elif step_n == 9:
        at = chain.get("step9_init_install_at")
        rows.extend(_result_kv("服务器连线检查", _latest_run_for(skill_root, "connection"), at))
        rows.extend(_result_kv("灵衢连线检查", _latest_run_for(skill_root, "lq_connection"), at))
    elif step_n == 10:
        rows.append(("子系统测试", str(chain.get("step10_subsystem_test_at") or "—")))
    elif step_n == 11:
        rows.append(("集群系统测试", str(chain.get("step11_cluster_test_at") or "—")))

    return [{"key": k, "value": v} for k, v in rows]


def _artifacts_for_step(skill_root: Path, step_n: int) -> list[dict[str, Any]]:
    plan = skill_root / "ProjectData" / "plan"
    out_dir = plan / "Output"
    arts: list[dict[str, Any]] = []

    if step_n == 1:
        arts.extend(_glob_artifacts(plan_receive_dir(skill_root), "*", prefix="in1", skill_root=skill_root, kind="other"))
        p = plan / "Input" / "second_level_tasks.json"
        if p.is_file():
            arts.append(_artifact(aid="out-second", label="second_level_tasks.json", path=p, kind="json", skill_root=skill_root))
    elif step_n == 2:
        arts.extend(_glob_artifacts(plan_split_input_dir(skill_root), "*", prefix="in2", skill_root=skill_root, kind="other"))
        for name in ("third_level_tasks.json",):
            p = out_dir / name
            if p.is_file():
                arts.append(_artifact(aid=f"out-{name}", label=name, path=p, kind="json", skill_root=skill_root))
        sp = plan / "RunTime" / "scene.json"
        if sp.is_file():
            arts.append(_artifact(aid="out-scene", label="scene.json", path=sp, kind="json", skill_root=skill_root))
    elif step_n == 3:
        arts.extend(_glob_artifacts(plan_dispatch_input_dir(skill_root), "*.xlsx", prefix="in3", skill_root=skill_root, kind="xlsx"))
        for p in sorted(out_dir.glob("全量设备完工清单列表_*.xlsx"))[:3]:
            arts.append(_artifact(aid=f"out-{p.name}", label=p.name, path=p, kind="xlsx", skill_root=skill_root))
        dr = out_dir / "dispatch_record.json"
        if dr.is_file():
            arts.append(_artifact(aid="out-dispatch-rec", label="dispatch_record.json", path=dr, kind="json", skill_root=skill_root))
    elif step_n == 4:
        p = out_dir / "CloudOps初始配置.xlsx"
        if p.is_file():
            arts.append(_artifact(aid="out-co-init", label=p.name, path=p, kind="xlsx", skill_root=skill_root))
    elif step_n == 5:
        arts.extend(_glob_artifacts(cloudops_input_dir(skill_root), "*.xlsx", prefix="in5", skill_root=skill_root, kind="xlsx"))
        p = out_dir / "CloudOps配置_手工补充.xlsx"
        if p.is_file():
            arts.append(_artifact(aid="out-co-manual", label=p.name, path=p, kind="xlsx", skill_root=skill_root))
    elif step_n == 6:
        arts.extend(_glob_artifacts(cloudops_input_dir(skill_root), "*.xlsx", prefix="in6-cl", skill_root=skill_root, kind="xlsx"))
        p = out_dir / "CloudOps完整配置文件.xlsx"
        if p.is_file():
            arts.append(_artifact(aid="out-co-full", label=p.name, path=p, kind="xlsx", skill_root=skill_root))
        rel = str(load_chain(skill_root).get("step6_ztp_path") or "").strip()
        ws_root = skill_root.resolve().parent.parent
        if rel:
            rel_path = rel.removeprefix("workspace/").lstrip("/")
            zpath = (ws_root / rel_path).resolve()
            if zpath.is_file():
                arts.append(_artifact(aid="out-ztp", label=zpath.name, path=zpath, kind="zip", skill_root=skill_root))
        zlatest = cloudops_input_dir(skill_root) / "ZTP文件_latest.zip"
        if zlatest.is_file():
            arts.append(_artifact(aid="out-ztp-latest", label=zlatest.name, path=zlatest, kind="zip", skill_root=skill_root))
        arts.extend(_glob_artifacts(cloudops_input_dir(skill_root), "ZTP*.zip", prefix="in6-ztp", skill_root=skill_root, kind="zip"))
        arts.extend(_glob_artifacts(cloudops_input_dir(skill_root), "*task_params*.xlsx", prefix="in6-params", skill_root=skill_root, kind="xlsx"))
        arts.extend(_glob_artifacts(cloudops_input_dir(skill_root), "*测试参数*.xlsx", prefix="in6-params-cn", skill_root=skill_root, kind="xlsx"))
    elif step_n == 7:
        ep = plan / "RunTime" / "toolkit_executor.json"
        if ep.is_file():
            arts.append(_artifact(aid="out-executor-json", label="toolkit_executor.json", path=ep, kind="json", skill_root=skill_root))
    elif step_n == 8:
        p = out_dir / "CloudOps完整配置文件.xlsx"
        if p.is_file():
            arts.append(_artifact(aid="in-co-full-toolkit", label="→ Toolkit 完整配置", path=p, kind="xlsx", skill_root=skill_root))
    elif step_n >= 9:
        results_dir = skill_root / "ProjectData" / "results"
        agg = results_dir / "调测报告汇总_latest.xlsx"
        if agg.is_file():
            arts.append(
                _artifact(
                    aid="out-report-aggregate",
                    label=agg.name,
                    path=agg,
                    kind="xlsx",
                    skill_root=skill_root,
                )
            )
    if step_n == 9:
        results_dir = skill_root / "ProjectData" / "results"
        for task_type in ("connection", "lq_connection"):
            tdir = results_dir / task_type
            if not tdir.is_dir():
                continue
            for rpt in sorted(tdir.glob("*/report.zip"))[-3:]:
                label = f"{task_type}/{rpt.parent.name}"
                arts.append(_artifact(aid=f"out10-{rpt.parent.name}", label=label, path=rpt, kind="zip", skill_root=skill_root))
    elif step_n >= 10:
        arts.extend(_glob_artifacts(skill_root / "ProjectData" / "Output", "*.zip", prefix=f"out{step_n}", skill_root=skill_root, kind="zip"))

    return arts


def build_dashboard_merge_ops(skill_root: Path) -> list[dict[str, Any]]:
    statuses = _step_statuses(skill_root)
    try:
        default_tab = f"s{next(i for i, s in enumerate(statuses) if s == 'running') + 1}"
    except StopIteration:
        default_tab = f"s{TOTAL_STEPS}"

    stepper_steps = [{**meta, "status": st} for meta, st in zip(_STEPPER_STEPS, statuses)]

    ops: list[dict[str, Any]] = [
        {
            "op": "merge",
            "target": {"by": "id", "nodeId": "sd-overview-card"},
            "value": {
                "type": "Card",
                "id": "sd-overview-card",
                "title": "软件部署与调测 · 当前进展",
                "density": "compact",
                "children": [
                    row
                    for row in (
                        _build_primary_actions_row(),
                        _build_toolbar_row(skill_root),
                        _build_step8_commands_row(skill_root),
                    )
                    if row is not None
                ],
            },
        },
        {
            "op": "merge",
            "target": {"by": "id", "nodeId": "stepper-main"},
            "value": {
                "type": "Stepper",
                "id": "stepper-main",
                "orientation": "horizontal",
                "orientationOnNarrow": "vertical",
                "scrollable": True,
                "linkedTabsId": "sd-stage-tabs",
                "steps": stepper_steps,
            },
        },
        {
            "op": "merge",
            "target": {"by": "id", "nodeId": "summary-text"},
            "value": {
                "type": "Text",
                "id": "summary-text",
                "variant": "body",
                "color": "subtle",
                "content": _summary_text(skill_root, statuses),
            },
        },
        {
            "op": "merge",
            "target": {"by": "id", "nodeId": "sd-stage-tabs"},
            "value": {
                "type": "Tabs",
                "id": "sd-stage-tabs",
                "linkedTabsId": "sd-stage-tabs",
                "defaultTabId": default_tab,
                "tabs": [
                    {
                        "id": f"s{i}",
                        "label": _STEPPER_STEPS[i - 1]["title"],
                        "icon": "fileText" if i <= 3 else ("clipboardCheck" if i <= 8 else "terminal"),
                        "children": [
                            {
                                "type": "KeyValueList",
                                "id": f"sd-kv-{i}",
                                "items": _kv_items_for_step(skill_root, i),
                            },
                            {
                                "type": "ArtifactGrid",
                                "id": f"sd-art-{i}",
                                "title": "本步输入/输出（点击预览）",
                                "mode": "input" if i <= 3 or i == 8 else "output",
                                "artifacts": _artifacts_for_step(skill_root, i),
                            },
                        ],
                    }
                    for i in range(1, TOTAL_STEPS + 1)
                ],
            },
        },
    ]
    return ops


def _hydrate_path(skill_root: Path) -> Path:
    return skill_root / "ProjectData" / "RunTime" / "stage_sdui_hydrate.json"


def build_baseline_dashboard_document(skill_root: Path) -> dict[str, Any]:
    """生成 ``data/dashboard.json`` 基线（含 Card 工具栏 + hydrate 节点）。"""
    ops = build_dashboard_merge_ops(skill_root)
    nodes: dict[str, Any] = {}
    for op in ops:
        if op.get("op") != "merge":
            continue
        t = op.get("target") if isinstance(op.get("target"), dict) else {}
        nid = str(t.get("nodeId") or "")
        val = op.get("value")
        if nid and isinstance(val, dict):
            nodes[nid] = val
    children: list[dict[str, Any]] = []
    for key in ("sd-overview-card", "stepper-main", "summary-text", "sd-stage-tabs"):
        if key in nodes:
            children.append(nodes[key])
    return {
        "schemaVersion": 1,
        "type": "SduiDocument",
        "meta": {
            "docId": DASHBOARD_DOC_ID,
            "provenance": "software_deployment",
            "role": "dashboard",
        },
        "root": {"type": "Stack", "gap": "lg", "children": children},
    }


def persist_stage_hydrate(skill_root: Path) -> None:
    ops = build_dashboard_merge_ops(skill_root)
    nodes: dict[str, Any] = {}
    for op in ops:
        if op.get("op") != "merge":
            continue
        t = op.get("target") if isinstance(op.get("target"), dict) else {}
        nid = str(t.get("nodeId") or "")
        val = op.get("value")
        if nid and isinstance(val, dict):
            nodes[nid] = val
    p = _hydrate_path(skill_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schemaVersion": 1, "nodes": nodes}, ensure_ascii=False, indent=2), encoding="utf-8")
    baseline = skill_root / "data" / "dashboard.json"
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text(
        json.dumps(build_baseline_dashboard_document(skill_root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def emit_dashboard_patch_event(
    *,
    thread_id: str,
    skill_name: str,
    skill_run_id: str,
    skill_root: Path,
    timestamp_ms: int,
) -> None:
    import sys

    persist_stage_hydrate(skill_root)
    payload = {
        "syntheticPath": DASHBOARD_SYNTHETIC,
        "docId": DASHBOARD_DOC_ID,
        "ops": build_dashboard_merge_ops(skill_root),
    }
    evt = {
        "event": "dashboard.patch",
        "threadId": thread_id,
        "skillName": skill_name,
        "skillRunId": skill_run_id,
        "timestamp": timestamp_ms,
        "payload": payload,
    }
    line = (json.dumps(evt, ensure_ascii=False) + "\n").encode("utf-8", errors="replace")
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.flush()
