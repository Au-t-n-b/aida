"""Shared check/run helpers for init_install commission BaseSteps."""
from __future__ import annotations

from ...base import SkillContext, SkillState, StepResult, Emit, CheckResult
from ..bridge import get_sd_root
from ._sd_ops import _chain, op_commission_command
from ._hitl import confirm_gate, is_scope_ready_for, apply_parsed_to_project


def commission_check(
    ctx: SkillContext,
    step_key: str,
    label: str,
    description: str,
) -> CheckResult:
    chain = _chain(ctx.work_root)
    if not chain.get("step8_toolkit_import_at"):
        return {
            "ok": False,
            "missing": ["Toolkit 导入完成标记（需先 toolkit_import）"],
            "found": [],
            "note": "",
        }
    if is_scope_ready_for(ctx.project, step_key):
        return {"ok": True, "missing": [], "found": [], "note": ""}
    return confirm_gate(ctx.project, step_key, label, note=f"{label} 需要确认", description=description)


def commission_run(
    ctx: SkillContext,
    emit: Emit,
    step_key: str,
    command: str,
    *,
    mark_init_install_complete: bool = False,
) -> StepResult:
    emit(f"[{step_key}] 执行 {command}…")
    proj = apply_parsed_to_project(dict(ctx.project or {}))
    scope = str(proj.get("scope") or "all")
    pod_ids = proj.get("pod_ids")
    devices = proj.get("devices")
    task_no = str(proj.get("task_no") or "")
    only_installed = proj.get("only_installed", True)
    if isinstance(pod_ids, list):
        pod_ids = [int(p) for p in pod_ids if str(p).strip() != ""]
    else:
        pod_ids = None
    if isinstance(devices, list):
        devices = [str(d).strip() for d in devices if str(d).strip()]
    else:
        devices = None
    # 每次执行用最新解析的工作区根（兼容 nanobot workspace 与 SOFTWARE_DEPLOYMENT_ROOT）
    result = op_commission_command(
        get_sd_root(),
        command,
        scope=scope,
        pod_ids=pod_ids,
        devices=devices,
        task_no=task_no,
        only_installed=bool(only_installed),
        mark_init_install_complete=mark_init_install_complete,
    )
    if not result.get("ok"):
        detail = result.get("detail")
        err = result.get("error") or f"{command} 执行失败"
        if isinstance(detail, dict) and detail.get("message"):
            emit(f"  {detail.get('message')}")
        emit(f"  失败：{err}")
        from ._preview_metrics import build_commission_failure_record

        from ..sdui import SD_STEP_ORDER

        try:
            pct = int(100 * (SD_STEP_ORDER.index(step_key) + 1) / len(SD_STEP_ORDER))
        except ValueError:
            pct = 0
        return {
            "error": err,
            "current_step": step_key,
            "overall_progress": pct,
            "metrics": {
                f"{command}_ok": False,
                "command": command,
                "commission_record": build_commission_failure_record(step_key, err),
            },
        }
    emit(f"[{step_key}] {result.get('message', '完成')}")
    if result.get("result_dir"):
        emit(f"  报告目录：{result.get('result_dir')}")
    from ._preview_metrics import build_commission_record

    from ..sdui import SD_STEP_ORDER

    try:
        pct = int(100 * (SD_STEP_ORDER.index(step_key) + 1) / len(SD_STEP_ORDER))
    except ValueError:
        pct = 0

    rd = str(result.get("result_dir") or "").strip().replace("\\", "/")
    if rd and "ProjectData/" in rd:
        rd = rd[rd.index("ProjectData/") :]
    return {
        "current_step": step_key,
        "overall_progress": pct,
        "artifacts": [rd] if rd else [],
        "metrics": {
            f"{command}_ok": True,
            "command": command,
            "task_id": result.get("task_id", ""),
            "result_dir": result.get("result_dir", ""),
            "commission_record": build_commission_record(step_key, result),
        },
    }
