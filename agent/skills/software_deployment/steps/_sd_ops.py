"""software_deployment 业务操作 · 供各 BaseStep 进程内调用仓库内 runtime 脚本（非 subprocess）。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..bridge import ensure_gateway_config, ensure_runtime, import_sd_script

INIT_INSTALL_COMMANDS: tuple[str, ...] = (
    "connection",
    "lq_connection",
    "weak_light",
    "hccs_weak_light",
)

COMMAND_LABELS: dict[str, str] = {
    "connection": "服务器连线检查",
    "lq_connection": "灵衢连线检查",
    "weak_light": "服务器弱光检查",
    "hccs_weak_light": "灵衢光链路检查",
}


def _plan_dir(root: Path) -> Path:
    return root / "ProjectData" / "plan"


def _save_json(path: Path, data: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":") if compact else None, indent=None if compact else 2)
    path.write_text(text, encoding="utf-8")


def _load_scene(root: Path) -> dict[str, Any]:
    p = _plan_dir(root) / "RunTime" / "scene.json"
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def scene_is_multi_pods(root: Path) -> bool:
    scene = _load_scene(root)
    pod = str(scene.get("pod_info") or scene.get("podInfo") or "").strip().lower()
    return pod == "multi_pods"


_SCENE_LABELS: dict[str, str] = {
    "air_cooling": "风冷",
    "liquid_cooling": "液冷",
    "infer": "推理",
    "train": "训练",
    "train_infer": "训推",
    "single_pod": "单 Pod",
    "multi_pods": "多 Pod",
}


def scene_summary_text(root: Path) -> str:
    """plan_split HITL 展示用：当前 scene.json 规格摘要。"""
    scene = _load_scene(root)
    if not scene:
        return "场景待同步（将按 projects_registry 默认 infer/单Pod）"
    parts: list[str] = []
    for key, label in (
        ("train_infer_scene", "训练/推理"),
        ("pod_info", "Pod"),
        ("cooling", "制冷"),
        ("product_specification", "产品规格"),
    ):
        raw = scene.get(key) or scene.get(key.replace("_", "").title()) or ""
        val = str(raw).strip()
        if val:
            parts.append(f"{label}={_SCENE_LABELS.get(val, val)}")
    return " · ".join(parts) if parts else "默认场景"


def _chain(root: Path) -> dict[str, Any]:
    ensure_runtime(root)
    from deploy_chain import load_chain  # noqa: WPS433

    return load_chain(root)


def _merge_chain(root: Path, **kw: Any) -> dict[str, Any]:
    ensure_runtime(root)
    from deploy_chain import merge_chain  # noqa: WPS433

    return merge_chain(root, **kw)


def op_plan_receive(root: Path, *, prefer_inbox: bool = True) -> dict[str, Any]:
    mod = import_sd_script(root, "1_plan_receive", "receive_tasks")
    return mod.run_receive(root, prefer_inbox=prefer_inbox)


def op_plan_split(root: Path, *, project_id: str = "nanobot-local") -> dict[str, Any]:
    ensure_runtime(root)
    from paths import resolve_slot  # noqa: WPS433
    from plan_chain import mark_step2_complete  # noqa: WPS433
    from projects_registry import sync_scene_from_projects  # noqa: WPS433

    receive = import_sd_script(root, "1_plan_receive", "receive_tasks")
    split_mod = import_sd_script(root, "2_plan_split", "plan_split")

    scene, sync_err = sync_scene_from_projects(root, project_id=project_id or None)
    if sync_err:
        return {"ok": False, "error": f"场景同步失败：{sync_err}"}

    tc = resolve_slot("testcase", skill_root=root)
    if tc.get("missing"):
        return {"ok": False, "error": "缺少验收用例 Word（ProjectData/input/plan_split/*.docx）"}

    second_tasks = receive.load_second_tasks(root)
    if not second_tasks:
        return {"ok": False, "error": "未找到二级任务（plan_receive 或 plan/Input）"}

    # Raw skill 临时阶段要求拆分前从收件箱刷新二级任务快照，保证 Excel 真值生效。
    receive.persist_received_tasks(root, second_tasks)
    from plan_chain import mark_step1_complete  # noqa: WPS433

    mark_step1_complete(
        root,
        second_tasks_path=_plan_dir(root) / "Input" / "second_level_tasks.json",
        task_count=len(second_tasks),
    )

    report = split_mod.split_plan_report(
        second_tasks,
        scene=scene or {},
        project_id=project_id,
        skill_root=root,
    )
    third_rows = report.get("tasks") or []
    plan_tree = report.get("tree") or []
    third_path = _plan_dir(root) / "Output" / "third_level_tasks.json"
    tree_path = _plan_dir(root) / "Output" / "plan_display_tree.json"
    _save_json(third_path, {"schemaVersion": 1, "tasks": third_rows})
    _save_json(
        tree_path,
        {
            "schemaVersion": 1,
            "secondCount": len(second_tasks),
            "thirdCount": len(third_rows),
            "tree": plan_tree,
            "rows": split_mod.flatten_plan_tree(plan_tree),
        },
    )
    mark_step2_complete(
        root,
        third_tasks_path=third_path,
        third_task_count=len(third_rows),
        testcase_path=str(tc.get("primary") or "") or None,
    )
    _merge_chain(root, step1_scene_path="ProjectData/plan/RunTime/scene.json")
    missing: list[str] = []
    try:
        from paths import load_second_to_third  # noqa: WPS433

        task_map = load_second_to_third(root)
        for row in second_tasks:
            name = str(row.get("activityName") or row.get("name") or "").strip()
            if name and name not in task_map and name not in missing:
                missing.append(name)
    except Exception:
        missing = []
    from ._preview_metrics import slim_scene_spec, slim_third_tasks

    return {
        "ok": True,
        "second_count": len(second_tasks),
        "third_count": len(third_rows),
        "testcase_path": str(tc.get("primary") or ""),
        "scene": report.get("scene") or {},
        "scene_spec": slim_scene_spec(report.get("scene") or {}),
        "third_tasks_preview": slim_third_tasks(third_rows),
        "skipped_no_device": report.get("skippedNoDevice") or [],
        "missing_mappings": missing,
    }


def op_plan_dispatch(root: Path, *, project_id: str = "nanobot-local") -> dict[str, Any]:
    ensure_runtime(root)
    from paths import resolve_slot  # noqa: WPS433
    from plan_chain import mark_step3_complete  # noqa: WPS433
    from checklist_export import export_device_checklist_xlsx, resolve_project_display_name  # noqa: WPS433

    lld_mod = import_sd_script(root, "3_plan_dispatch", "lld_resolve")
    dispatch_mod = import_sd_script(root, "3_plan_dispatch", "dispatch_plan")
    receive = import_sd_script(root, "1_plan_receive", "receive_tasks")

    lld_primary = lld_mod.resolve_lld_path(root)
    lld = resolve_slot("lld_design", skill_root=root)
    if lld_primary:
        lld = {**lld, "primary": lld_primary, "missing": False, "resolved": [lld_primary]}
    if lld.get("missing"):
        return {"ok": False, "error": "缺少 LLD 设计文件（ProjectData/input/plan_dispatch）"}

    third_path = _plan_dir(root) / "Output" / "third_level_tasks.json"
    if not third_path.is_file():
        return {"ok": False, "error": "缺少 third_level_tasks.json，请先执行 plan_split"}
    raw = json.loads(third_path.read_text(encoding="utf-8"))
    third_tasks = [t for t in (raw.get("tasks") or []) if isinstance(t, dict)]

    second_tasks = receive.load_second_tasks(root)
    scene_dict = _load_scene(root)
    result = dispatch_mod.dispatch_device_base(
        lld_path=str(lld.get("primary")),
        third_tasks=third_tasks,
        second_tasks=second_tasks,
        scene=scene_dict,
        project_id=project_id,
    )
    out_dir = _plan_dir(root) / "Output"
    display_name = resolve_project_display_name(
        scene=scene_dict,
        project_id=project_id,
        project_name=None,
        skill_root=root,
    )
    xlsx_info = export_device_checklist_xlsx(
        device_tasks=result["deviceTasks"],
        scene=scene_dict,
        output_dir=out_dir,
        project_display_name=display_name,
    )
    _save_json(
        out_dir / "device_base_table.json",
        {"schemaVersion": 1, "tasks": result.get("deviceTasks") or []},
        compact=True,
    )
    _save_json(
        out_dir / "dispatch_record.json",
        {
            "schemaVersion": 1,
            "lldPath": result["lldPath"],
            "thirdTaskCount": len(third_tasks),
            "devicePoolSummary": result["devicePoolSummary"],
            "deviceTaskRows": result["stats"]["rows"],
            "dispatchStats": result["stats"],
            "checklistExport": xlsx_info,
            "status": "issued",
        },
    )
    checklist_file = str(xlsx_info.get("filePath") or "").strip()
    if not checklist_file and xlsx_info.get("fileName"):
        checklist_file = str(out_dir / xlsx_info["fileName"])
    mark_step3_complete(
        root,
        lld_path=str(lld.get("primary") or ""),
        device_base_path=out_dir / "device_base_table.json",
        dispatch_record_path=out_dir / "dispatch_record.json",
        checklist_path=checklist_file or None,
    )
    from ._preview_metrics import device_stats, slim_device_tasks, slim_scene_spec

    device_tasks = result.get("deviceTasks") or []
    return {
        "ok": True,
        "device_rows": result["stats"]["rows"],
        "lld_path": result["lldPath"],
        "scene_spec": slim_scene_spec(scene_dict),
        "device_tasks_preview": slim_device_tasks(device_tasks),
        "device_stats": device_stats(device_tasks),
    }


def op_cloudops_init(root: Path, *, project_id: str = "nanobot-local") -> dict[str, Any]:
    mod = import_sd_script(root, "4_cloudops_init", "cloudops_runner")
    scene = _load_scene(root)
    ps = str(scene.get("product_specification") or scene.get("productSpecification") or "").strip()
    cool = str(scene.get("cooling") or "").strip()
    result = mod.run_cloudops_init_for_project(
        skill_dir=str(root),
        product_specification=ps,
        cooling=cool,
    )
    if not result.ok:
        return {"ok": False, "error": result.message, "logs": result.logs}
    rel = f"skills/{root.name}/ProjectData/plan/Output/CloudOps初始配置.xlsx"
    _merge_chain(
        root,
        project_id=project_id,
        step4_cloudops_init_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        step4_cloudops_output_path=rel,
        step4_cloudops_lld_source=result.lld_source,
    )
    return {"ok": True, "output_bytes": result.output_bytes_len, "lld_source": result.lld_source}


def op_cloudops_supplement(root: Path) -> dict[str, Any]:
    mod = import_sd_script(root, "5_cloudops_supplement", "supplement")
    manual = mod.discover_latest_manual_supplement_xlsx(str(root))
    if not manual:
        return {
            "ok": False,
            "error": "缺少 CloudOps 手工补充表（ProjectData/plan/Output 或 input/cloudops）",
        }
    present, src = mod.probe_checklist(skill_dir=str(root))
    _merge_chain(
        root,
        step5_cloudops_supplement_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        step5_cloudops_manual_path=manual,
        step5_checklist_detected=bool(present),
    )
    return {"ok": True, "manual_path": manual, "checklist_present": present, "checklist_source": src}


def op_cloudops_full(root: Path) -> dict[str, Any]:
    mod = import_sd_script(root, "6_cloudops_full", "checklist_to_full")
    chain = _chain(root)
    result = mod.run_full_config_for_project(skill_dir=str(root), chain=chain)
    if not result.ok:
        return {"ok": False, "error": result.message, "logs": result.logs}
    rel = f"skills/{root.name}/ProjectData/plan/Output/CloudOps完整配置文件.xlsx"
    _merge_chain(
        root,
        step6_cloudops_full_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        step6_cloudops_full_path=rel,
    )
    return {
        "ok": True,
        "message": result.message,
        "logs": result.logs,
        "output_bytes": getattr(result, "output_bytes_len", 0),
        "server_rows": getattr(result, "server_rows", 0),
        "switch_rows": getattr(result, "switch_rows", 0),
    }


def op_cloudops_material_check(root: Path) -> dict[str, Any]:
    mod = import_sd_script(root, "6_cloudops_full", "material_check")
    chain = _chain(root)
    scene = _load_scene(root)
    ztp = mod.probe_ztp(skill_dir=str(root), chain=chain)
    params = mod.probe_params(skill_dir=str(root), chain=chain)
    requires_ztp = bool(mod.scene_requires_ztp(scene))

    updates: dict[str, Any] = {
        "step6_materials_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if getattr(ztp, "present", False):
        updates.update(
            step6_ztp_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            step6_ztp_path=f"skills/{root.name}/ProjectData/input/cloudops/{getattr(ztp, 'file_name', '')}",
            step6_ztp_source=getattr(ztp, "source", "") or "deployment_local",
        )
    if getattr(params, "present", False):
        updates.update(
            step6_params_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            step6_params_path=f"skills/{root.name}/ProjectData/input/cloudops/{getattr(params, 'file_name', '')}",
        )
    if (not requires_ztp or getattr(ztp, "present", False)) and getattr(params, "present", False):
        updates["step6_materials_ready_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _merge_chain(root, **updates)

    summary = mod.build_step6_material_markdown(
        full_detail="CloudOps 完整配置已生成。",
        requires_ztp=requires_ztp,
        ztp_present=bool(getattr(ztp, "present", False)),
        ztp_message=str(getattr(ztp, "message", "")),
        params_present=bool(getattr(params, "present", False)),
        params_message=str(getattr(params, "message", "")),
    )
    return {
        "ok": True,
        "requires_ztp": requires_ztp,
        "ztp_present": bool(getattr(ztp, "present", False)),
        "ztp_message": str(getattr(ztp, "message", "")),
        "params_present": bool(getattr(params, "present", False)),
        "params_message": str(getattr(params, "message", "")),
        "summary": summary,
    }


def load_standalone_executor(root: Path) -> dict[str, Any]:
    """大盘旁路读取执行机配置（不触发 LangGraph 步骤）。"""
    ensure_runtime(root)
    from toolkit_executor import load_executor_config  # noqa: WPS433

    cfg = load_executor_config(root)
    ip = str(cfg.get("base_url_ip") or "").strip()
    sk = str(cfg.get("secret_key") or "").strip()
    port = str(cfg.get("base_url_port") or "28880").strip() or "28880"
    return {
        "ok": True,
        "base_url_ip": ip,
        "secret_key": sk,
        "base_url_port": port,
        "configured": bool(ip and sk),
    }


def save_standalone_executor(
    root: Path,
    *,
    base_url_ip: str,
    secret_key: str,
    base_url_port: str = "28880",
) -> dict[str, Any]:
    """大盘旁路写入 toolkit_executor.json（仅落盘 + chain 标记，不改 run 进度）。"""
    ensure_runtime(root)
    from toolkit_executor import save_executor_config  # noqa: WPS433

    ip = str(base_url_ip or "").strip()
    sk = str(secret_key or "").strip()
    if not ip or not sk:
        return {"ok": False, "error": "IP 与 SK 不能为空"}
    port = str(base_url_port or "28880").strip() or "28880"
    cfg = {"base_url_ip": ip, "secret_key": sk, "base_url_port": port}
    save_executor_config(root, cfg)
    _merge_chain(root, step7_executor_config_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return {"ok": True, "base_url_ip": ip, "base_url_port": port}


def op_toolkit_executor(root: Path, config: dict[str, str] | None = None) -> dict[str, Any]:
    ensure_runtime(root)
    from toolkit_executor import load_executor_config, save_executor_config  # noqa: WPS433

    cfg = dict(config or {})
    if not cfg.get("base_url_ip") or not cfg.get("secret_key"):
        existing = load_executor_config(root)
        if existing.get("base_url_ip") and existing.get("secret_key"):
            cfg = existing
    if not cfg.get("base_url_ip") or not cfg.get("secret_key"):
        return {"ok": False, "error": "缺少调测设备配置（base_url_ip / secret_key）"}
    cfg.setdefault("base_url_port", "28880")
    save_executor_config(root, cfg)
    _merge_chain(root, step7_executor_config_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return {"ok": True, "base_url_ip": cfg["base_url_ip"]}


def op_toolkit_import(root: Path) -> dict[str, Any]:
    ensure_gateway_config(root)
    mod = import_sd_script(root, "8_toolkit_import", "toolkit_import")
    result = mod.run_step8_import_and_refresh(skill_dir=str(root))
    if not result.ok:
        return {"ok": False, "error": result.message, "logs": result.logs}
    _merge_chain(root, step8_toolkit_import_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return {
        "ok": True,
        "message": result.message,
        "logs": result.logs,
        "refreshed_rows": getattr(result, "refreshed_rows", 0),
        "refreshed_devices": getattr(result, "refreshed_devices", 0),
    }


def op_commission_command(
    root: Path,
    command: str,
    *,
    scope: str = "all",
    pod_ids: list[int] | None = None,
    devices: list[str] | None = None,
    task_no: str = "",
    only_installed: bool = True,
    mark_init_install_complete: bool = False,
) -> dict[str, Any]:
    if command not in INIT_INSTALL_COMMANDS:
        return {"ok": False, "error": f"不支持的 init_install 命令: {command}"}
    mod = import_sd_script(root, "9_commission/shared/task_runner", "task_runner")
    result = mod.run_command(
        str(root),
        command,
        scope=scope,
        pod_ids=pod_ids,
        devices=devices,
        task_no=task_no,
        only_installed=only_installed,
    )
    if not result.ok:
        return {"ok": False, "error": result.message, "detail": result.detail}
    if mark_init_install_complete:
        _merge_chain(root, step9_init_install_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return {
        "ok": True,
        "message": result.message,
        "task_id": result.task_id,
        "result_dir": result.result_dir,
        "command": command,
        "detail": result.detail,
    }


def op_commission_report(root: Path) -> dict[str, Any]:
    """生成 Raw Skill 的调测报告汇总 xlsx（对齐 driver._report_aggregate）。"""
    mod = import_sd_script(root, "9_commission/shared", "report_aggregate")
    res = mod.build_aggregate(str(root), task_types=list(INIT_INSTALL_COMMANDS))
    if isinstance(res, dict) and res.get("latestPath"):
        return {
            "ok": True,
            "message": "调测报告汇总已生成",
            "report_path": str(res.get("latestPath") or ""),
            "report_name": str(res.get("latestName") or ""),
            "total_commands": res.get("totalCommands"),
            "tested_commands": res.get("testedCommands"),
            "untested_commands": res.get("untestedCommands"),
            "detail_sheets": res.get("detailSheets"),
        }
    return {"ok": False, "error": f"report_aggregate 返回异常：{res!r}"}


def slot_missing(root: Path, slot_id: str) -> list[str]:
    ensure_runtime(root)
    from paths import resolve_slot  # noqa: WPS433

    slot = resolve_slot(slot_id, skill_root=root)
    if slot.get("missing"):
        label = slot.get("label") or slot_id
        return [f"ProjectData/input/…（{label}）"]
    return []
