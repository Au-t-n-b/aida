from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _safe_key(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "default").strip("_")
    return safe or "default"


def state_path(skill_root: Path, thread_id: str) -> Path:
    root = skill_root / "ProjectData" / "State"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{_safe_key(thread_id)}.json"


def load_state(skill_root: Path, thread_id: str) -> dict[str, Any]:
    path = state_path(skill_root, thread_id)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(skill_root: Path, thread_id: str, data: dict[str, Any]) -> None:
    path = state_path(skill_root, thread_id)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_state(skill_root: Path, thread_id: str, **changes: Any) -> dict[str, Any]:
    data = load_state(skill_root, thread_id)
    data.update(changes)
    save_state(skill_root, thread_id, data)
    return data
