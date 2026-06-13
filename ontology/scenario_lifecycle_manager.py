from __future__ import annotations

import csv
import json
import os
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Iterable

from dolt_schema_sync import object_type_table_name, quote_ident, validate_sql_identifier


BASE_DIR = Path(__file__).parent
OBJECT_TYPES_PATH = BASE_DIR / "schema" / "object-types.json"
DELIVERY_PLAN_ROW_TABLE = "delivery_plan_row"
_BRANCH_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_HEX32_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
# A commit / timestamp / branch reference accepted by Dolt time-travel (AS OF, dolt
# commit-diff). Whitelisted to a quote/backtick/semicolon-free charset so the value
# can be safely inlined where bound parameters are not accepted (the AS OF clause).
# Covers commit hashes, branch names, ISO-8601 timestamps and relative refs (HEAD~1).
_COMMIT_REF_RE = re.compile(r"^[A-Za-z0-9 :.\-_+~]{1,64}$")
_MAIN_ALIASES = {"", "main", "master"}
_DEFAULT_INGEST_BRANCH = "ingest"


class ScenarioLifecycleError(RuntimeError):
    """沙盘生命周期通用异常。"""


class ScenarioUnavailableError(ScenarioLifecycleError):
    """Dolt 或 SQLAlchemy 不可用。"""


class ScenarioBranchExistsError(ScenarioLifecycleError):
    """目标沙盘分支已存在。"""


class ScenarioBranchNotFoundError(ScenarioLifecycleError):
    """目标沙盘分支不存在。"""


class ScenarioMergeConflictError(ScenarioLifecycleError):
    """沙盘合并 main 时发生冲突。"""


class ScenarioMergeRejectedError(ScenarioLifecycleError):
    """沙盘被业务规则拒绝合并。"""


EngineFactory = Callable[..., Any]


class ScenarioLifecycleManager:
    def __init__(
        self,
        *,
        database_url: str | None = None,
        engine_factory: EngineFactory | None = None,
        main_branch: str | None = None,
        max_cached_engines: int | None = None,
        ingest_chunk_size: int = 1000,
        ingest_branch: str | None = None,
    ) -> None:
        self.database_url = (database_url or os.getenv("DOLT_DATABASE_URL") or "").strip()
        self.main_branch = (main_branch or os.getenv("DOLT_MAIN_BRANCH") or "main").strip() or "main"
        self.ingest_branch = (
            ingest_branch or os.getenv("DOLT_INGEST_BRANCH") or _DEFAULT_INGEST_BRANCH
        ).strip() or _DEFAULT_INGEST_BRANCH
        self.max_cached_engines = max_cached_engines or int(os.getenv("DOLT_SCENARIO_ENGINE_CACHE_SIZE") or "128")
        self.ingest_chunk_size = max(1, int(ingest_chunk_size))
        self._engine_factory = engine_factory
        self._engine_cache: OrderedDict[str, Any] = OrderedDict()
        self._base_hash_by_branch: dict[str, str] = {}
        self._lock = threading.RLock()

    @property
    def reserved_branches(self) -> set[str]:
        """Branches that are not user scenarios (e.g. the pipeline ingest branch)."""
        return {self.ingest_branch}

    def create_scenario(self, scenario_id: str) -> str:
        branch_name = self._validate_scenario_branch(scenario_id)
        with self.get_main_engine().connect() as conn:
            if self._branch_exists(conn, branch_name):
                raise ScenarioBranchExistsError(f"Preview branch already exists: {branch_name}")
            base_hash = self._head_hash(conn)
            conn.execute(_sql_text("CALL dolt_branch(:branch)"), {"branch": branch_name})
            conn.commit()
        self._base_hash_by_branch[branch_name] = base_hash
        return branch_name

    def get_main_engine(self) -> Any:
        return self.get_scenario_engine(self.main_branch)

    def get_scenario_engine(self, branch_name: str) -> Any:
        branch = self._validate_branch_name(branch_name)
        with self._lock:
            cached = self._engine_cache.get(branch)
            if cached is not None:
                self._engine_cache.move_to_end(branch)
                return cached
            engine = self._build_engine(self._branch_database_url(branch))
            self._engine_cache[branch] = engine
            self._evict_oldest_engine_if_needed()
            return engine

    def dispose_scenario_engine(self, branch_name: str) -> None:
        branch = self._validate_branch_name(branch_name)
        with self._lock:
            engine = self._engine_cache.pop(branch, None)
        if engine is not None and hasattr(engine, "dispose"):
            engine.dispose()

    def list_scenarios(self) -> dict[str, Any]:
        with self.get_main_engine().connect() as conn:
            rows = conn.execute(_sql_text("SELECT name, hash FROM dolt_branches ORDER BY name")).mappings().all()
            conn.commit()
        items = [
            {
                "previewBranchId": row.get("name"),
                "doltBranch": row.get("name"),
                "isMain": str(row.get("name")) == self.main_branch,
                "headHash": row.get("hash"),
            }
            for row in rows
            if str(row.get("name")) != self.main_branch
            and str(row.get("name")) not in self.reserved_branches
        ]
        return {"items": items, "total": len(items)}

    def read_table(
        self,
        branch_name: str,
        table_name: str,
        *,
        project_key: str | None = None,
    ) -> list[dict[str, Any]]:
        table = self._resolve_table_name(table_name)
        sql = f"SELECT * FROM {quote_ident(table)}"
        params: dict[str, Any] = {}
        if project_key:
            sql += " WHERE `projectKey` = :project_key"
            params["project_key"] = project_key
        with self.get_scenario_engine(branch_name).connect() as conn:
            rows = [dict(row) for row in conn.execute(_sql_text(sql), params).mappings().all()]
            conn.commit()
        return rows

    def read_object_history(
        self,
        branch_name: str,
        object_type: str,
        primary_key: dict[str, Any],
        *,
        project_key: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return every committed version of one object (Dolt ``dolt_history_<table>``).

        Each item is the object's column values at one commit plus that commit's
        metadata (``commit_hash`` / ``committer`` / ``commit_date``) and message
        (joined from ``dolt_log``), newest commit first. This is the read side of the
        version history Dolt already records on every writeback — the equivalent of
        Foundry's object edit history, but covering every commit rather than only the
        opt-in Action edits Foundry tracks.
        """
        table = self._resolve_table_name(object_type)
        history_table = f"dolt_history_{table}"
        validate_sql_identifier(history_table, kind="table")
        clauses, params = self._object_filter_clauses(
            primary_key, project_key=project_key, prefix="pk_", qualifier="h"
        )
        sql = (
            f"SELECT h.*, l.message AS commit_message "
            f"FROM {quote_ident(history_table)} AS h "
            f"LEFT JOIN dolt_log AS l ON l.commit_hash = h.commit_hash"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY h.commit_date DESC"
        if limit is not None:
            sql += " LIMIT :history_limit"
            params["history_limit"] = max(1, int(limit))
        with self.get_scenario_engine(branch_name).connect() as conn:
            rows = [dict(row) for row in conn.execute(_sql_text(sql), params).mappings().all()]
            conn.commit()
        return rows

    def read_table_as_of(
        self,
        branch_name: str,
        object_type: str,
        ref: str,
        *,
        primary_key: dict[str, Any] | None = None,
        project_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read a table (optionally a single object) as of a commit/timestamp/branch.

        Uses Dolt time-travel (``SELECT ... AS OF``). ``ref`` is whitelisted and
        inlined as a string literal because ``AS OF`` is a table-expression clause
        that does not accept bound parameters; every row predicate stays parameterized.
        """
        table = self._resolve_table_name(object_type)
        ref_literal = self._commit_ref_literal(ref)
        clauses, params = self._object_filter_clauses(
            primary_key or {}, project_key=project_key, prefix="pk_"
        )
        sql = f"SELECT * FROM {quote_ident(table)} AS OF {ref_literal}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self.get_scenario_engine(branch_name).connect() as conn:
            rows = [dict(row) for row in conn.execute(_sql_text(sql), params).mappings().all()]
            conn.commit()
        return rows

    def read_object_diff(
        self,
        branch_name: str,
        object_type: str,
        from_ref: str,
        to_ref: str,
        primary_key: dict[str, Any],
        *,
        project_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Field-level diff of one object between two refs (``dolt_commit_diff_<table>``).

        Returns ``from_<col>`` / ``to_<col>`` / ``diff_type`` rows. ``dolt_commit_diff_``
        requires both ``from_commit`` and ``to_commit`` predicates; the object is
        matched on its primary key via ``COALESCE(to_<col>, from_<col>)`` so added,
        modified and removed versions are all captured.
        """
        table = self._resolve_table_name(object_type)
        diff_table = f"dolt_commit_diff_{table}"
        validate_sql_identifier(diff_table, kind="table")
        columns = [str(column) for column in primary_key]
        if not columns:
            raise ValueError("primary_key must not be empty.")
        for column in columns:
            validate_sql_identifier(column, kind="column")
        params: dict[str, Any] = {
            "from_ref": self._validate_commit_ref(from_ref),
            "to_ref": self._validate_commit_ref(to_ref),
        }
        clauses = ["from_commit = :from_ref", "to_commit = :to_ref"]
        for column in columns:
            clauses.append(
                f"COALESCE({quote_ident('to_' + column)}, {quote_ident('from_' + column)}) = :pk_{column}"
            )
            params[f"pk_{column}"] = primary_key[column]
        if project_key:
            clauses.append(
                f"COALESCE({quote_ident('to_projectKey')}, {quote_ident('from_projectKey')}) = :project_key"
            )
            params["project_key"] = project_key
        sql = f"SELECT * FROM {quote_ident(diff_table)} WHERE " + " AND ".join(clauses)
        with self.get_scenario_engine(branch_name).connect() as conn:
            rows = [dict(row) for row in conn.execute(_sql_text(sql), params).mappings().all()]
            conn.commit()
        return rows

    def _object_filter_clauses(
        self,
        primary_key: dict[str, Any],
        *,
        project_key: str | None,
        prefix: str,
        qualifier: str = "",
    ) -> tuple[list[str], dict[str, Any]]:
        """Build a parameterized WHERE for a single object (shared by the readers)."""
        columns = [str(column) for column in primary_key]
        for column in columns:
            validate_sql_identifier(column, kind="column")
        qualify = f"{qualifier}." if qualifier else ""
        clauses = [f"{qualify}{quote_ident(column)} = :{prefix}{column}" for column in columns]
        params: dict[str, Any] = {f"{prefix}{column}": primary_key[column] for column in columns}
        if project_key:
            clauses.append(f"{qualify}{quote_ident('projectKey')} = :{prefix}__project_key")
            params[f"{prefix}__project_key"] = project_key
        return clauses, params

    def _validate_commit_ref(self, ref: str) -> str:
        raw = str(ref or "").strip()
        if not raw or not _COMMIT_REF_RE.match(raw):
            raise ValueError(f"Invalid commit/timestamp reference: {ref!r}")
        return raw

    def _commit_ref_literal(self, ref: str) -> str:
        return "'" + self._validate_commit_ref(ref) + "'"

    def apply_update_milestone_date_batch(
        self,
        branch_name: str,
        normalized_items: list[dict[str, Any]],
        *,
        project_key: str | None = None,
    ) -> dict[str, Any]:
        with self.get_scenario_engine(branch_name).connect() as conn:
            try:
                for item in normalized_items:
                    column = str(item["dateField"])
                    validate_sql_identifier(column, kind="column")
                    params = {
                        "new_date": item["newDate"],
                        "row_key": item["rowKey"],
                    }
                    sql = f"UPDATE `{DELIVERY_PLAN_ROW_TABLE}` SET `{column}` = :new_date WHERE `rowKey` = :row_key"
                    if project_key:
                        sql += " AND `projectKey` = :project_key"
                        params["project_key"] = project_key
                    conn.execute(_sql_text(sql), params)
                conn.commit()
                self._call_commit_allow_empty(conn, f"Apply UpdateMilestoneDate on preview branch {branch_name}")
                conn.commit()
            except Exception:
                self._rollback_quietly(conn)
                self._reset_working_set(conn)
                conn.commit()
                raise
        return {
            "success": True,
            "actionName": "UpdateMilestoneDate",
            "appliedCount": len(normalized_items),
            "previewBranchId": branch_name,
            "results": [{**item, "data": {}} for item in normalized_items],
        }

    def apply_object_update(
        self,
        branch_name: str,
        object_type: str,
        primary_key: dict[str, Any],
        changes: dict[str, Any],
        *,
        author: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Generic Action writeback: UPDATE one object's changed columns by primary key.

        Uses ``UPDATE ... SET ... WHERE <pk>`` (not an upsert) so partial-column edits
        work on tables with NOT NULL columns — an upsert's INSERT arm fails strict-mode
        when non-supplied NOT NULL columns lack defaults. This matches the milestone
        writeback and the Action semantic of editing an existing object. The caller
        supplies the primary key (it knows the ObjectType schema).
        """
        table = self._resolve_table_name(object_type)
        primary_key_columns = [str(column) for column in primary_key]
        if not primary_key_columns:
            raise ValueError("primary_key must not be empty.")
        if not changes:
            raise ValueError("changes must not be empty.")
        change_columns = [str(column) for column in changes]
        for column in change_columns + primary_key_columns:
            validate_sql_identifier(column, kind="column")

        set_clause = ", ".join(f"{quote_ident(column)} = :set_{column}" for column in change_columns)
        where_clause = " AND ".join(f"{quote_ident(column)} = :pk_{column}" for column in primary_key_columns)
        sql = f"UPDATE {quote_ident(table)} SET {set_clause} WHERE {where_clause}"
        params: dict[str, Any] = {f"set_{column}": changes[column] for column in change_columns}
        params.update({f"pk_{column}": primary_key[column] for column in primary_key_columns})

        with self.get_scenario_engine(branch_name).connect() as conn:
            try:
                result = conn.execute(_sql_text(sql), params)
                conn.commit()
                commit_message = message or f"Apply {object_type} update on branch {branch_name}"
                self._call_commit_allow_empty(conn, commit_message, author=author)
                conn.commit()
            except Exception:
                self._rollback_quietly(conn)
                self._reset_working_set(conn)
                conn.commit()
                raise
        matched = getattr(result, "rowcount", None)
        return {
            "success": True,
            "objectType": object_type,
            "tableName": table,
            "primaryKey": dict(primary_key),
            "appliedColumns": sorted(change_columns),
            "matchedRows": matched if isinstance(matched, int) and matched >= 0 else None,
            "branch": branch_name,
        }

    def ingest_simulation_csv(self, branch_name: str, csv_file_path: str, target_table: str) -> dict[str, Any]:
        branch = self._validate_scenario_branch(branch_name)
        csv_path = Path(str(csv_file_path))
        if not csv_path.exists():
            raise FileNotFoundError(f"Simulation CSV not found: {csv_path}")
        table = self._resolve_table_name(target_table)

        with self.get_scenario_engine(branch).connect() as conn:
            before_hash = self._head_hash(conn)
            rows_written = 0
            try:
                primary_keys = self._fetch_primary_keys(conn, table)
                if not primary_keys:
                    raise ValueError(f"Target table `{table}` must define a primary key for scenario upsert.")
                for chunk in self._iter_csv_chunks(csv_path):
                    if not chunk:
                        continue
                    conn.execute(_sql_text(self._build_upsert_sql(table, chunk[0].keys(), primary_keys)), chunk)
                    rows_written += len(chunk)
                conn.commit()
                self._call_commit_allow_empty(conn, f"Ingest simulation CSV into {table} on {branch}")
                conn.commit()
            except Exception:
                self._rollback_quietly(conn)
                conn.execute(_sql_text("CALL dolt_reset('--hard', :target_hash)"), {"target_hash": before_hash})
                conn.commit()
                raise
        return {"previewBranchId": branch, "tableName": table, "rowsWritten": rows_written, "status": "INGESTED"}

    def ensure_ingest_branch(self) -> str:
        """Create the reserved pipeline ingest branch from main if it does not exist."""
        branch = self.ingest_branch
        with self.get_main_engine().connect() as conn:
            if not self._branch_exists(conn, branch):
                conn.execute(_sql_text("CALL dolt_branch(:branch)"), {"branch": branch})
                conn.commit()
        return branch

    def ingest_and_merge(
        self,
        target_table: str,
        rows: Iterable[dict[str, Any]],
        *,
        columns: Iterable[str] | None = None,
        primary_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        """Foundry-style writeback overlay (Dolt-native).

        Pipeline rows are UPSERTed onto the reserved ``ingest`` branch, then merged
        into ``main`` with ``dolt_conflicts_resolve('--ours')`` so that main-side
        (user / Action) edits always win. This keeps pipeline re-runs from clobbering
        edits while still flowing in non-conflicting pipeline updates. No
        ``dolt_checkout`` is used — each branch is reached via its own engine.
        """
        table = self._resolve_table_name(target_table)
        materialized = [dict(row) for row in (rows or [])]
        column_list = [str(column) for column in columns] if columns is not None else None
        if column_list is not None:
            for column in column_list:
                validate_sql_identifier(column, kind="column")
            materialized = [{column: row.get(column, "") for column in column_list} for row in materialized]

        branch = self.ensure_ingest_branch()
        rows_written = 0
        with self.get_scenario_engine(branch).connect() as conn:
            before_hash = self._head_hash(conn)
            try:
                keys = primary_keys or self._fetch_primary_keys(conn, table)
                if not keys:
                    raise ValueError(f"Target table `{table}` must define a primary key for pipeline ingest.")
                for chunk in _chunked(materialized, self.ingest_chunk_size):
                    if not chunk:
                        continue
                    conn.execute(_sql_text(self._build_upsert_sql(table, chunk[0].keys(), keys)), chunk)
                    rows_written += len(chunk)
                conn.commit()
                self._call_commit_allow_empty(conn, f"Pipeline ingest into {table} on {branch}")
                conn.commit()
            except Exception:
                self._rollback_quietly(conn)
                conn.execute(_sql_text("CALL dolt_reset('--hard', :target_hash)"), {"target_hash": before_hash})
                conn.commit()
                raise

        self._merge_ingest_to_main(branch, table)
        return {
            "ingestBranch": branch,
            "tableName": table,
            "rowsWritten": rows_written,
            "status": "MERGED",
            "targetBranch": self.main_branch,
        }

    def _merge_ingest_to_main(self, branch: str, table: str) -> None:
        with self.get_main_engine().connect() as conn:
            if not self._branch_exists(conn, branch):
                raise ScenarioBranchNotFoundError(f"Ingest branch not found: {branch}")
            try:
                conn.execute(_sql_text("CALL dolt_merge(:branch)"), {"branch": branch})
                self._resolve_conflicts_ours(conn, table)
                conn.commit()
                self._call_commit_allow_empty(
                    conn, f"Merge pipeline branch {branch} into {self.main_branch} (retain edits, --ours)"
                )
                conn.commit()
            except Exception:
                self._rollback_quietly(conn)
                self._reset_working_set(conn)
                conn.commit()
                raise

    def _resolve_conflicts_ours(self, conn: Any, table: str) -> None:
        validate_sql_identifier(table, kind="table")
        try:
            conn.execute(_sql_text("CALL dolt_conflicts_resolve('--ours', :table)"), {"table": table})
        except Exception as exc:
            message = str(exc).lower()
            if "no conflict" in message or "nothing to" in message or "does not exist" in message:
                return
            raise

    def resolve_scenario(
        self,
        branch_name: str,
        accept: bool,
        *,
        is_env_simulation: bool = False,
    ) -> dict[str, Any]:
        branch = self._validate_scenario_branch(branch_name)
        try:
            if accept:
                if is_env_simulation:
                    raise ScenarioMergeRejectedError(
                        "Environment simulation branches contain hypothetical data and cannot be published to main."
                    )
                self._merge_to_main(branch)
                self._drop_branch(branch)
                return {"previewBranchId": branch, "status": "PUBLISHED", "targetBranch": self.main_branch}
            self._drop_branch(branch)
            return {"previewBranchId": branch, "status": "DISCARDED"}
        finally:
            self.dispose_scenario_engine(branch)
            self._base_hash_by_branch.pop(branch, None)

    def _merge_to_main(self, branch: str) -> None:
        with self.get_main_engine().connect() as conn:
            if not self._branch_exists(conn, branch):
                raise ScenarioBranchNotFoundError(f"Preview branch not found: {branch}")
            try:
                conn.execute(_sql_text("CALL dolt_merge(:branch)"), {"branch": branch})
                conn.commit()
                self._call_commit_allow_empty(conn, f"Publish preview branch {branch}")
                conn.commit()
            except Exception as exc:
                self._rollback_quietly(conn)
                self._reset_working_set(conn)
                conn.commit()
                message = str(exc)
                if "conflict" in message.lower() or "merge" in message.lower():
                    raise ScenarioMergeConflictError(message) from exc
                raise

    def _drop_branch(self, branch: str) -> None:
        with self.get_main_engine().connect() as conn:
            if not self._branch_exists(conn, branch):
                raise ScenarioBranchNotFoundError(f"Preview branch not found: {branch}")
            conn.execute(_sql_text("CALL dolt_branch('-D', :branch)"), {"branch": branch})
            conn.commit()

    def _branch_database_url(self, branch: str) -> str:
        if not self.database_url:
            raise ScenarioUnavailableError("DOLT_DATABASE_URL is required for scenario lifecycle operations.")
        lower = self.database_url.lower()
        if not (lower.startswith("mysql+pymysql://") or lower.startswith("mysql+mysqldb://")):
            raise ScenarioUnavailableError(
                "DOLT_DATABASE_URL must use a MySQL SQLAlchemy dialect such as mysql+pymysql://."
            )
        try:
            from sqlalchemy.engine import make_url
        except ImportError as exc:
            raise ScenarioUnavailableError("SQLAlchemy is required for scenario lifecycle operations.") from exc
        url = make_url(self.database_url)
        database = str(url.database or "").strip()
        if not database:
            raise ScenarioUnavailableError("DOLT_DATABASE_URL must include a database name.")
        base_database = database.split("/", 1)[0]
        return url.set(database=f"{base_database}/{branch}").render_as_string(hide_password=False)

    def _build_engine(self, url: str) -> Any:
        if self._engine_factory is not None:
            return self._engine_factory(
                url,
                future=True,
                pool_pre_ping=True,
            )
        try:
            import pymysql  # noqa: F401
            from sqlalchemy import create_engine
        except ImportError as exc:
            raise ScenarioUnavailableError("PyMySQL and SQLAlchemy are required for scenario lifecycle operations.") from exc
        pool_size = int(os.getenv("DOLT_SCENARIO_POOL_SIZE") or "5")
        max_overflow = int(os.getenv("DOLT_SCENARIO_MAX_OVERFLOW") or "10")
        return create_engine(url, future=True, pool_pre_ping=True, pool_size=pool_size, max_overflow=max_overflow)

    def _evict_oldest_engine_if_needed(self) -> None:
        while len(self._engine_cache) > self.max_cached_engines:
            _branch, engine = self._engine_cache.popitem(last=False)
            if hasattr(engine, "dispose"):
                engine.dispose()

    def _iter_csv_chunks(self, csv_path: Path) -> Iterable[list[dict[str, Any]]]:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError(f"Simulation CSV has no header: {csv_path}")
            headers = [str(header).strip() for header in reader.fieldnames if str(header).strip()]
            for header in headers:
                validate_sql_identifier(header, kind="column")
            chunk: list[dict[str, Any]] = []
            for raw_row in reader:
                chunk.append({header: raw_row.get(header, "") for header in headers})
                if len(chunk) >= self.ingest_chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk

    def _build_upsert_sql(self, table: str, columns: Iterable[str], primary_keys: list[str]) -> str:
        column_names = [str(column) for column in columns]
        for column in column_names:
            validate_sql_identifier(column, kind="column")
        missing_keys = [key for key in primary_keys if key not in column_names]
        if missing_keys:
            raise ValueError(f"Simulation CSV is missing primary key column(s): {', '.join(missing_keys)}")
        column_sql = ", ".join(quote_ident(column) for column in column_names)
        values_sql = ", ".join(f":{column}" for column in column_names)
        update_columns = [column for column in column_names if column not in set(primary_keys)]
        if not update_columns:
            update_columns = column_names[:1]
        assignments = ", ".join(f"{quote_ident(column)} = VALUES({quote_ident(column)})" for column in update_columns)
        return f"INSERT INTO {quote_ident(table)} ({column_sql}) VALUES ({values_sql}) ON DUPLICATE KEY UPDATE {assignments}"

    def _fetch_primary_keys(self, conn: Any, table: str) -> list[str]:
        result = conn.execute(
            _sql_text(
                """
                SELECT COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                  AND CONSTRAINT_NAME = 'PRIMARY'
                ORDER BY ORDINAL_POSITION
                """
            ),
            {"table_name": table},
        )
        return [str(row.get("COLUMN_NAME")) for row in _result_mappings(result) if row.get("COLUMN_NAME") is not None]

    def _resolve_table_name(self, target_table: str) -> str:
        target = str(target_table or "").strip()
        if not target:
            raise ValueError("target_table is required.")
        object_types = _load_object_types()
        if target in object_types and isinstance(object_types[target], dict):
            return object_type_table_name(target, object_types[target])
        validate_sql_identifier(target, kind="table")
        return target

    def _branch_exists(self, conn: Any, branch: str) -> bool:
        row = conn.execute(
            _sql_text("SELECT 1 AS ok FROM dolt_branches WHERE name = :name LIMIT 1"),
            {"name": branch},
        ).first()
        return row is not None

    def _head_hash(self, conn: Any) -> str:
        result = conn.execute(_sql_text("SELECT HASHOF('HEAD') AS head_hash"))
        first = result.first()
        if first is None:
            return ""
        if isinstance(first, dict):
            return str(first.get("head_hash") or first.get("HASHOF('HEAD')") or "")
        try:
            return str(first[0] or "")
        except Exception:
            return str(first)

    def _call_commit_allow_empty(self, conn: Any, message: str, *, author: str | None = None) -> None:
        params: dict[str, Any] = {"message": message[:500]}
        if author:
            sql = "CALL dolt_commit('-A', '-m', :message, '--author', :author)"
            params["author"] = str(author)[:200]
        else:
            sql = "CALL dolt_commit('-A', '-m', :message)"
        try:
            conn.execute(_sql_text(sql), params)
        except Exception as exc:
            if "nothing to commit" not in str(exc).lower():
                raise

    def _reset_working_set(self, conn: Any) -> None:
        try:
            conn.execute(_sql_text("CALL dolt_reset('--hard')"))
        except Exception:
            return

    def _rollback_quietly(self, conn: Any) -> None:
        if hasattr(conn, "rollback"):
            try:
                conn.rollback()
            except Exception:
                return

    def _validate_branch_name(self, branch_name: str) -> str:
        branch = str(branch_name or "").strip()
        if not branch:
            raise ValueError("branch_name must not be empty.")
        if branch.upper() == "HEAD":
            raise ValueError("branch_name must not be HEAD.")
        if _HEX32_RE.match(branch):
            raise ValueError("branch_name must not look like a commit hash.")
        if not _BRANCH_RE.match(branch):
            raise ValueError(f"Invalid branch_name: {branch!r}.")
        return branch

    def _validate_scenario_branch(self, branch_name: str) -> str:
        branch = self._validate_branch_name(branch_name)
        if branch.lower() in _MAIN_ALIASES:
            raise ValueError("Scenario branch must be a non-main branch.")
        if branch in self.reserved_branches:
            raise ValueError(f"Branch `{branch}` is reserved and cannot be used as a scenario branch.")
        return branch


def _chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    step = max(1, int(size))
    for start in range(0, len(items), step):
        yield items[start : start + step]


def _load_object_types() -> dict[str, Any]:
    with OBJECT_TYPES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _result_mappings(result: Any) -> list[dict[str, Any]]:
    if hasattr(result, "mappings"):
        return [dict(row) for row in result.mappings().all()]
    rows = result.fetchall() if hasattr(result, "fetchall") else []
    return [dict(row) if isinstance(row, dict) else dict(enumerate(row)) for row in rows]


def _sql_text(sql: str) -> Any:
    try:
        from sqlalchemy import text
    except ImportError:
        return sql
    return text(sql)
