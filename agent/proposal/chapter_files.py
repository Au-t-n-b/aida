"""Chapter JSON + XLSX co-located storage (draft / version folders)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.proposal.chapter_excel import (
    chapter_template_keys,
    export_chapter_xlsx,
    export_xlsx_for_json_file,
    read_header_keys_from_xlsx,
    read_rows_from_xlsx,
)
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
    proposal_output_dir,
    save_json,
)


def chapter_storage_dir(project_id: str, version: str = "draft") -> Path:
    if version == "draft":
        return draft_dir(project_id)
    return output_version_dir(project_id, version)


def chapter_output_xlsx_dir(project_id: str) -> Path:
    return proposal_output_dir(project_id)


OUTPUT_XLSX_NAME_BY_KEY: dict[str, str] = {
    "meta": "元数据信息.xlsx",
    "1": "项目背景信息表.xlsx",
    "2": "设备信息表.xlsx",
    "3": "智算部件配置信息表.xlsx",
    "4": "软件配置信息表.xlsx",
    "5.1": "网络平面配置信息表.xlsx",
    "5.2": "网管服务器配置表.xlsx",
    "5.3": "集群设备清单表.xlsx",
    "6": "预集成预验证需求信息表.xlsx",
    "7": "机房机柜信息表.xlsx",
    "8.1": "服务交付界面表.xlsx",
    "8.2": "服务内容表.xlsx",
    "8.3": "维保策略表.xlsx",
    "8.4": "维保SLA表.xlsx",
    "9": "项目责任矩阵.xlsx",
    "10": "计划表.xlsx",
    "11": "验收策略.xlsx",
    "12": "测试用例.xlsx",
}


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


def _chapter_output_xlsx_path(project_id: str, spec: ChapterSpec) -> Path:
    file_name = OUTPUT_XLSX_NAME_BY_KEY.get(spec.key, spec.json_file.replace(".json", ".xlsx"))
    return chapter_output_xlsx_dir(project_id) / file_name


def _normalize_output_excel_names(project_id: str) -> None:
    out_dir = chapter_output_xlsx_dir(project_id)
    if not out_dir.exists():
        return
    for spec in LEAF_CHAPTERS:
        old_name = spec.json_file.replace(".json", ".xlsx")
        new_name = OUTPUT_XLSX_NAME_BY_KEY.get(spec.key, old_name)
        if old_name == new_name:
            continue
        old_path = out_dir / old_name
        new_path = out_dir / new_name
        if old_path.exists() and not new_path.exists():
            old_path.rename(new_path)


def _merge_versioned_rows(
    existing_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    proposal_version: str,
    *,
    allowed_keys: list[str] | None = None,
) -> list[dict[str, Any]]:
    kept_keys = [k for k in (allowed_keys or []) if k and k != "proposalVersion"]

    def _shape_row(src: dict[str, Any], version: str) -> dict[str, Any]:
        row: dict[str, Any] = {}
        if kept_keys:
            for k in kept_keys:
                row[k] = src.get(k, "")
        else:
            for k, v in src.items():
                if k != "proposalVersion":
                    row[k] = v
        row["proposalVersion"] = version
        return row

    def _normalized(v: Any) -> str:
        return str(v or "").strip()

    if proposal_version == "草稿":
        draft_rows = [_shape_row(r, "草稿") for r in current_rows if isinstance(r, dict)]
        history = [
            _shape_row(r, _normalized(r.get("proposalVersion")))
            for r in existing_rows
            if _normalized(r.get("proposalVersion")) not in ("", "草稿")
        ]
        return draft_rows + history

    draft_rows = [
        _shape_row(r, "草稿")
        for r in existing_rows
        if _normalized(r.get("proposalVersion")) == "草稿"
    ]
    if not draft_rows:
        draft_rows = [_shape_row(r, "草稿") for r in current_rows if isinstance(r, dict)]

    history = [
        _shape_row(r, _normalized(r.get("proposalVersion")))
        for r in existing_rows
        if _normalized(r.get("proposalVersion")) not in ("", "草稿", proposal_version)
    ]
    current_version_rows = [
        _shape_row(r, proposal_version) for r in current_rows if isinstance(r, dict)
    ]
    return draft_rows + history + current_version_rows


def sync_output_chapter_excels(
    project_id: str,
    *,
    proposal_version: str,
    source_version: str = "draft",
) -> list[str]:
    """Sync chapter excels in 输出结果 root without creating version folders.

    Rules:
    - If 输出结果 has no chapter xlsx, initialize all chapter xlsx.
    - If not empty, only update already existing chapter xlsx files.
    """
    out_dir = chapter_output_xlsx_dir(project_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    _normalize_output_excel_names(project_id)

    targets: list[ChapterSpec] = list(LEAF_CHAPTERS)

    written: list[str] = []
    for spec in targets:
        payload = load_chapter_payload(project_id, spec.key, source_version)
        enriched = dict(payload or {})
        enriched.setdefault("chapterKey", spec.key)
        enriched.setdefault("chapterTitle", spec.label)
        enriched["proposalVersion"] = proposal_version
        xlsx_path = _chapter_output_xlsx_path(project_id, spec)
        template_keys = chapter_template_keys(spec.key)
        locked_keys = template_keys or read_header_keys_from_xlsx(xlsx_path)
        has_structured_payload = bool(
            isinstance(enriched.get("rows"), list)
            or (isinstance(enriched.get("fields"), dict) and enriched.get("fields"))
            or (isinstance(enriched.get("extras"), dict) and enriched.get("extras"))
        )

        # Do not wipe existing chapter excel when this round has no backend payload.
        # This protects chapters currently rendered by frontend-local/legacy data sources.
        if not has_structured_payload and xlsx_path.exists():
            written.append(str(xlsx_path))
            continue

        rows = enriched.get("rows")
        if isinstance(rows, list):
            existing_rows = read_rows_from_xlsx(xlsx_path)
            merged_rows = _merge_versioned_rows(
                existing_rows,
                rows,
                proposal_version,
                allowed_keys=locked_keys,
            )
            enriched["rows"] = merged_rows

        export_chapter_xlsx(xlsx_path, spec, enriched)
        written.append(str(xlsx_path))
    return written
