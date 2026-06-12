from __future__ import annotations

import json
from typing import Any


def sd_runtime_action(
    *,
    label: str,
    action: str,
    skill_name: str = "software_deployment",
    request_id: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """GuidanceCard / 会话按钮：平台只认 ``verb`` + ``payload``。"""
    rid = request_id or f"req-sd-{action.replace('_', '-')}"
    payload: dict[str, Any] = {
        "type": "skill_runtime_start",
        "skillName": skill_name,
        "requestId": rid,
        "action": action,
    }
    if thread_id:
        payload["threadId"] = thread_id
    return {"label": label, "verb": "skill_runtime_start", "payload": payload}


def sd_download_action(
    *,
    label: str,
    path: str,
    filename: str | None = None,
) -> dict[str, Any]:
    """GuidanceCard 下载按钮：前端 ``skill_web_download`` 直调 ``/api/download``。"""
    payload: dict[str, Any] = {"path": path}
    if filename:
        payload["filename"] = filename
    return {"label": label, "verb": "skill_web_download", "payload": payload}


def sd_guidance_payload(
    *,
    card_id: str,
    step: int,
    body: str,
    action: str,
    action_label: str,
    prev_done_step: int | None = None,
    prev_detail: str = "",
    intro: str | None = None,
    skill_name: str = "software_deployment",
) -> dict[str, Any]:
    """单卡闸门：只用 GuidanceCard（避免 confirm + guidance 双卡）。"""
    from step_ui import step_gate_banner

    payload: dict[str, Any] = {
        "context": step_gate_banner(step, body=body, prev_done_step=prev_done_step, prev_detail=prev_detail),
        "cardId": card_id,
        "variant": "rows",
        "actions": [
            sd_runtime_action(label=action_label, action=action, skill_name=skill_name),
        ],
    }
    if intro:
        payload["intro"] = intro
    return payload


def sd_done_payload(
    *,
    card_id: str,
    step: int,
    detail: str,
    next_step: int | None = None,
    next_action: str | None = None,
    next_label: str | None = None,
    skill_name: str = "software_deployment",
) -> dict[str, Any]:
    from step_ui import STEP_TITLES, TOTAL_STEPS, step_all_done_banner, step_done_banner

    if step >= TOTAL_STEPS:
        context = step_all_done_banner() + ("\n\n" + detail.strip() if detail.strip() else "")
        actions: list[dict[str, Any]] = []
    else:
        context = step_done_banner(step, detail=detail)
        if next_step and next_action and next_label:
            context += (
                f"\n\n▶️ **下一步 · 步骤 {next_step}/{TOTAL_STEPS}："
                f"{STEP_TITLES.get(next_step, next_label)}** — 请点下方继续。"
            )
            actions = [sd_runtime_action(label=next_label, action=next_action, skill_name=skill_name)]
        else:
            actions = []
    return {"context": context, "cardId": card_id, "actions": actions}


def sync_skill_dashboard(
    *,
    skill_root: Any,
    thread_id: str,
    skill_name: str = "software_deployment",
    run_id: str,
    timestamp_ms: int,
) -> None:
    """刷新右侧大盘：六步 Stepper + 分步 Tab 产物（可 openPreview）。"""
    from pathlib import Path

    from dashboard_sync import emit_dashboard_patch_event

    root = Path(skill_root).resolve() if skill_root else Path.cwd().resolve()
    emit_dashboard_patch_event(
        thread_id=thread_id,
        skill_name=skill_name,
        skill_run_id=run_id,
        skill_root=root,
        timestamp_ms=timestamp_ms,
    )


def sd_dashboard_intent_text(
    action: str,
    *,
    skill_name: str = "software_deployment",
    request_id: str | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> str:
    """大盘 Button ``post_user_message`` 内嵌的 chat_card_intent JSON 字符串。"""
    rid = request_id or f"req-sd-{action.replace('_', '-')}"
    payload: dict[str, Any] = {
        "type": "skill_runtime_start",
        "skillName": skill_name,
        "requestId": rid,
        "action": action,
    }
    if isinstance(extra_payload, dict):
        payload.update(extra_payload)
    return json.dumps(
        {
            "type": "chat_card_intent",
            "verb": "skill_runtime_start",
            "payload": payload,
        },
        ensure_ascii=False,
    )
