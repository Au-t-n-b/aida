"""Chapter JSON + XLSX co-located storage (draft / version folders)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.proposal.chapter_excel import export_chapter_xlsx, export_xlsx_for_json_file
from agent.proposal.chapter_registry import (
    CHAPTER_BY_KEY,
    LEAF_CHAPTERS,
    SKIP_JSON_NAMES,
    ChapterSpec,
)
from agent.proposal.draft_store import (
    draft_dir,
    load_json,
    output_version_dir,
    save_json,
)


def chapter_storage_dir(project_id: str, version: str = "draft") -> Path:
    if version == "draft":
        return draft_dir(project_id)
    return output_version_dir(project_id, version)


def _json_path(project_id: str, spec: ChapterSpec, version: str) -> Path:
    return chapter_storage_dir(project_id, version) / spec.json_file


def _resolve_read_path(project_id: str, spec: ChapterSpec, version: str) -> Path | None:
    base = chapter_storage_dir(project_id, version)
    primary = base / spec.json_file
    if primary.exists():
        return primary
    if spec.legacy_json:
        legacy = base / spec.legacy_json
        if legacy.exists():
            return legacy
    return None


def load_chapter_payload(project_id: str, chapter_key: str, version: str = "draft") -> dict[str, Any]:
    spec = CHAPTER_BY_KEY.get(chapter_key)
    if spec is None:
        return {}
    path = _resolve_read_path(project_id, spec, version)
    if path is None:
        return {}
    return load_json(path, {})


def save_chapter_payload(
    project_id: str,
    chapter_key: str,
    version: str,
    payload: dict[str, Any],
) -> Path:
    """Persist JSON + sibling XLSX for one leaf chapter."""
    spec = CHAPTER_BY_KEY.get(chapter_key)
    if spec is None:
        raise KeyError(f"Unknown chapter key: {chapter_key}")

    enriched = dict(payload)
    enriched.setdefault("chapterKey", spec.key)
    enriched.setdefault("chapterTitle", spec.label)
    if version != "draft":
        enriched["proposalVersion"] = version
        for row in enriched.get("rows") or []:
            if isinstance(row, dict):
                row["proposalVersion"] = version
    else:
        enriched["proposalVersion"] = "草稿"

    json_path = _json_path(project_id, spec, version)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(json_path, enriched)
    export_chapter_xlsx(json_path.with_suffix(".xlsx"), spec, enriched)
    return json_path


def merge_draft_chapters(project_id: str, chapters: dict[str, Any]) -> None:
    for key, payload in chapters.items():
        if key not in CHAPTER_BY_KEY or not isinstance(payload, dict):
            continue
        save_chapter_payload(project_id, key, "draft", payload)


def sync_all_chapter_excel(project_id: str, version: str = "draft") -> list[str]:
    """Normalize registry chapters to canonical JSON + sibling XLSX; export any extra JSON."""
    written: list[str] = []
    for spec in LEAF_CHAPTERS:
        src = _resolve_read_path(project_id, spec, version)
        if src is None:
            continue
        payload = load_json(src, {})
        if not payload:
            continue
        json_path = save_chapter_payload(project_id, spec.key, version, payload)
        written.append(str(json_path.with_suffix(".xlsx")))

    base = chapter_storage_dir(project_id, version)
    if not base.exists():
        return written
    registry_names = {s.json_file for s in LEAF_CHAPTERS}
    registry_legacy = {s.legacy_json for s in LEAF_CHAPTERS if s.legacy_json}
    for json_path in sorted(base.glob("*.json")):
        if json_path.name in SKIP_JSON_NAMES:
            continue
        if json_path.name in registry_names or json_path.name in registry_legacy:
            continue
        out = export_xlsx_for_json_file(json_path)
        if out:
            written.append(str(out))
    return written


def promote_draft_chapters_to_version(project_id: str, new_version: str) -> list[str]:
    """Copy all draft chapter JSON (+ XLSX) into version folder with version stamp."""
    saved: list[str] = []
    for spec in LEAF_CHAPTERS:
        src = _resolve_read_path(project_id, spec, "draft")
        if src is None:
            continue
        payload = load_json(src, {})
        if not payload:
            continue
        dest = save_chapter_payload(project_id, spec.key, new_version, payload)
        saved.append(str(dest))
    # Also pick up any extra *.json in draft (forward compatible)
    draft_base = draft_dir(project_id)
    for json_path in sorted(draft_base.glob("*.json")):
        if json_path.name in SKIP_JSON_NAMES:
            continue
        if json_path.name in {s.json_file for s in LEAF_CHAPTERS}:
            continue
        if any(json_path.name == s.legacy_json for s in LEAF_CHAPTERS if s.legacy_json):
            continue
        payload = load_json(json_path, {})
        if not isinstance(payload, dict) or not payload:
            continue
        payload = dict(payload)
        payload["proposalVersion"] = new_version
        for row in payload.get("rows") or []:
            if isinstance(row, dict):
                row["proposalVersion"] = new_version
        dest_dir = output_version_dir(project_id, new_version)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_json = dest_dir / json_path.name
        save_json(dest_json, payload)
        export_xlsx_for_json_file(dest_json)
        saved.append(str(dest_json))
    return saved
