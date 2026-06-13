from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import data_connector
from datasource_bindings import object_types_with_backing_data
from dolt_schema_sync import (
    _call_checkout,
    _get_dolt_engine,
    _get_dolt_main_branch,
    _sql_text,
    build_add_column_statements,
    build_create_table_sql,
    object_type_table_name,
    quote_ident,
    validate_sql_identifier,
)
from preview_branch import (
    PreviewBranchContext,
    PreviewBranchUnavailableError,
    ensure_preview_branch_available,
    get_scenario_manager,
    resolve_preview_branch_context,
    use_preview_branch,
    writeback_overlay_enabled,
)


BASE_DIR = Path(__file__).parent
OBJECT_TYPES_PATH = BASE_DIR / "schema" / "object-types.json"
SUPPORTED_MIRROR_OBJECT_TYPES = tuple(object_types_with_backing_data())
SAMPLE_LIMIT = 5


def supported_mirror_object_types() -> tuple[str, ...]:
    return tuple(object_types_with_backing_data())


class DoltMirrorUnavailableError(PreviewBranchUnavailableError):
    """Raised when mirror operations require Dolt but it is not reachable."""


def sync_main_mirror(
    object_types: list[str] | tuple[str, ...] | str | None = None,
    *,
    object_type_schemas: dict[str, Any] | None = None,
    engine: Any | None = None,
) -> dict[str, Any]:
    schemas = object_type_schemas or _load_object_types()
    target_object_types = _normalize_object_types(object_types)
    resolved_engine = _require_engine(engine)
    overlay = writeback_overlay_enabled()
    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for object_type in target_object_types:
        try:
            schema = _require_schema(schemas, object_type)
            if overlay:
                item = _sync_object_type_via_ingest(object_type, schema)
            else:
                item = _sync_object_type(resolved_engine, object_type, schema)
            items.append(item)
        except Exception as exc:
            error = {"objectType": object_type, "errors": [str(exc)]}
            errors.append(error)
            items.append(
                {
                    "objectType": object_type,
                    "tableName": _safe_table_name(schemas, object_type),
                    "csvCount": 0,
                    "doltCount": 0,
                    "missingInDolt": 0,
                    "extraInDolt": 0,
                    "mismatchedRows": 0,
                    "status": "error",
                    "errors": [str(exc)],
                }
            )

    return {"status": "error" if errors else "ok", "items": items, "errors": errors}


def validate_main_mirror(
    object_types: list[str] | tuple[str, ...] | str | None = None,
    *,
    object_type_schemas: dict[str, Any] | None = None,
    engine: Any | None = None,
) -> dict[str, Any]:
    schemas = object_type_schemas or _load_object_types()
    target_object_types = _normalize_object_types(object_types)
    resolved_engine = _require_engine(engine)
    overlay = writeback_overlay_enabled()
    ingest_branch = get_scenario_manager().ingest_branch if overlay else None
    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for object_type in target_object_types:
        try:
            item = _validate_object_type(
                resolved_engine, object_type, _require_schema(schemas, object_type), branch=ingest_branch
            )
            items.append(item)
        except Exception as exc:
            error = {"objectType": object_type, "errors": [str(exc)]}
            errors.append(error)
            items.append(
                {
                    "objectType": object_type,
                    "tableName": _safe_table_name(schemas, object_type),
                    "csvCount": 0,
                    "doltCount": 0,
                    "missingInDolt": 0,
                    "extraInDolt": 0,
                    "mismatchedRows": 0,
                    "status": "error",
                    "errors": [str(exc)],
                }
            )

    if errors:
        status = "error"
    elif any(item.get("status") == "drift" for item in items):
        status = "drift"
    else:
        status = "ok"
    return {"status": status, "items": items, "errors": errors}


def ensure_preview_branch_data_source(context: PreviewBranchContext) -> None:
    if context.is_main:
        return
    ensure_preview_branch_available(context)


def _sync_object_type(engine: Any, object_type: str, object_schema: dict[str, Any]) -> dict[str, Any]:
    table_name = object_type_table_name(object_type, object_schema)
    rows = _current_csv_rows(object_type)
    columns = _schema_column_names(object_schema)
    with engine.connect() as conn:
        try:
            _checkout_main(conn)
            _ensure_table_schema(conn, object_type, object_schema, table_name)
            conn.commit()
            conn.execute(_sql_text(f"DELETE FROM {quote_ident(table_name)}"))
            for row in rows:
                _insert_row(conn, table_name, columns, row)
            conn.commit()
            _call_commit_allow_empty(conn, f"Sync Dolt main mirror for {object_type}")
            conn.commit()
        except Exception:
            _call_reset_hard_allow_unavailable(conn)
            conn.commit()
            raise
        finally:
            _checkout_main(conn)
            conn.commit()

    count = len(rows)
    return {
        "objectType": object_type,
        "tableName": table_name,
        "csvCount": count,
        "doltCount": count,
        "missingInDolt": 0,
        "extraInDolt": 0,
        "mismatchedRows": 0,
        "status": "ok",
        "errors": [],
    }


def _sync_object_type_via_ingest(object_type: str, object_schema: dict[str, Any]) -> dict[str, Any]:
    """Foundry-style overlay sync: write CSV (pipeline) rows to the ingest branch and
    merge into main with --ours, preserving user/Action edits on main."""
    table_name = object_type_table_name(object_type, object_schema)
    rows = _current_csv_rows(object_type)
    columns = _schema_column_names(object_schema)
    primary_key = _primary_key_fields(object_schema)
    manager = get_scenario_manager()
    with manager.get_main_engine().connect() as conn:
        _ensure_table_schema(conn, object_type, object_schema, table_name)
        conn.commit()
    result = manager.ingest_and_merge(table_name, rows, columns=columns, primary_keys=primary_key)
    count = len(rows)
    return {
        "objectType": object_type,
        "tableName": table_name,
        "csvCount": count,
        "doltCount": int(result.get("rowsWritten", count) or count),
        "missingInDolt": 0,
        "extraInDolt": 0,
        "mismatchedRows": 0,
        "status": "ok",
        "errors": [],
        "ingestBranch": result.get("ingestBranch"),
    }


def _validate_object_type(
    engine: Any,
    object_type: str,
    object_schema: dict[str, Any],
    *,
    branch: str | None = None,
) -> dict[str, Any]:
    table_name = object_type_table_name(object_type, object_schema)
    primary_key = _primary_key_fields(object_schema)
    if not primary_key:
        raise ValueError(f"ObjectType `{object_type}` must define a primary key for mirror validation.")
    rows = _current_csv_rows(object_type)
    if branch:
        dolt_rows = get_scenario_manager().read_table(branch, table_name)
    else:
        dolt_rows = _read_dolt_rows(engine, table_name)
    csv_by_key = {_row_key(row, primary_key): row for row in rows}
    dolt_by_key = {_row_key(row, primary_key): row for row in dolt_rows}

    missing_keys = sorted(set(csv_by_key) - set(dolt_by_key))
    extra_keys = sorted(set(dolt_by_key) - set(csv_by_key))
    checked_fields = _comparison_fields(object_schema, primary_key)
    mismatched_keys: list[str] = []
    for key in sorted(set(csv_by_key) & set(dolt_by_key)):
        has_mismatch = any(
            _normalize_value(csv_by_key[key].get(field)) != _normalize_value(dolt_by_key[key].get(field))
            for field in checked_fields
        )
        if has_mismatch:
            mismatched_keys.append(key)

    status = "ok" if not missing_keys and not extra_keys and not mismatched_keys else "drift"
    return {
        "objectType": object_type,
        "tableName": table_name,
        "csvCount": len(rows),
        "doltCount": len(dolt_rows),
        "missingInDolt": len(missing_keys),
        "extraInDolt": len(extra_keys),
        "mismatchedRows": len(mismatched_keys),
        "missingKeysSample": missing_keys[:SAMPLE_LIMIT],
        "extraKeysSample": extra_keys[:SAMPLE_LIMIT],
        "mismatchedKeysSample": mismatched_keys[:SAMPLE_LIMIT],
        "checkedFields": checked_fields,
        "status": status,
        "errors": [],
    }


def _ensure_table_schema(conn: Any, object_type: str, object_schema: dict[str, Any], table_name: str) -> None:
    conn.execute(_sql_text(build_create_table_sql(object_type, object_schema)))
    existing_columns = _fetch_column_names(conn, table_name)
    statements, _added_columns = build_add_column_statements(table_name, object_schema, existing_columns)
    for statement in statements:
        conn.execute(_sql_text(statement))


def _insert_row(conn: Any, table_name: str, columns: list[str], source_row: dict[str, Any]) -> None:
    if not columns:
        return
    for column in columns:
        validate_sql_identifier(column, kind="column")
    column_sql = ", ".join(quote_ident(column) for column in columns)
    values_sql = ", ".join(f":{column}" for column in columns)
    params = {column: _sql_value(source_row.get(column)) for column in columns}
    conn.execute(
        _sql_text(f"INSERT INTO {quote_ident(table_name)} ({column_sql}) VALUES ({values_sql})"),
        params,
    )


def _read_dolt_rows(engine: Any, table_name: str) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        _checkout_main(conn)
        result = conn.execute(_sql_text(f"SELECT * FROM {quote_ident(table_name)}"))
        rows = _result_mappings(result)
        conn.commit()
        return rows


def _fetch_column_names(conn: Any, table_name: str) -> set[str]:
    result = conn.execute(
        _sql_text(
            """
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
            """
        ),
        {"table_name": table_name},
    )
    return {str(row.get("COLUMN_NAME")) for row in _result_mappings(result) if row.get("COLUMN_NAME") is not None}


def _result_mappings(result: Any) -> list[dict[str, Any]]:
    if hasattr(result, "mappings"):
        return [dict(row) for row in result.mappings().all()]
    rows = result.fetchall() if hasattr(result, "fetchall") else []
    return [dict(row) if isinstance(row, dict) else dict(enumerate(row)) for row in rows]


def _current_csv_rows(object_type: str) -> list[dict[str, Any]]:
    with use_preview_branch(resolve_preview_branch_context(None)):
        return data_connector.get_object_data(object_type)


def _checkout_main(conn: Any) -> None:
    _call_checkout(conn, _get_dolt_main_branch())


def _call_commit_allow_empty(conn: Any, message: str) -> None:
    try:
        conn.execute(_sql_text("CALL dolt_commit('-A', '-m', :message)"), {"message": message[:500]})
    except Exception as exc:
        if "nothing to commit" not in str(exc).lower():
            raise


def _call_reset_hard_allow_unavailable(conn: Any) -> None:
    try:
        conn.execute(_sql_text("CALL dolt_reset('--hard')"))
    except Exception:
        return


def _require_engine(engine: Any | None) -> Any:
    if engine is not None:
        return engine
    if not (os.getenv("DOLT_DATABASE_URL") or "").strip():
        raise DoltMirrorUnavailableError("DOLT_DATABASE_URL is required for Dolt mirror operations.")
    try:
        return _get_dolt_engine()
    except Exception as exc:
        message = str(exc) or "DOLT_DATABASE_URL is required for Dolt mirror operations."
        if "DOLT_DATABASE_URL" not in message:
            message = f"DOLT_DATABASE_URL is required for Dolt mirror operations. {message}"
        raise DoltMirrorUnavailableError(message) from exc


def _normalize_object_types(object_types: list[str] | tuple[str, ...] | str | None) -> list[str]:
    supported = supported_mirror_object_types()
    if object_types is None:
        names = list(supported)
    elif isinstance(object_types, str):
        names = [part.strip() for part in object_types.split(",") if part.strip()]
    else:
        names = [str(item).strip() for item in object_types if str(item).strip()]
    unsupported = [name for name in names if name not in supported]
    if unsupported:
        raise ValueError(f"Unsupported Dolt mirror object type(s): {', '.join(unsupported)}")
    return names


def _require_schema(object_types: dict[str, Any], object_type: str) -> dict[str, Any]:
    object_schema = object_types.get(object_type)
    if not isinstance(object_schema, dict):
        raise KeyError(f"ObjectType not found: {object_type}")
    return object_schema


def _safe_table_name(object_types: dict[str, Any], object_type: str) -> str:
    try:
        return object_type_table_name(object_type, _require_schema(object_types, object_type))
    except Exception:
        return ""


def _load_object_types() -> dict[str, Any]:
    with OBJECT_TYPES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _schema_column_names(object_schema: dict[str, Any]) -> list[str]:
    columns: list[str] = []
    properties = object_schema.get("properties") or {}
    if not isinstance(properties, dict):
        return columns
    for fallback_name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            continue
        column = str(property_schema.get("apiName") or fallback_name).strip()
        if column:
            validate_sql_identifier(column, kind="column")
            columns.append(column)
    return columns


def _primary_key_fields(object_schema: dict[str, Any]) -> list[str]:
    raw = object_schema.get("primaryKeyPropertyApiNames")
    if not isinstance(raw, list):
        return []
    primary_key = [str(item).strip() for item in raw if isinstance(item, str) and str(item).strip()]
    for column in primary_key:
        validate_sql_identifier(column, kind="primary key column")
    return primary_key


def _comparison_fields(object_schema: dict[str, Any], primary_key: list[str]) -> list[str]:
    primary_key_set = set(primary_key)
    return [column for column in _schema_column_names(object_schema) if column not in primary_key_set]


def _row_key(row: dict[str, Any], primary_key: list[str]) -> str:
    return "::".join(_normalize_value(row.get(column)) for column in primary_key)


def _sql_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
