"""Draft save/load orchestration."""
from __future__ import annotations

from typing import Any

from agent.proposal.auth import ProposalSession, proposal_operator_display_name
from agent.proposal.draft_store import (
    assert_etag_match,
    load_chapter_02,
    load_chapter_81,
    load_chapter_82,
    load_chapter_83,
    load_chapter_84,
    load_manifest,
    save_chapter_02_draft,
    save_chapter_81_draft,
    save_chapter_82_draft,
    save_chapter_83_draft,
    save_chapter_84_draft,
    save_manifest,
)
from agent.proposal.models import PutDraftBody
from agent.proposal.services import metadata as metadata_service
from agent.proposal.chapter_files import merge_draft_chapters, sync_all_chapter_excel


def get_draft(
    project_id: str,
    *,
    operator: str | None = None,
    session: ProposalSession | None = None,
) -> dict[str, Any]:
    op = operator or proposal_operator_display_name(session)
    manifest = load_manifest(project_id)
    chapters: dict[str, Any] = {}
    ch02 = load_chapter_02(project_id, "draft")
    if ch02.get("rows"):
        chapters["2"] = ch02
    ch81 = load_chapter_81(project_id, "draft")
    if ch81.get("rows"):
        chapters["8.1"] = ch81
    ch82 = load_chapter_82(project_id, "draft")
    if ch82.get("rows"):
        chapters["8.2"] = ch82
    ch83 = load_chapter_83(project_id, "draft")
    if ch83.get("rows"):
        chapters["8.3"] = ch83
    ch84 = load_chapter_84(project_id, "draft")
    if ch84.get("rows") or ch84.get("hardwareSupport"):
        chapters["8.4"] = ch84

    meta_row, meta_deps = metadata_service.ensure_metadata_draft(project_id, op)
    return {
        "manifest": {
            "projectId": manifest.get("projectId"),
            "baseProposalVersion": manifest.get("baseProposalVersion"),
            "workingVersionLabel": "草稿",
            "status": manifest.get("status", "draft"),
            "dirty": manifest.get("dirty", False),
            "changeRecords": manifest.get("changeRecords") or [],
            "publishedVersions": manifest.get("publishedVersions") or [],
            "etag": manifest.get("etag"),
        },
        "metadata": meta_row,
        "metadataDependencies": meta_deps,
        "cumulativeChangeLog": metadata_service.build_cumulative_change_log(project_id),
        "chapters": chapters,
    }


def save_draft(
    project_id: str,
    body: PutDraftBody,
    session: ProposalSession,
    *,
    if_match: str | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    assert_etag_match(manifest, if_match)

    working_label = "草稿"

    if body.chapters and "2" in body.chapters:
        save_chapter_02_draft(project_id, body.chapters["2"])
    if body.chapters and "8.1" in body.chapters:
        save_chapter_81_draft(project_id, body.chapters["8.1"])
    if body.chapters and "8.2" in body.chapters:
        save_chapter_82_draft(project_id, body.chapters["8.2"])
    if body.chapters and "8.3" in body.chapters:
        save_chapter_83_draft(project_id, body.chapters["8.3"])
    if body.chapters and "8.4" in body.chapters:
        save_chapter_84_draft(project_id, body.chapters["8.4"])

    if body.chapters:
        merge_draft_chapters(project_id, body.chapters)

    operator = proposal_operator_display_name(session)

    if body.manual_change_log is not None:
        metadata_service.save_manual_change_log(
            project_id,
            [e.model_dump(by_alias=True) for e in body.manual_change_log],
            operator,
        )
        manifest = load_manifest(project_id)
    elif body.change_records is not None:
        manifest["changeRecords"] = [r.model_dump() for r in body.change_records]
        metadata_service.save_manual_change_log(
            project_id,
            [
                {"chapter": r.chapter, "changeDescription": r.description}
                for r in body.change_records
            ],
            operator,
        )
        manifest = load_manifest(project_id)

    manifest["dirty"] = False
    manifest["workingVersionLabel"] = working_label
    manifest["status"] = "draft"
    saved = save_manifest(project_id, manifest)

    meta_row = metadata_service.touch_metadata_on_save(project_id, operator)

    sync_all_chapter_excel(project_id, "draft")

    return {
        "status": "draft",
        "baseProposalVersion": saved.get("baseProposalVersion"),
        "workingVersionLabel": saved.get("workingVersionLabel"),
        "updatedBy": meta_row.get("updatedBy"),
        "updatedAt": meta_row.get("updatedAt"),
        "dirty": False,
        "etag": saved.get("etag"),
        "metadata": meta_row,
        "cumulativeChangeLog": metadata_service.build_cumulative_change_log(project_id),
    }
