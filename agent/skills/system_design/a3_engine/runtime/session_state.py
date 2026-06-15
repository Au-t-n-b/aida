from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from path_config import RUNTIME_DIR, ensure_dirs  # noqa: E402


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def session_rid_path() -> Path:
    return Path(RUNTIME_DIR) / "session_rid.json"


def pipeline_state_path() -> Path:
    return Path(RUNTIME_DIR) / "pipeline_state.json"


def plane_progress_path() -> Path:
    return Path(RUNTIME_DIR) / "plane_progress.json"


def get_session_rid(*, thread_id: str) -> str:
    ensure_dirs()
    path = session_rid_path()
    data = _read_json(path)
    rid = str(data.get("rid") or "").strip()
    if not rid:
        rid = f"a3:{thread_id}:{uuid.uuid4().hex[:8]}"
        _write_json(path, {"rid": rid, "thread_id": thread_id})
    return rid


def hitl_request_id(thread_id: str, suffix: str) -> str:
    return f"{get_session_rid(thread_id=thread_id)}:{suffix}"


def load_pipeline_state() -> dict[str, Any]:
    ensure_dirs()
    return _read_json(pipeline_state_path())


def save_pipeline_state(**fields: Any) -> dict[str, Any]:
    ensure_dirs()
    state = load_pipeline_state()
    state.update({k: v for k, v in fields.items() if v is not None})
    _write_json(pipeline_state_path(), state)
    return state


def load_plane_progress() -> dict[str, Any]:
    ensure_dirs()
    data = _read_json(plane_progress_path())
    if not data:
        data = {"planes": {}, "updated_at": None}
    return data


def save_plane_progress(data: dict[str, Any]) -> None:
    ensure_dirs()
    _write_json(plane_progress_path(), data)
