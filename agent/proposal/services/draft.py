"""Draft save/load orchestration."""
from __future__ import annotations

from typing import Any

from agent.proposal.auth import ProposalSession, proposal_operator_display_name
from agent.proposal.chapter_files import (
    load_chapter_payload,
    merge_draft_chapters,
    sync_output_chapter_excels,
)
from agent.proposal.chapter_registry import LEAF_CHAPTERS
from agent.proposal.draft_store import (
    assert_etag_match,
    load_manifest,
    save_manifest,
)
from agent.proposal.models import PutDraftBody
from agent.proposal.services import metadata as metadata_service


def get_draft(
    project_id: str,
    *,
    operator: str | None = None,
    session: ProposalSession | None = None,
) -> dict[str, Any]:
    def _has_content(payload: dict[str, Any]) -> bool:
        return bool(
            (isinstance(payload.get("rows"), list) and payload.get("rows"))
            or (isinstance(payload.get("fields"), dict) and payload.get("fields"))
            or (isinstance(payload.get("extras"), dict) and payload.get("extras"))
            or payload.get("hardwareSupport")
        )

    op = operator or proposal_operator_display_name(session)
    manifest = load_manifest(project_id)
    chapters: dict[str, Any] = {}
    for spec in LEAF_CHAPTERS:
        if spec.key == "meta":
            continue
        payload = load_chapter_payload(project_id, spec.key, "draft")
        if _has_content(payload):
            chapters[spec.key] = payload

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
    output_written = sync_output_chapter_excels(
        project_id,
        proposal_version=saved.get("workingVersionLabel") or "草稿",
        source_version="draft",
    )

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
        "outputExcelPaths": output_written,
    }
