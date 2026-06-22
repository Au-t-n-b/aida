"""Read maintenance proposal SLA parse JSON from datacenter parse directory."""
from __future__ import annotations

import json
from typing import Any

from shared.datacenter.types import SemanticFileRef

from agent.proposal.dc_store import read_bytes
from agent.services.dc_path_mapper import map_project_relative

MAINT_SLA_PARSE_FILENAME = "维保建议书解析结果.json"


def load_maintenance_sla_parse_json(project_id: str) -> dict[str, Any] | None:
    mapped = map_project_relative(project_id, f"早期介入/交付预案/解析结果/维保建议书解析结果/{MAINT_SLA_PARSE_FILENAME}")
    if mapped is None or not mapped.ref.file_name:
        return None
    ref = SemanticFileRef(
        project_id=mapped.ref.project_id,
        module_code=mapped.ref.module_code,
        file_stage=mapped.ref.file_stage,
        folder_sub_path=mapped.ref.folder_sub_path,
        file_name=mapped.ref.file_name,
    )
    raw = read_bytes(ref)
    if not raw:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
