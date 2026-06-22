"""Read service BOQ normalized JSON from datacenter parse directory."""
from __future__ import annotations

import json
from typing import Any

from shared.datacenter.types import SemanticFileRef

from agent.proposal.dc_store import list_file_names, read_bytes
from agent.services.dc_path_mapper import map_project_relative


def find_latest_normalized_json(project_id: str) -> tuple[str, dict[str, Any]] | None:
    mapped = map_project_relative(project_id, "早期介入/合同/解析结果/服务BOQ解析结果")
    if mapped is None:
        return None
    folder_ref = SemanticFileRef(
        project_id=mapped.ref.project_id,
        module_code=mapped.ref.module_code,
        file_stage=mapped.ref.file_stage,
        folder_sub_path=mapped.ref.folder_sub_path,
    )
    candidates = sorted(
        name for name in list_file_names(folder_ref) if name.endswith(".normalized.json")
    )
    if not candidates:
        return None
    if len(candidates) == 1:
        name = candidates[0]
        payload = _load_json_for_name(folder_ref, name)
        return (name, payload) if payload else None

    parsed: list[tuple[str, dict[str, Any]]] = []
    for name in candidates:
        payload = _load_json_for_name(folder_ref, name)
        if payload:
            parsed.append((name, payload))
    if not parsed:
        return None

    def _parsed_at(item: tuple[str, dict[str, Any]]) -> str:
        return str(item[1].get("parsed_at") or "")

    return max(parsed, key=_parsed_at)


def _load_json_for_name(folder_ref: SemanticFileRef, file_name: str) -> dict[str, Any] | None:
    ref = SemanticFileRef(
        project_id=folder_ref.project_id,
        module_code=folder_ref.module_code,
        file_stage=folder_ref.file_stage,
        folder_sub_path=folder_ref.folder_sub_path,
        file_name=file_name,
    )
    raw = read_bytes(ref)
    if not raw:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_normalized_boq(project_id: str) -> dict[str, Any] | None:
    hit = find_latest_normalized_json(project_id)
    if hit is None:
        return None
    _, payload = hit
    return payload
