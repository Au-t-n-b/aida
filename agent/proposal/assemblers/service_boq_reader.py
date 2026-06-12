"""Read service BOQ normalized JSON from IPO parse directory."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.proposal.draft_store import service_boq_parse_dir


def find_latest_normalized_json(project_id: str) -> Path | None:
    parse_dir = service_boq_parse_dir(project_id)
    if not parse_dir.exists():
        return None
    candidates = sorted(parse_dir.glob("*.normalized.json"))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    def _parsed_at(path: Path) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return str(data.get("parsed_at") or "")
        except (json.JSONDecodeError, OSError):
            return ""

    return max(candidates, key=_parsed_at)


def load_normalized_boq(project_id: str) -> dict[str, Any] | None:
    path = find_latest_normalized_json(project_id)
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))
