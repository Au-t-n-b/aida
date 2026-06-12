"""Document export stub."""
from __future__ import annotations

import json
from typing import Any

from agent.proposal.draft_store import (
    load_chapter_02,
    load_chapter_81,
    load_chapter_82,
    load_chapter_83,
    load_chapter_84,
    load_manifest,
    load_version_info,
)
from agent.proposal.services.draft import get_draft


def build_export_payload(project_id: str, version: str = "draft") -> dict[str, Any]:
    if version == "draft":
        draft = get_draft(project_id)
        manifest = draft["manifest"]
        chapters = draft.get("chapters") or {}
    else:
        info = load_version_info(project_id, version)
        manifest = load_manifest(project_id)
        chapters = {
            "2": load_chapter_02(project_id, version),
            "8.1": load_chapter_81(project_id, version),
            "8.2": load_chapter_82(project_id, version),
            "8.3": load_chapter_83(project_id, version),
            "8.4": load_chapter_84(project_id, version),
        }
        manifest = {
            "workingVersionLabel": version,
            "createdBy": info.get("createdBy"),
            "updatedBy": info.get("updatedBy"),
        }

    return {
        "projectId": project_id,
        "proposalVersion": version if version != "draft" else "draft",
        "manifest": manifest,
        "chapters": chapters,
        "format": "json-stub",
        "note": "docx generation pending early.proposal.table_gen",
    }


def export_document_bytes(project_id: str, version: str = "draft") -> tuple[bytes, str]:
    payload = build_export_payload(project_id, version)
    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    label = version if version != "draft" else "draft"
    filename = f"proposal_{label}.json"
    return content, filename
