"""Version history and read-only snapshots."""
from __future__ import annotations

from typing import Any

from agent.proposal.auth import proposal_operator_display_name
from agent.proposal.draft_store import (
    format_display_datetime,
    load_chapter_02,
    load_chapter_81,
    load_chapter_82,
    load_chapter_83,
    load_chapter_84,
    load_manifest,
    load_version_info,
    list_published_versions,
)
from agent.proposal.services import metadata as metadata_service
from agent.proposal.version_info_store import find_snapshot


def _format_dt(iso: str | None) -> str | None:
    return format_display_datetime(iso)


def _tone_for_version(version: str) -> str:
    if "_DTRB" in version:
        return "green"
    if "_DRB" in version:
        return "amber"
    return "green"


def list_versions(project_id: str) -> list[dict[str, Any]]:
    manifest = load_manifest(project_id)
    published = list_published_versions(project_id)
    latest = manifest.get("latestReleaseVersion") or (published[0] if published else None)
    versions: list[dict[str, Any]] = []

    for idx, ver in enumerate(published):
        snap = find_snapshot(project_id, ver)
        info = snap if snap else load_version_info(project_id, ver)
        versions.append(
            {
                "proposalVersion": ver,
                "status": "published",
                "label": ver,
                "tone": _tone_for_version(ver),
                "createdBy": info.get("createdBy") or proposal_operator_display_name(),
                "createdAt": _format_dt(info.get("createdAt")),
                "updatedBy": info.get("updatedBy") or proposal_operator_display_name(),
                "updatedAt": _format_dt(info.get("updatedAt")),
                "isLatest": ver == latest,
                "isEditable": False,
            }
        )

    meta_row, _ = metadata_service.ensure_metadata_draft(
        project_id, proposal_operator_display_name()
    )
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
    ch02 = load_chapter_02(project_id, proposal_version)
    if ch02.get("rows"):
        chapters["2"] = ch02
    ch81 = load_chapter_81(project_id, proposal_version)
    if ch81.get("rows"):
        chapters["8.1"] = ch81
    ch82 = load_chapter_82(project_id, proposal_version)
    if ch82.get("rows"):
        chapters["8.2"] = ch82
    ch83 = load_chapter_83(project_id, proposal_version)
    if ch83.get("rows"):
        chapters["8.3"] = ch83
    ch84 = load_chapter_84(project_id, proposal_version)
    if ch84.get("rows") or ch84.get("hardwareSupport"):
        chapters["8.4"] = ch84

    return {
        "proposalVersion": proposal_version,
        "status": "published",
        "metadata": meta_row,
        "chapters": chapters,
        "isEditable": False,
    }
