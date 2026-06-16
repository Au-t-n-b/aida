"""规范侧 release 元数据 · 写 预案版本信息表（不调用 REST release_and_decide）。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from agent.proposal.version_info_store import append_snapshot, sync_xlsx, list_snapshots

_MAIN_VERSION_PATTERN = re.compile(r"^V(?P<major>\d+)\.(?P<minor>\d+)$")


def _now_display() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _parse_main_version(version: str | None) -> tuple[int, int] | None:
    if not version:
        return None
    head = str(version).split("_")[0]
    match = _MAIN_VERSION_PATTERN.match(head)
    if not match:
        return None
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    if major < 1 or minor < 0:
        return None
    if minor > 9:
        return major + 1, 9
    return major, minor


def _next_main_version(latest: str | None) -> str:
    parsed = _parse_main_version(latest)
    if parsed is None:
        return "V1.0"
    major, minor = parsed
    if minor >= 9:
        return f"V{major + 1}.0"
    return f"V{major}.{minor + 1}"


def next_proposal_version(project_id: str) -> str:
    snapshots = list_snapshots(project_id)
    latest = snapshots[-1].get("proposalVersion") if snapshots else None
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{_next_main_version(str(latest) if latest else None)}_{ts}"


def append_release_version(
    project_id: str,
    *,
    operator: str = "LangGraph",
    change_description: str = "proposal_gen table_gen_release",
    project_name: str = "",
) -> dict[str, Any]:
    version = next_proposal_version(project_id)
    now = _now_display()
    row: dict[str, Any] = {
        "projectId": project_id,
        "projectName": project_name or project_id,
        "proposalVersion": version,
        "createdBy": operator,
        "createdAt": now,
        "updatedBy": operator,
        "updatedAt": now,
        "changeDescription": change_description,
        "documentSummary": "",
    }
    append_snapshot(project_id, row)
    sync_xlsx(project_id)
    return row
