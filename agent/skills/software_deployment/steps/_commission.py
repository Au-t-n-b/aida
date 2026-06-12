"""Shared check/run helpers for init_install commission BaseSteps."""
from __future__ import annotations

from ...base import SkillContext, SkillState, StepResult, Emit, CheckResult
from ._sd_ops import _chain, op_commission_command
from ._hitl import confirm_gate


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
    scope = str((ctx.project or {}).get("scope") or "all")
    result = op_commission_command(
        ctx.work_root,
        command,
        scope=scope,
        mark_init_install_complete=mark_init_install_complete,
    )
    if not result.get("ok"):
        detail = result.get("detail")
        if isinstance(detail, dict) and detail.get("message"):
            emit(f"  {detail.get('message')}")
        return {"error": result.get("error") or f"{command} 执行失败"}
    emit(f"[{step_key}] {result.get('message', '完成')}")
    if result.get("result_dir"):
        emit(f"  报告目录：{result.get('result_dir')}")
    from ._preview_metrics import build_commission_record

    from ..sdui import SD_STEP_ORDER

    try:
        pct = int(100 * (SD_STEP_ORDER.index(step_key) + 1) / len(SD_STEP_ORDER))
    except ValueError:
        pct = 0

    return {
        "current_step": step_key,
        "overall_progress": pct,
        "metrics": {
            f"{command}_ok": True,
            "command": command,
            "task_id": result.get("task_id", ""),
            "result_dir": result.get("result_dir", ""),
            "commission_record": build_commission_record(step_key, result),
        },
    }
