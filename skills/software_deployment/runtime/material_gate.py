# -*- coding: utf-8 -*-
"""材料闸门：目录已有文件时提示「已就绪」，用户可选沿用或重新上传。"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from guidance_actions import sd_runtime_action


def file_line(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        return ""
    try:
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))
    except OSError:
        mtime = "?"
    return f"`{p.name}`（{mtime}）"


def slot_bullet(slot: dict[str, Any], *, prefix: str = "") -> str:
    label = str(slot.get("label") or slot.get("slotId") or "材料")
    if slot.get("missing"):
        if slot.get("optional"):
            return f"- {prefix}{label}：（可选，暂无）"
        return f"- {prefix}{label}：（待上传）"
    primary = str(slot.get("primary") or "").strip()
    if primary:
        return f"- {prefix}{label}：{file_line(primary)}"
    resolved = slot.get("resolved") or []
    if resolved:
        return f"- {prefix}{label}：{file_line(str(resolved[0]))}"
    return f"- {prefix}{label}：（已就绪）"


def required_missing(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in slots if isinstance(s, dict) and s.get("missing") and not s.get("optional")]


def any_present(slots: list[dict[str, Any]]) -> bool:
    return any(isinstance(s, dict) and not s.get("missing") for s in slots)


def material_footer(*, has_required: bool) -> str:
    if has_required:
        return "请确认**沿用目录内材料并继续**，或点 **重新上传** 更换文件。"
    return "必填材料尚未齐；可放入对应 input 目录后点 **继续**，或 **重新上传**。"


def choice_actions(
    *,
    use_action: str,
    use_label: str,
    reupload_action: str | None = None,
    reupload_label: str = "重新上传材料",
    skill_name: str = "software_deployment",
) -> list[dict[str, Any]]:
    actions = [sd_runtime_action(label=use_label, action=use_action, skill_name=skill_name)]
    if reupload_action:
        actions.append(
            sd_runtime_action(label=reupload_label, action=reupload_action, skill_name=skill_name)
        )
    return actions


def append_reupload_action(
    payload: dict[str, Any],
    *,
    reupload_action: str,
    reupload_label: str = "重新上传材料",
    skill_name: str = "software_deployment",
) -> dict[str, Any]:
    actions = list(payload.get("actions") or [])
    actions.append(
        sd_runtime_action(label=reupload_label, action=reupload_action, skill_name=skill_name)
    )
    payload["actions"] = actions
    payload["variant"] = "rows"
    return payload
