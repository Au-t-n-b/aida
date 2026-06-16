"""zhgk HITL 续跑路由表 · full_restart 时决定 route_to。"""
from __future__ import annotations

from typing import Any


def resolve_resume_route_to(
    *,
    hitl_step: str,
    project: dict[str, Any],
    payload: dict[str, Any],
    prev_state: dict[str, Any],
) -> str | None:
    """根据 HITL 步骤与用户选择，决定 full_restart 应从哪个 step 续跑。"""
    _ = prev_state  # 预留：后续可按 prev steps 推断
    choice = str((payload or {}).get("choice") or "").strip()
    intent = str((project or {}).get("intent") or "").strip()

    if hitl_step == "intent_select" and choice:
        # 意图已写入 project；跳过 intent_select，进入代际识别
        return "determine_gen"

    if hitl_step == "determine_gen" and choice:
        return "determine_gen"

    if hitl_step == "data_append" and (choice or (payload or {}).get("uploaded")):
        return "data_append"

    if hitl_step == "confirm_table":
        if choice == "redo":
            return "filter_build"
        if choice == "confirm":
            return "task_dispatch"

    if hitl_step == "task_dispatch":
        if choice in {"dispatch", "skip"} or (payload or {}).get("assignees"):
            return "task_dispatch"

    if hitl_step == "wait_survey":
        uploaded = (payload or {}).get("uploaded")
        if uploaded or choice:
            return "assess"

    if hitl_step == "filter_build":
        uploaded = (payload or {}).get("uploaded")
        if uploaded:
            return "filter_build"

    if hitl_step == "supplement_run" and choice:
        return "assess"

    if hitl_step == "report_gen_run" and choice:
        return "report_gen_run"

    if hitl_step == "report_distribute" and choice:
        return "report_distribute"

    if hitl_step == "resurvey_gate":
        if choice == "resurvey":
            return "resurvey_gate"
        if choice == "dispatch":
            return "task_dispatch"
        if choice == "skip":
            return "wait_survey"

    # scene_suggest 等无 HITL 续跑 payload 时，按 intent 推断下一合法 step
    if not hitl_step and intent == "scene_suggest":
        return None

    return None
