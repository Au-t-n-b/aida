"""Version history and read-only snapshots."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agent.proposal.chapter_files import load_chapter_payload
from agent.proposal.chapter_registry import LEAF_CHAPTERS
from agent.proposal.draft_store import (
    format_display_datetime,
    load_manifest,
    load_version_info,
    list_published_versions,
)
from agent.proposal.services import metadata as metadata_service
from agent.proposal.version_info_store import find_snapshot


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    # region agent log
    try:
        payload = {
            "sessionId": "f94a50",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        Path("debug-f94a50.log").open("a", encoding="utf-8").write(
            json.dumps(payload, ensure_ascii=False) + "\n"
        )
    except Exception:
        pass
    # endregion


def _format_dt(iso: str | None) -> str | None:
    return format_display_datetime(iso)


def _tone_for_version(version: str) -> str:
    if "_DTRB" in version:
        return "green"
    if "_DRB" in version:
        return "amber"
    return "green"


def list_versions(project_id: str, *, operator: str | None = None) -> list[dict[str, Any]]:
    manifest = load_manifest(project_id)
    published = list_published_versions(project_id)
    latest = manifest.get("latestReleaseVersion") or (published[0] if published else None)
    versions: list[dict[str, Any]] = []
    fallback_operator = operator or manifest.get("updatedBy") or manifest.get("createdBy") or "system"

    for idx, ver in enumerate(published):
        snap = find_snapshot(project_id, ver)
        info = snap if snap else load_version_info(project_id, ver)
        versions.append(
            {
                "proposalVersion": ver,
                "status": "published",
                "label": ver,
                "tone": _tone_for_version(ver),
                "createdBy": info.get("createdBy") or fallback_operator,
                "createdAt": _format_dt(info.get("createdAt")),
                "updatedBy": info.get("updatedBy") or fallback_operator,
                "updatedAt": _format_dt(info.get("updatedAt")),
                "isLatest": ver == latest,
                "isEditable": False,
            }
        )

    meta_row, _ = metadata_service.ensure_metadata_draft(project_id, fallback_operator)
    # region agent log
    _debug_log(
        "H14",
        "agent/proposal/services/versions.py:list_versions",
        "draft row used in versions response",
        {
            "projectId": project_id,
            "fallbackOperator": fallback_operator,
            "metaUpdatedBy": meta_row.get("updatedBy"),
            "metaCreatedBy": meta_row.get("createdBy"),
            "metaProposalVersion": meta_row.get("proposalVersion"),
        },
    )
    # endregion
    versions.insert(
        0,
        {
            "proposalVersion": "draft",
            "status": "draft",
            "label": "草稿",
            "tone": "amber",
            "baseProposalVersion": manifest.get("baseProposalVersion"),
            "createdBy": meta_row.get("createdBy"),
            "createdAt": meta_row.get("createdAt"),
            "updatedBy": meta_row.get("updatedBy"),
            "updatedAt": meta_row.get("updatedAt"),
            "isLatest": True,
            "isEditable": True,
            "dirty": manifest.get("dirty", False),
        },
    )
    return versions


def get_version_snapshot(project_id: str, proposal_version: str) -> dict[str, Any]:
    if proposal_version == "draft":
        from agent.proposal.services.draft import get_draft

        return get_draft(project_id)

    meta_row, _ = metadata_service.get_metadata(project_id, proposal_version)
    chapters: dict[str, Any] = {}
    for spec in LEAF_CHAPTERS:
        if spec.key == "meta":
            continue
        payload = load_chapter_payload(project_id, spec.key, proposal_version)
        if (
            (isinstance(payload.get("rows"), list) and payload.get("rows"))
            or (isinstance(payload.get("fields"), dict) and payload.get("fields"))
            or (isinstance(payload.get("extras"), dict) and payload.get("extras"))
            or payload.get("hardwareSupport")
        ):
            chapters[spec.key] = payload

    return {
        "proposalVersion": proposal_version,
        "status": "published",
        "metadata": meta_row,
        "chapters": chapters,
        "isEditable": False,
    }
