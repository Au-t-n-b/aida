"""Read maintenance proposal SLA parse JSON from IPO parse directory."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.proposal.draft_store import maint_proposal_parse_dir

MAINT_SLA_PARSE_FILENAME = "维保建议书解析结果.json"


def maint_sla_parse_path(project_id: str) -> Path:
    return maint_proposal_parse_dir(project_id) / MAINT_SLA_PARSE_FILENAME


def load_maintenance_sla_parse_json(project_id: str) -> dict[str, Any] | None:
    path = maint_sla_parse_path(project_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
