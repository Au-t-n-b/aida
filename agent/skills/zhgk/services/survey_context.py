"""勘测任务上下文：项目名 / 机房名 / 任务名（单一真相）。"""
from __future__ import annotations

from typing import Any


def resolve_survey_context(
    project: dict[str, Any] | None,
    info: dict[str, Any] | None = None,
) -> dict[str, str]:
    """合并 project 与 project_info.json，解析当前工勘上下文。

    project（state）优先；info 兜底。兼容旧版中文键名。
    """
    proj = project or {}
    inf = info or {}

    def _pick(en: str, zh: str = "") -> str:
        for src in (proj, inf):
            v = str(src.get(en) or "").strip()
            if v:
                return v
        if zh:
            v = str(inf.get(zh) or "").strip()
            if v:
                return v
        return ""

    project_name = _pick("project_name", "项目名称") or "未知项目"
    room_name = _pick("room_name", "机房名称")
    activity_id = _pick("activity_id", "工勘活动ID")
    project_code = _pick("project_code")

    return {
        "project_name": project_name,
        "room_name": room_name,
        "activity_id": activity_id,
        "project_code": project_code,
    }


def format_survey_task_name(
    *,
    project_name: str = "",
    room_name: str = "",
    survey_round: int = 1,
) -> str:
    """下发任务包 / GKCLAW task.json 共用的任务名。"""
    pn = str(project_name or "").strip()
    rn = str(room_name or "").strip()
    round_suffix = f"（第{survey_round}轮）" if survey_round > 1 else ""
    label = "·".join(p for p in (pn, rn) if p)
    if label:
        return f"{label} 现场勘测{round_suffix}"
    return f"现场勘测{round_suffix}" if round_suffix else "勘测任务"
