from __future__ import annotations

import os
import re
import uuid
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from dolt_schema_sync import object_type_table_name
from scenario_lifecycle_manager import (
    ScenarioLifecycleManager,
    ScenarioUnavailableError,
)

PREVIEW_BRANCH_HEADER = "Preview-Branch-Id"
DELIVERY_PLAN_ROW_TABLE = "delivery_plan_row"
MILESTONE_TABLE = "milestone"
BASE_DIR = Path(__file__).parent
OBJECT_TYPES_PATH = BASE_DIR / "schema" / "object-types.json"

_BRANCH_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_HEX32_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
_MAIN_ALIASES = {"", "main", "master"}
_current_preview_branch: ContextVar[PreviewBranchContext | None] = ContextVar(
    "current_preview_branch",
    default=None,
)
_dolt_engine: Any | None = None
_scenario_manager: ScenarioLifecycleManager | None = None


class PreviewBranchUnavailableError(RuntimeError):
    """Raised when a preview branch request requires Dolt but Dolt is unavailable."""


@dataclass(frozen=True)
class PreviewBranchContext:
    raw_header: str | None
    preview_branch_id: str
    dolt_branch: str
    is_main: bool


def get_dolt_main_branch() -> str:
    return (os.getenv("DOLT_MAIN_BRANCH") or "main").strip() or "main"


def writeback_overlay_enabled() -> bool:
    """When enabled, pipeline ingestion overlays onto Dolt main via the ingest
    branch (Foundry-style writeback), and backing object reads/writes are served
    from Dolt main instead of CSV. Off by default so CSV remains the source of
    truth until a Dolt deployment opts in."""
    return (os.getenv("DOLT_WRITEBACK_OVERLAY") or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_preview_branch_context(raw_value: str | None) -> PreviewBranchContext:
    raw = "" if raw_value is None else str(raw_value).strip()
    main = get_dolt_main_branch()
    if raw.lower() in _MAIN_ALIASES:
        return PreviewBranchContext(
            raw_header=raw_value,
            preview_branch_id="master",
            dolt_branch=main,
            is_main=True,
        )
    _validate_branch_name(raw)
    return PreviewBranchContext(
        raw_header=raw_value,
        preview_branch_id=raw,
        dolt_branch=raw,
        is_main=False,
    )


@contextmanager
def use_preview_branch(context: PreviewBranchContext) -> Iterator[PreviewBranchContext]:
    token = _current_preview_branch.set(context)
    try:
        yield context
    finally:
        _current_preview_branch.reset(token)


def get_current_preview_branch() -> PreviewBranchContext:
    context = _current_preview_branch.get()
    if context is None:
        return resolve_preview_branch_context(None)
    return context


def list_preview_branches() -> dict[str, Any]:
    return _get_scenario_manager().list_scenarios()


def create_preview_branch(
    *,
    base_context: PreviewBranchContext,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = payload or {}
    requested = str(body.get("previewBranchId") or body.get("branchId") or "").strip()
    preview_branch_id = requested or f"shadow_{uuid.uuid4().hex[:12]}"
    _validate_preview_branch_id(preview_branch_id)

    source_branch = base_context.dolt_branch
    _get_scenario_manager().create_scenario(preview_branch_id)
    return {
        "previewBranchId": preview_branch_id,
        "doltBranch": preview_branch_id,
        "baseBranch": source_branch,
        "status": "ACTIVE",
    }


def publish_preview_branch(preview_branch_id: str) -> dict[str, Any]:
    _validate_preview_branch_id(preview_branch_id)
    return _get_scenario_manager().resolve_scenario(preview_branch_id, accept=True)


def discard_preview_branch(preview_branch_id: str) -> dict[str, Any]:
    _validate_preview_branch_id(preview_branch_id)
    return _get_scenario_manager().resolve_scenario(preview_branch_id, accept=False)


def get_object_data_for_branch(
    context: PreviewBranchContext,
    object_type: str,
    project_key: str | None = None,
) -> list[dict[str, Any]]:
    return _get_scenario_manager().read_table(context.dolt_branch, object_type, project_key=project_key)


def read_delivery_plan_source_rows(
    context: PreviewBranchContext,
    *,
    project_key: str,
    source_columns: dict[str, str],
) -> list[dict[str, str]]:
    object_rows = get_object_data_for_branch(context, "DeliveryPlanRow", project_key=project_key)
    source_rows: list[dict[str, str]] = []
    for object_row in object_rows:
        source_row: dict[str, str] = {}
        for api_name, source_column in source_columns.items():
            source_row[source_column] = "" if object_row.get(api_name) is None else str(object_row.get(api_name))
        source_rows.append(source_row)
    return source_rows


def apply_update_milestone_date_batch_to_dolt(
    context: PreviewBranchContext,
    normalized_items: list[dict[str, Any]],
    *,
    project_key: str | None = None,
) -> dict[str, Any]:
    return _get_scenario_manager().apply_update_milestone_date_batch(
        context.dolt_branch,
        normalized_items,
        project_key=project_key,
    )


def apply_object_update_to_dolt(
    context: PreviewBranchContext,
    object_type: str,
    primary_key: dict[str, Any],
    changes: dict[str, Any],
    *,
    author: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Generic single-object Action writeback to the context's Dolt branch.

    ``author`` (a Dolt ``"Name <email>"`` string) and ``message`` are recorded on the
    commit so the object history read side can attribute who changed what and why.
    """
    return _get_scenario_manager().apply_object_update(
        context.dolt_branch,
        object_type,
        primary_key,
        changes,
        author=author,
        message=message,
    )


def get_object_history_for_branch(
    context: PreviewBranchContext,
    object_type: str,
    primary_key: dict[str, Any],
    *,
    project_key: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    return _get_scenario_manager().read_object_history(
        context.dolt_branch,
        object_type,
        primary_key,
        project_key=project_key,
        limit=limit,
    )


def get_object_as_of_for_branch(
    context: PreviewBranchContext,
    object_type: str,
    ref: str,
    *,
    primary_key: dict[str, Any] | None = None,
    project_key: str | None = None,
) -> list[dict[str, Any]]:
    return _get_scenario_manager().read_table_as_of(
        context.dolt_branch,
        object_type,
        ref,
        primary_key=primary_key,
        project_key=project_key,
    )


def get_object_diff_for_branch(
    context: PreviewBranchContext,
    object_type: str,
    from_ref: str,
    to_ref: str,
    primary_key: dict[str, Any],
    *,
    project_key: str | None = None,
) -> list[dict[str, Any]]:
    return _get_scenario_manager().read_object_diff(
        context.dolt_branch,
        object_type,
        from_ref,
        to_ref,
        primary_key,
        project_key=project_key,
    )


def _object_type_table(object_type: str) -> str:
    object_schema = _load_object_types().get(object_type)
    if not isinstance(object_schema, dict):
        raise PreviewBranchUnavailableError(
            f"{PREVIEW_BRANCH_HEADER} routing is not implemented for object type `{object_type}`."
        )
    try:
        return object_type_table_name(object_type, object_schema)
    except ValueError as exc:
        raise PreviewBranchUnavailableError(str(exc)) from exc


def _load_object_types() -> dict[str, Any]:
    with OBJECT_TYPES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _get_dolt_database_url() -> str:
    raw = (os.getenv("DOLT_DATABASE_URL") or "").strip()
    if not raw:
        raise PreviewBranchUnavailableError(
            "DOLT_DATABASE_URL is required when using Preview-Branch-Id."
        )
    lower = raw.lower()
    if not (lower.startswith("mysql+pymysql://") or lower.startswith("mysql+mysqldb://")):
        raise PreviewBranchUnavailableError(
            "DOLT_DATABASE_URL must use a MySQL SQLAlchemy dialect such as mysql+pymysql://."
        )
    return raw


def _get_dolt_engine() -> Any:
    if _dolt_engine is not None:
        return _dolt_engine
    return _get_scenario_manager().get_main_engine()


def _get_scenario_manager() -> ScenarioLifecycleManager:
    global _scenario_manager
    if _dolt_engine is not None:
        return ScenarioLifecycleManager(
            database_url=(os.getenv("DOLT_DATABASE_URL") or "mysql+pymysql://local:@127.0.0.1:3306/dolt"),
            main_branch=get_dolt_main_branch(),
            engine_factory=lambda *_args, **_kwargs: _dolt_engine,
        )
    if _scenario_manager is None:
        try:
            _scenario_manager = ScenarioLifecycleManager(
                database_url=_get_dolt_database_url(),
                main_branch=get_dolt_main_branch(),
            )
        except ScenarioUnavailableError as exc:
            raise PreviewBranchUnavailableError(str(exc)) from exc
    return _scenario_manager


def get_scenario_manager() -> ScenarioLifecycleManager:
    """Public accessor for the shared ScenarioLifecycleManager (Dolt branch ops)."""
    return _get_scenario_manager()


def _validate_branch_name(branch_id: str) -> None:
    if not branch_id:
        raise ValueError(f"{PREVIEW_BRANCH_HEADER} must not be empty.")
    if branch_id.upper() == "HEAD":
        raise ValueError(f"{PREVIEW_BRANCH_HEADER} must not be HEAD.")
    if _HEX32_RE.match(branch_id):
        raise ValueError(f"{PREVIEW_BRANCH_HEADER} must not look like a commit hash.")
    if not _BRANCH_RE.match(branch_id):
        raise ValueError(f"Invalid {PREVIEW_BRANCH_HEADER}: {branch_id!r}.")


def _validate_preview_branch_id(branch_id: str) -> None:
    _validate_branch_name(branch_id)
    if branch_id.lower() in _MAIN_ALIASES:
        raise ValueError(f"{PREVIEW_BRANCH_HEADER} must be a non-main preview branch.")


def ensure_preview_branch_available(_context: PreviewBranchContext) -> None:
    _get_scenario_manager().get_scenario_engine(_context.dolt_branch)


def _validate_sql_identifier(name: str, *, kind: str) -> None:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid {kind} identifier: {name!r}")


def _sql_text(sql: str):
    from sqlalchemy import text

    return text(sql)


def _call_checkout(conn: Any, branch: str) -> None:
    conn.execute(_sql_text("CALL dolt_checkout(:branch)"), {"branch": branch})


def _call_branch(conn: Any, branch: str) -> None:
    conn.execute(_sql_text("CALL dolt_branch(:branch)"), {"branch": branch})


def _call_commit(conn: Any, message: str) -> None:
    try:
        conn.execute(_sql_text("CALL dolt_commit('-A', '-m', :message)"), {"message": message[:500]})
    except Exception as exc:
        if "nothing to commit" in str(exc).lower():
            return
        raise


def _call_reset_hard(conn: Any) -> None:
    conn.execute(_sql_text("CALL dolt_reset('--hard')"))


def _branch_exists(conn: Any, branch: str) -> bool:
    row = conn.execute(
        _sql_text("SELECT 1 AS ok FROM dolt_branches WHERE name = :name LIMIT 1"),
        {"name": branch},
    ).first()
    return row is not None
