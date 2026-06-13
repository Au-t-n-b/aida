from __future__ import annotations

import os
import re
import sys
from typing import Any

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
_dolt_engine: Any | None = None


class DoltSchemaSyncUnavailableError(RuntimeError):
    """Raised when Dolt schema sync is required but Dolt cannot be reached."""


def object_type_table_name(object_type: str, object_schema: dict[str, Any]) -> str:
    api_name = str(object_schema.get("apiName") or object_type or "").strip()
    table_name = to_snake_case(api_name)
    validate_sql_identifier(table_name, kind="table")
    return table_name


def to_snake_case(value: str) -> str:
    raw = str(value or "").strip()
    first_pass = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", raw)
    second_pass = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first_pass)
    return second_pass.lower()


def validate_sql_identifier(name: str, *, kind: str = "SQL") -> None:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid {kind} identifier: {name!r}")


def quote_ident(name: str) -> str:
    validate_sql_identifier(name, kind="SQL")
    return "`" + name.replace("`", "``") + "`"


def build_create_table_sql(object_type: str, object_schema: dict[str, Any]) -> str:
    table_name = object_type_table_name(object_type, object_schema)
    primary_key = _primary_key_fields(object_schema)
    primary_key_set = set(primary_key)

    parts: list[str] = []
    seen_columns: set[str] = set()
    for fallback_name, property_schema in _iter_properties(object_schema):
        column_name = _property_api_name(fallback_name, property_schema)
        if column_name in seen_columns:
            continue
        seen_columns.add(column_name)
        in_primary_key = column_name in primary_key_set
        parts.append(
            f"{quote_ident(column_name)} {_column_type_sql(property_schema, for_alter=False, in_primary_key=in_primary_key)}"
        )

    missing_primary_keys = primary_key_set - seen_columns
    if missing_primary_keys:
        raise ValueError(f"primaryKey columns not found in properties: {sorted(missing_primary_keys)}")
    if primary_key:
        parts.append(f"PRIMARY KEY ({', '.join(quote_ident(column) for column in primary_key)})")
    if not parts:
        raise ValueError(f"Object type `{object_type}` has no Dolt columns to create.")

    columns_sql = ",\n  ".join(parts)
    return f"CREATE TABLE IF NOT EXISTS {quote_ident(table_name)} (\n  {columns_sql}\n)"


def build_add_column_statements(
    table_name: str,
    object_schema: dict[str, Any],
    existing_columns: set[str],
) -> tuple[list[str], list[str]]:
    validate_sql_identifier(table_name, kind="table")
    statements: list[str] = []
    added_columns: list[str] = []
    for fallback_name, property_schema in _iter_properties(object_schema):
        column_name = _property_api_name(fallback_name, property_schema)
        if column_name in existing_columns or column_name in added_columns:
            continue
        added_columns.append(column_name)
        statements.append(
            f"ALTER TABLE {quote_ident(table_name)} ADD COLUMN {quote_ident(column_name)} "
            f"{_column_type_sql(property_schema, for_alter=True, in_primary_key=False)}"
        )
    return statements, added_columns


def sync_object_type_dolt_schema(
    object_type: str,
    object_schema: dict[str, Any],
    *,
    engine: Any | None = None,
) -> dict[str, Any]:
    table_name = object_type_table_name(object_type, object_schema)
    primary_key = _primary_key_fields(object_schema)
    base_result = {
        "objectType": object_type,
        "tableName": table_name,
        "primaryKey": primary_key,
        "addedColumns": [],
        "errors": [],
    }

    resolved_engine = _resolve_engine(engine)
    if resolved_engine is None:
        return {**base_result, "status": "skipped"}

    create_sql = build_create_table_sql(object_type, object_schema)
    try:
        with resolved_engine.connect() as conn:
            if _checkout_branch_enabled():
                _call_checkout(conn, _get_dolt_main_branch())
                conn.commit()
            conn.execute(_sql_text(create_sql))
            conn.commit()
            existing_columns = _fetch_column_names(conn, table_name)
            statements, added_columns = build_add_column_statements(table_name, object_schema, existing_columns)
            for statement in statements:
                conn.execute(_sql_text(statement))
            conn.commit()
            if _truthy_env("DOLT_SCHEMA_SYNC_COMMIT"):
                _call_commit(conn, f"Sync ObjectType schema for {object_type}")
                conn.commit()
    except Exception as exc:
        return {**base_result, "status": "error", "errors": [str(exc)]}

    return {**base_result, "status": "ok", "addedColumns": added_columns}


def sync_all_object_type_dolt_schemas(
    object_types: dict[str, Any],
    *,
    engine: Any | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for object_type, object_schema in object_types.items():
        if not isinstance(object_schema, dict):
            result = {
                "objectType": object_type,
                "tableName": "",
                "status": "error",
                "primaryKey": [],
                "addedColumns": [],
                "errors": [f"Object type schema must be a JSON object: {object_type}"],
            }
        else:
            result = sync_object_type_dolt_schema(object_type, object_schema, engine=engine)
        items.append(result)
        if result.get("status") == "error":
            errors.append({"objectType": object_type, "errors": result.get("errors", [])})

    statuses = {str(item.get("status")) for item in items}
    status = "error" if errors else ("skipped" if statuses == {"skipped"} else "ok")
    return {"status": status, "items": items, "errors": errors}


def _iter_properties(object_schema: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    properties = object_schema.get("properties")
    if not isinstance(properties, dict):
        return []
    return [(name, schema) for name, schema in properties.items() if isinstance(schema, dict)]


def _property_api_name(fallback_name: str, property_schema: dict[str, Any]) -> str:
    column_name = str(property_schema.get("apiName") or fallback_name or "").strip()
    validate_sql_identifier(column_name, kind="column")
    return column_name


def _primary_key_fields(object_schema: dict[str, Any]) -> list[str]:
    raw = object_schema.get("primaryKeyPropertyApiNames")
    if not isinstance(raw, list):
        return []
    primary_key = [str(item).strip() for item in raw if isinstance(item, str) and str(item).strip()]
    for column_name in primary_key:
        validate_sql_identifier(column_name, kind="primary key column")
    return primary_key


def _column_type_sql(
    property_schema: dict[str, Any],
    *,
    for_alter: bool,
    in_primary_key: bool,
) -> str:
    base_type = _map_data_type(_property_data_type(property_schema))
    if for_alter:
        return f"{base_type} NULL"
    required = bool(property_schema.get("required", False)) or in_primary_key
    return f"{base_type}{' NOT NULL' if required else ' NULL'}"


def _property_data_type(property_schema: dict[str, Any]) -> str:
    data_type = property_schema.get("dataType")
    if isinstance(data_type, dict):
        raw = data_type.get("type") or data_type.get("typeName")
        return str(raw or "")
    if data_type is not None:
        return str(data_type)
    return ""


def _map_data_type(data_type: str) -> str:
    normalized = str(data_type or "").strip().lower()
    mapping = {
        "string": "VARCHAR(255)",
        "str": "VARCHAR(255)",
        "text": "TEXT",
        "integer": "INT",
        "int": "INT",
        "long": "BIGINT",
        "bigint": "BIGINT",
        "double": "DOUBLE",
        "float": "DOUBLE",
        "number": "DOUBLE",
        "boolean": "BOOLEAN",
        "bool": "BOOLEAN",
        "date": "DATE",
        "timestamp": "DATETIME(6)",
        "datetime": "DATETIME(6)",
    }
    if normalized in {"array", "list", "set", "json"}:
        return "LONGTEXT" if _truthy_env("DOLT_SCHEMA_SYNC_JSON_AS_TEXT") else "JSON"
    return mapping.get(normalized, "TEXT")


def _truthy_env(name: str) -> bool:
    value = (os.getenv(name) or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _checkout_branch_enabled() -> bool:
    value = (os.getenv("DOLT_SCHEMA_SYNC_CHECKOUT_BRANCH") or "").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _get_dolt_main_branch() -> str:
    return (os.getenv("DOLT_MAIN_BRANCH") or "main").strip() or "main"


def _get_dolt_database_url() -> str:
    raw = (os.getenv("DOLT_DATABASE_URL") or "").strip()
    if not raw:
        raise DoltSchemaSyncUnavailableError("DOLT_DATABASE_URL is not set.")
    lower = raw.lower()
    if not (lower.startswith("mysql+pymysql://") or lower.startswith("mysql+mysqldb://")):
        raise DoltSchemaSyncUnavailableError(
            "DOLT_DATABASE_URL must use a MySQL driver dialect such as mysql+pymysql://."
        )
    return raw


def _resolve_engine(engine: Any | None) -> Any | None:
    if engine is not None:
        return engine
    try:
        return _get_dolt_engine()
    except DoltSchemaSyncUnavailableError:
        if _truthy_env("DOLT_SCHEMA_SYNC_REQUIRED"):
            raise
        return None


def _get_dolt_engine() -> Any:
    global _dolt_engine
    if _dolt_engine is not None:
        return _dolt_engine
    url = _get_dolt_database_url()
    try:
        import pymysql  # noqa: F401
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool
    except ImportError as exc:
        raise DoltSchemaSyncUnavailableError(
            "PyMySQL and SQLAlchemy are required for Dolt schema sync. "
            f'Use this interpreter: {sys.executable}.'
        ) from exc
    _dolt_engine = create_engine(url, poolclass=NullPool, future=True)
    return _dolt_engine


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
    if hasattr(result, "mappings"):
        return {str(row.get("COLUMN_NAME")) for row in result.mappings().all() if row.get("COLUMN_NAME") is not None}
    rows = result.fetchall() if hasattr(result, "fetchall") else []
    return {str(row[0]) for row in rows if row and row[0] is not None}


def _sql_text(sql: str) -> Any:
    try:
        from sqlalchemy import text
    except ImportError:
        return sql
    return text(sql)


def _call_checkout(conn: Any, branch: str) -> None:
    conn.execute(_sql_text("CALL dolt_checkout(:branch)"), {"branch": branch})


def _call_commit(conn: Any, message: str) -> None:
    if "\x00" in message:
        raise ValueError("commit message must not contain NUL")
    conn.execute(_sql_text("CALL dolt_commit('-A', '-m', :message)"), {"message": message[:500]})
