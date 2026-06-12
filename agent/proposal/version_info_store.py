"""Unified storage for 预案版本信息表 (draft row + version snapshots)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from agent.proposal.draft_store import physical_project_root, save_json, load_json, _ensure_parent
from agent.constants.project_paths import proposal_paths

RECORDS_FILE = "records.json"
XLSX_FILE = "预案版本信息表.xlsx"
DRAFT_VERSION_LABEL = "草稿"

XLSX_HEADERS = [
    "项目ID",
    "项目名称",
    "预案版本号",
    "创建人",
    "创建时间",
    "最后修改人",
    "修改时间",
    "本次修改描述",
    "文档摘要",
]


def _paths(project_id: str) -> dict[str, str]:
    return proposal_paths(project_id)


def version_info_dir(project_id: str) -> Path:
    return physical_project_root(project_id) / Path(_paths(project_id)["version_info_out"])


def records_path(project_id: str) -> Path:
    return version_info_dir(project_id) / RECORDS_FILE


def xlsx_path(project_id: str) -> Path:
    return version_info_dir(project_id) / XLSX_FILE


def _empty_store() -> dict[str, Any]:
    return {"draft": None, "snapshots": []}


def load_store(project_id: str) -> dict[str, Any]:
    store = load_json(records_path(project_id), _empty_store())
    store.setdefault("draft", None)
    store.setdefault("snapshots", [])
    return store


def save_store(project_id: str, store: dict[str, Any]) -> None:
    save_json(records_path(project_id), store)


def load_draft_row(project_id: str) -> dict[str, Any] | None:
    store = load_store(project_id)
    draft = store.get("draft")
    return dict(draft) if draft else None


def save_draft_row(project_id: str, row: dict[str, Any]) -> dict[str, Any]:
    store = load_store(project_id)
    store["draft"] = row
    save_store(project_id, store)
    return row


def append_snapshot(project_id: str, row: dict[str, Any]) -> dict[str, Any]:
    store = load_store(project_id)
    snapshots: list[dict[str, Any]] = list(store.get("snapshots") or [])
    snapshots.append(row)
    store["snapshots"] = snapshots
    save_store(project_id, store)
    return row


def list_snapshots(project_id: str) -> list[dict[str, Any]]:
    store = load_store(project_id)
    return list(store.get("snapshots") or [])


def find_snapshot(project_id: str, proposal_version: str) -> dict[str, Any] | None:
    for row in list_snapshots(project_id):
        if row.get("proposalVersion") == proposal_version:
            return dict(row)
    return None


def _row_to_xlsx_values(row: dict[str, Any]) -> list[Any]:
    return [
        row.get("projectId", ""),
        row.get("projectName", ""),
        row.get("proposalVersion", ""),
        row.get("createdBy") or "",
        row.get("createdAt") or "",
        row.get("updatedBy") or "",
        row.get("updatedAt") or "",
        row.get("changeDescription") or "",
        row.get("documentSummary") or "",
    ]


def sync_xlsx(project_id: str) -> Path:
    """Rewrite xlsx from records.json (draft first, then snapshots in order)."""
    store = load_store(project_id)
    path = xlsx_path(project_id)
    _ensure_parent(path)

    wb = Workbook()
    ws = wb.active
    ws.title = "预案版本信息表"
    ws.append(XLSX_HEADERS)

    draft = store.get("draft")
    if draft:
        ws.append(_row_to_xlsx_values(draft))

    for snap in store.get("snapshots") or []:
        ws.append(_row_to_xlsx_values(snap))

    wb.save(path)
    return path


def import_legacy_version_info(project_id: str) -> None:
    """One-time import from per-version version-info.json if store has no snapshots."""
    from agent.proposal.draft_store import list_published_versions, load_version_info

    store = load_store(project_id)
    if store.get("snapshots"):
        return

    snapshots: list[dict[str, Any]] = []
    for ver in reversed(list_published_versions(project_id)):
        info = load_version_info(project_id, ver)
        if not info.get("proposalVersion"):
            info["proposalVersion"] = ver
        snapshots.append(info)

    if snapshots:
        store["snapshots"] = snapshots
        save_store(project_id, store)
