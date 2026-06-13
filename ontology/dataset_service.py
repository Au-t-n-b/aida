from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datasource_bindings import (
    object_types_with_backing_data,
    resolve_object_type_writable,
)
from dolt_schema_sync import (
    _call_checkout,
    _call_commit,
    _checkout_branch_enabled,
    _get_dolt_main_branch,
    _primary_key_fields,
    _resolve_engine,
    _sql_text,
    build_create_table_sql,
    object_type_table_name,
    quote_ident,
    to_snake_case,
    validate_sql_identifier,
)
from scenario_lifecycle_manager import ScenarioLifecycleManager


BASE_DIR = Path(__file__).parent
DEFAULT_REGISTRY_PATH = BASE_DIR / ".local" / "datasets" / "registry.json"
DEFAULT_STAGING_ROOT = BASE_DIR / ".local" / "datasets" / "staging"
DEFAULT_OBJECT_BACKING_FOLDER_RID = "ri.compass.main.folder.local_ontology"
SUPPORTED_OBJECT_BACKING_DATA = set(object_types_with_backing_data())
TRANSACTION_TYPES = {"APPEND", "UPDATE", "SNAPSHOT"}


def supported_object_backing_data() -> set[str]:
    return set(object_types_with_backing_data())


def _object_type_writable(object_type: str | None) -> bool:
    """Whether Action-driven edit transactions are allowed for this ObjectType.

    Generic (non-ontology) datasets and unknown object types default to writable;
    only ObjectTypes whose binding declares ``writable: false`` are read-only.
    Pipeline materialization (SNAPSHOT / ingest) bypasses this via ``_enforce_writable``.
    """
    if not object_type:
        return True
    writable = resolve_object_type_writable(str(object_type))
    return True if writable is None else bool(writable)


class DatasetError(RuntimeError):
    status_code = 400


class DatasetNotFoundError(DatasetError):
    status_code = 404


class DatasetConflictError(DatasetError):
    status_code = 409


class DatasetInvalidTransactionError(DatasetError):
    status_code = 400


class DatasetNotImplementedError(DatasetError):
    status_code = 501


class DatasetReadOnlyError(DatasetError):
    status_code = 403


class DatasetUnavailableError(DatasetError):
    status_code = 503


class LocalDatasetService:
    def __init__(
        self,
        *,
        registry_path: Path | None = None,
        staging_root: Path | None = None,
        engine: Any | None = None,
        scenario_manager: ScenarioLifecycleManager | None = None,
    ) -> None:
        self.registry_path = registry_path or Path(os.getenv("DATASET_REGISTRY_PATH") or DEFAULT_REGISTRY_PATH)
        self.staging_root = staging_root or Path(os.getenv("DATASET_STAGING_ROOT") or DEFAULT_STAGING_ROOT)
        self.engine = engine
        self.scenario_manager = scenario_manager

    def create_dataset(
        self,
        *,
        name: str,
        parent_folder_rid: str = "",
        object_type: str | None = None,
        object_types: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dataset_name = str(name or "").strip()
        if not dataset_name:
            raise ValueError("dataset.name is required.")
        parent_rid = str(parent_folder_rid or "").strip()
        object_type_name = str(object_type or "").strip() or None
        object_schema = None
        if object_type_name:
            object_schema = _require_object_type_schema(object_type_name, object_types or {})
            table_name = object_type_table_name(object_type_name, object_schema)
            primary_key = _primary_key_fields(object_schema)
            schema = _schema_columns_from_object_type(object_schema)
        else:
            table_name = _dataset_table_name(dataset_name)
            primary_key = []
            schema = []

        dataset_rid = _dataset_rid(dataset_name, parent_rid, object_type_name)
        registry = self._load_registry()
        existing = registry["datasets"].get(dataset_rid)
        if existing is None:
            existing = {
                "datasetRid": dataset_rid,
                "name": dataset_name,
                "parentFolderRid": parent_rid,
                "tableName": table_name,
                "objectType": object_type_name,
                "primaryKey": primary_key,
                "schema": schema,
                "createdTime": _utc_now(),
            }
            registry["datasets"][dataset_rid] = existing
            self._save_registry(registry)

        table_status = "pending_schema"
        if existing.get("schema"):
            table_status = self._try_ensure_table(existing)
        return {
            "datasetRid": dataset_rid,
            "name": existing["name"],
            "parentFolderRid": existing.get("parentFolderRid", ""),
            "tableName": existing["tableName"],
            "objectType": existing.get("objectType"),
            "primaryKey": list(existing.get("primaryKey") or []),
            "schema": list(existing.get("schema") or []),
            "status": "ok",
            "tableStatus": table_status,
        }

    def create_transaction(
        self,
        dataset_rid: str,
        transaction_type: str = "UPDATE",
        *,
        _enforce_writable: bool = True,
    ) -> dict[str, Any]:
        tx_type = str(transaction_type or "").strip().upper()
        if tx_type == "DELETE":
            raise DatasetNotImplementedError("DELETE transactions are not implemented.")
        if tx_type not in TRANSACTION_TYPES:
            raise ValueError(f"Unsupported transactionType `{transaction_type}`.")

        registry = self._load_registry()
        dataset = self._require_dataset(registry, dataset_rid)
        if _enforce_writable and not _object_type_writable(dataset.get("objectType")):
            raise DatasetReadOnlyError(
                f"ObjectType `{dataset.get('objectType')}` is read-only (template/reference data); "
                "edit transactions are not allowed. Pipeline updates must use the dolt mirror / ingest path."
            )
        for transaction in registry["transactions"].values():
            if transaction.get("datasetRid") == dataset_rid and transaction.get("status") == "OPEN":
                raise DatasetConflictError("OPEN transaction already exists for this dataset.")

        transaction_rid = f"ri.foundry.main.transaction.{uuid.uuid4().hex}"
        transaction = {
            "transactionRid": transaction_rid,
            "datasetRid": dataset_rid,
            "transactionType": tx_type,
            "status": "OPEN",
            "createdTime": _utc_now(),
            "stagedFiles": [],
        }
        registry["transactions"][transaction_rid] = transaction
        self._save_registry(registry)
        return _transaction_response(transaction)

    def upload_file(
        self,
        dataset_rid: str,
        transaction_rid: str,
        content: bytes,
        *,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        if not transaction_rid:
            raise ValueError("transactionRid query parameter is required.")
        registry = self._load_registry()
        self._require_dataset(registry, dataset_rid)
        transaction = self._require_transaction(registry, dataset_rid, transaction_rid)
        if transaction.get("status") != "OPEN":
            raise DatasetInvalidTransactionError("transaction must be OPEN to upload files.")

        staged_dir = self.staging_root / _safe_path_segment(dataset_rid) / _safe_path_segment(transaction_rid)
        staged_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_upload_file_name(file_name)
        staged_path = staged_dir / safe_name
        staged_path.write_bytes(content)
        staged_file = {
            "fileName": safe_name,
            "path": str(staged_path),
            "sizeBytes": len(content),
            "uploadedTime": _utc_now(),
        }
        transaction.setdefault("stagedFiles", []).append(staged_file)
        self._save_registry(registry)
        return {
            "datasetRid": dataset_rid,
            "transactionRid": transaction_rid,
            "fileName": safe_name,
            "sizeBytes": len(content),
            "status": "STAGED",
        }

    def commit_transaction(self, dataset_rid: str, transaction_rid: str) -> dict[str, Any]:
        registry = self._load_registry()
        dataset = self._require_dataset(registry, dataset_rid)
        transaction = self._require_transaction(registry, dataset_rid, transaction_rid)
        if transaction.get("status") != "OPEN":
            raise DatasetInvalidTransactionError("transaction must be OPEN to commit.")

        preview_context = _current_preview_branch_context()
        if preview_context is not None and not preview_context.is_main:
            return self._commit_transaction_to_preview_branch(registry, dataset, transaction, preview_context)

        rows = self._load_transaction_rows(dataset, transaction)
        if not dataset.get("schema"):
            self._infer_generic_schema(dataset, rows)
            registry["datasets"][dataset_rid] = dataset

        engine = self._require_engine()
        rows_written = 0
        with engine.connect() as conn:
            self._prepare_branch(conn)
            self._ensure_table(conn, dataset)
            if transaction.get("transactionType") == "SNAPSHOT":
                conn.execute(_sql_text(f"DELETE FROM {quote_ident(str(dataset['tableName']))}"))
            seen_primary_keys: set[tuple[str, ...]] = set()
            for row in rows:
                prepared = _filter_row_for_dataset(dataset, row)
                if not prepared:
                    continue
                self._validate_primary_key(dataset, prepared)
                if transaction.get("transactionType") == "APPEND":
                    self._ensure_append_primary_key_is_new(conn, dataset, prepared, seen_primary_keys)
                self._insert_row(
                    conn,
                    dataset,
                    prepared,
                    upsert=transaction.get("transactionType") == "UPDATE",
                )
                rows_written += 1
            conn.commit()
            _call_commit(conn, f"Commit dataset {dataset_rid} transaction {transaction_rid}")
            conn.commit()

        transaction["status"] = "COMMITTED"
        transaction["committedTime"] = _utc_now()
        transaction["rowsWritten"] = rows_written
        self._save_registry(registry)
        return {
            "datasetRid": dataset_rid,
            "transactionRid": transaction_rid,
            "transactionType": transaction.get("transactionType"),
            "status": "COMMITTED",
            "rowsWritten": rows_written,
            "tableName": dataset.get("tableName"),
        }

    def list_branches(self, dataset_rid: str) -> dict[str, Any]:
        registry = self._load_registry()
        self._require_dataset(registry, dataset_rid)
        manager = self._scenario_manager()
        with manager.get_main_engine().connect() as conn:
            rows = conn.execute(_sql_text("SELECT name, hash FROM dolt_branches ORDER BY name")).mappings().all()
            conn.commit()
        reserved = manager.reserved_branches
        return {
            "data": [
                {
                    "branchId": str(row.get("name") or ""),
                    "rid": _dataset_branch_rid(str(row.get("name") or "")),
                    "latestTransactionRid": str(row.get("hash") or ""),
                }
                for row in rows
                if str(row.get("name") or "") not in reserved
            ]
        }

    def get_branch(self, dataset_rid: str, branch_id: str) -> dict[str, Any]:
        for branch in self.list_branches(dataset_rid)["data"]:
            if branch.get("branchId") == branch_id:
                return branch
        raise DatasetNotFoundError(f"Dataset branch not found: {branch_id}")

    def create_branch(self, dataset_rid: str, branch_id: str, _payload: dict[str, Any] | None = None) -> dict[str, Any]:
        registry = self._load_registry()
        self._require_dataset(registry, dataset_rid)
        branch_name = self._scenario_manager().create_scenario(branch_id)
        return {
            "branchId": branch_name,
            "rid": _dataset_branch_rid(branch_name),
            "latestTransactionRid": "",
        }

    def delete_branch(self, dataset_rid: str, branch_id: str) -> None:
        registry = self._load_registry()
        self._require_dataset(registry, dataset_rid)
        self._scenario_manager().resolve_scenario(branch_id, accept=False)

    def read_table(self, dataset_rid: str, *, output_format: str = "json") -> dict[str, Any]:
        normalized_format = str(output_format or "json").strip().lower()
        if normalized_format not in {"json", "csv"}:
            raise ValueError("format must be json or csv.")
        registry = self._load_registry()
        dataset = self._require_dataset(registry, dataset_rid)
        engine = self._require_engine()
        columns = _dataset_column_names(dataset)
        select_columns = ", ".join(quote_ident(column) for column in columns) if columns else "*"
        with engine.connect() as conn:
            result = conn.execute(_sql_text(f"SELECT {select_columns} FROM {quote_ident(str(dataset['tableName']))}"))
        rows = _result_mappings(result)
        if normalized_format == "csv":
            return {
                "datasetRid": dataset_rid,
                "tableName": dataset.get("tableName"),
                "format": "csv",
                "content": _rows_to_csv(rows, columns),
                "total": len(rows),
            }
        return {
            "datasetRid": dataset_rid,
            "tableName": dataset.get("tableName"),
            "format": "json",
            "rows": rows,
            "total": len(rows),
        }

    def sync_object_type_backing_datasets(
        self,
        *,
        object_types: dict[str, Any],
        object_type_names: list[str] | None = None,
    ) -> dict[str, Any]:
        target_names = object_type_names or list(object_types.keys())
        items: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for object_type in target_names:
            try:
                object_schema = _require_object_type_schema(object_type, object_types)
                dataset = self.create_dataset(
                    name=object_type,
                    parent_folder_rid=DEFAULT_OBJECT_BACKING_FOLDER_RID,
                    object_type=object_type,
                    object_types=object_types,
                )
                if object_type not in supported_object_backing_data():
                    items.append(
                        {
                            "objectType": object_type,
                            "datasetRid": dataset["datasetRid"],
                            "tableName": dataset["tableName"],
                            "status": "skipped",
                            "rowsWritten": 0,
                            "reason": "No current CSV-backed object rows for this ObjectType.",
                        }
                    )
                    continue

                rows = _current_object_rows(object_type)
                if not rows:
                    items.append(
                        {
                            "objectType": object_type,
                            "datasetRid": dataset["datasetRid"],
                            "tableName": dataset["tableName"],
                            "status": "skipped",
                            "rowsWritten": 0,
                            "reason": "No rows returned by get_object_data().",
                        }
                    )
                    continue

                transaction = self.create_transaction(
                    dataset["datasetRid"], "UPDATE", _enforce_writable=False
                )
                csv_bytes = _serialize_object_rows(rows, object_schema)
                self.upload_file(
                    dataset["datasetRid"],
                    transaction["transactionRid"],
                    csv_bytes,
                    file_name=f"{object_type}.csv",
                )
                committed = self.commit_transaction(dataset["datasetRid"], transaction["transactionRid"])
                items.append(
                    {
                        "objectType": object_type,
                        "datasetRid": dataset["datasetRid"],
                        "tableName": dataset["tableName"],
                        "status": "ok",
                        "rowsWritten": committed["rowsWritten"],
                    }
                )
            except Exception as exc:
                error = {"objectType": object_type, "errors": [str(exc)]}
                errors.append(error)
                items.append(
                    {
                        "objectType": object_type,
                        "datasetRid": "",
                        "tableName": "",
                        "status": "error",
                        "rowsWritten": 0,
                        "errors": [str(exc)],
                    }
                )

        status = "error" if errors else "ok"
        return {"status": status, "items": items, "errors": errors}

    def _load_registry(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"version": 1, "datasets": {}, "transactions": {}}
        with self.registry_path.open("r", encoding="utf-8") as handle:
            registry = json.load(handle)
        registry.setdefault("datasets", {})
        registry.setdefault("transactions", {})
        return registry

    def _save_registry(self, registry: dict[str, Any]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.registry_path.open("w", encoding="utf-8") as handle:
            json.dump(registry, handle, ensure_ascii=False, indent=2)

    def _require_dataset(self, registry: dict[str, Any], dataset_rid: str) -> dict[str, Any]:
        dataset = registry.get("datasets", {}).get(dataset_rid)
        if dataset is None:
            raise DatasetNotFoundError(f"Dataset not found: {dataset_rid}")
        return dataset

    def _require_transaction(
        self,
        registry: dict[str, Any],
        dataset_rid: str,
        transaction_rid: str,
    ) -> dict[str, Any]:
        transaction = registry.get("transactions", {}).get(transaction_rid)
        if transaction is None or transaction.get("datasetRid") != dataset_rid:
            raise DatasetNotFoundError(f"Transaction not found: {transaction_rid}")
        return transaction

    def _require_engine(self) -> Any:
        try:
            engine = _resolve_engine(self.engine)
        except Exception as exc:
            raise DatasetUnavailableError(str(exc)) from exc
        if engine is None:
            raise DatasetUnavailableError("DOLT_DATABASE_URL is required for dataset table operations.")
        return engine

    def _scenario_manager(self) -> ScenarioLifecycleManager:
        if self.scenario_manager is None:
            self.scenario_manager = ScenarioLifecycleManager()
        return self.scenario_manager

    def _commit_transaction_to_preview_branch(
        self,
        registry: dict[str, Any],
        dataset: dict[str, Any],
        transaction: dict[str, Any],
        preview_context: Any,
    ) -> dict[str, Any]:
        if not dataset.get("schema"):
            rows = self._load_transaction_rows(dataset, transaction)
            self._infer_generic_schema(dataset, rows)
            registry["datasets"][str(dataset["datasetRid"])] = dataset

        rows_written = 0
        table_name = str(dataset["tableName"])
        for staged_file in transaction.get("stagedFiles") or []:
            path = Path(str(staged_file.get("path") or ""))
            if not path.exists():
                raise DatasetNotFoundError(f"Staged file not found: {path}")
            result = self._scenario_manager().ingest_simulation_csv(
                preview_context.dolt_branch,
                str(path),
                table_name,
            )
            rows_written += int(result.get("rowsWritten") or 0)

        transaction["status"] = "COMMITTED"
        transaction["committedTime"] = _utc_now()
        transaction["rowsWritten"] = rows_written
        self._save_registry(registry)
        return {
            "datasetRid": dataset["datasetRid"],
            "transactionRid": transaction["transactionRid"],
            "transactionType": transaction.get("transactionType"),
            "status": "COMMITTED",
            "rowsWritten": rows_written,
            "tableName": dataset.get("tableName"),
            "previewBranchId": preview_context.preview_branch_id,
        }

    def _try_ensure_table(self, dataset: dict[str, Any]) -> str:
        try:
            engine = _resolve_engine(self.engine)
        except Exception:
            return "skipped"
        if engine is None:
            return "skipped"
        with engine.connect() as conn:
            self._prepare_branch(conn)
            self._ensure_table(conn, dataset)
            conn.commit()
        return "ok"

    def _prepare_branch(self, conn: Any) -> None:
        if _checkout_branch_enabled():
            _call_checkout(conn, _get_dolt_main_branch())
            conn.commit()

    def _ensure_table(self, conn: Any, dataset: dict[str, Any]) -> None:
        object_type = dataset.get("objectType")
        if object_type:
            object_schema = _object_schema_from_dataset(dataset)
            conn.execute(_sql_text(build_create_table_sql(str(object_type), object_schema)))
            return
        columns = _dataset_column_names(dataset)
        if not columns:
            raise ValueError("Generic dataset schema is not inferred yet.")
        column_sql = ",\n  ".join(f"{quote_ident(column)} TEXT NULL" for column in columns)
        conn.execute(
            _sql_text(
                f"CREATE TABLE IF NOT EXISTS {quote_ident(str(dataset['tableName']))} (\n"
                f"  {column_sql}\n)"
            )
        )

    def _load_transaction_rows(self, dataset: dict[str, Any], transaction: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        object_columns = set(_dataset_column_names(dataset))
        generic_column_map: dict[str, str] = {}
        for staged_file in transaction.get("stagedFiles") or []:
            path = Path(str(staged_file.get("path") or ""))
            if not path.exists():
                raise DatasetNotFoundError(f"Staged file not found: {path}")
            text = path.read_text(encoding="utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            if reader.fieldnames is None:
                continue
            if dataset.get("objectType"):
                headers = [header for header in reader.fieldnames if header in object_columns]
                for raw_row in reader:
                    rows.append({header: raw_row.get(header, "") for header in headers})
            else:
                if not generic_column_map:
                    generic_column_map = _generic_column_map(reader.fieldnames)
                for raw_row in reader:
                    rows.append(
                        {
                            generic_column_map[header]: raw_row.get(header, "")
                            for header in reader.fieldnames
                            if header in generic_column_map
                        }
                    )
        return rows

    def _infer_generic_schema(self, dataset: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        columns: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for column in row.keys():
                if column not in seen:
                    validate_sql_identifier(column, kind="column")
                    seen.add(column)
                    columns.append(column)
        if not columns:
            raise ValueError("Cannot infer dataset schema from an empty CSV upload.")
        dataset["schema"] = [{"name": column, "dataType": {"type": "string"}} for column in columns]

    def _validate_primary_key(self, dataset: dict[str, Any], row: dict[str, Any]) -> None:
        primary_key = list(dataset.get("primaryKey") or [])
        for column in primary_key:
            if str(row.get(column) or "").strip() == "":
                raise ValueError(f"Missing primary key column `{column}` for dataset {dataset.get('datasetRid')}.")

    def _ensure_append_primary_key_is_new(
        self,
        conn: Any,
        dataset: dict[str, Any],
        row: dict[str, Any],
        seen_primary_keys: set[tuple[str, ...]],
    ) -> None:
        primary_key = list(dataset.get("primaryKey") or [])
        if not primary_key:
            return
        key = tuple(str(row.get(column, "")) for column in primary_key)
        if key in seen_primary_keys:
            raise DatasetConflictError("APPEND transaction contains duplicate primary key.")
        seen_primary_keys.add(key)
        where_sql = " AND ".join(f"{quote_ident(column)} = :{column}" for column in primary_key)
        result = conn.execute(
            _sql_text(
                f"SELECT COUNT(*) AS existing_count FROM {quote_ident(str(dataset['tableName']))} WHERE {where_sql}"
            ),
            {column: row.get(column) for column in primary_key},
        )
        if _scalar_count(result) > 0:
            raise DatasetConflictError("APPEND transaction would duplicate an existing primary key.")

    def _insert_row(self, conn: Any, dataset: dict[str, Any], row: dict[str, Any], *, upsert: bool) -> None:
        columns = list(row.keys())
        for column in columns:
            validate_sql_identifier(column, kind="column")
        table_name = str(dataset["tableName"])
        column_sql = ", ".join(quote_ident(column) for column in columns)
        values_sql = ", ".join(f":{column}" for column in columns)
        sql = f"INSERT INTO {quote_ident(table_name)} ({column_sql}) VALUES ({values_sql})"
        primary_key = set(dataset.get("primaryKey") or [])
        if upsert and primary_key:
            update_columns = [column for column in columns if column not in primary_key]
            if not update_columns:
                update_columns = columns[:1]
            assignments = ", ".join(f"{quote_ident(column)} = VALUES({quote_ident(column)})" for column in update_columns)
            sql = f"{sql} ON DUPLICATE KEY UPDATE {assignments}"
        conn.execute(_sql_text(sql), row)


_default_service: LocalDatasetService | None = None


def get_default_dataset_service() -> LocalDatasetService:
    global _default_service
    if _default_service is None:
        _default_service = LocalDatasetService()
    return _default_service


def create_dataset(
    *,
    name: str,
    parent_folder_rid: str = "",
    object_type: str | None = None,
    object_types: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return get_default_dataset_service().create_dataset(
        name=name,
        parent_folder_rid=parent_folder_rid,
        object_type=object_type,
        object_types=object_types,
    )


def create_dataset_transaction(dataset_rid: str, transaction_type: str = "UPDATE") -> dict[str, Any]:
    return get_default_dataset_service().create_transaction(dataset_rid, transaction_type)


def upload_dataset_file(
    dataset_rid: str,
    transaction_rid: str,
    content: bytes,
    *,
    file_name: str | None = None,
) -> dict[str, Any]:
    return get_default_dataset_service().upload_file(dataset_rid, transaction_rid, content, file_name=file_name)


def commit_dataset_transaction(dataset_rid: str, transaction_rid: str) -> dict[str, Any]:
    return get_default_dataset_service().commit_transaction(dataset_rid, transaction_rid)


def read_dataset_table(dataset_rid: str, *, output_format: str = "json") -> dict[str, Any]:
    return get_default_dataset_service().read_table(dataset_rid, output_format=output_format)


def list_dataset_branches(dataset_rid: str) -> dict[str, Any]:
    return get_default_dataset_service().list_branches(dataset_rid)


def get_dataset_branch(dataset_rid: str, branch_id: str) -> dict[str, Any]:
    return get_default_dataset_service().get_branch(dataset_rid, branch_id)


def create_dataset_branch(dataset_rid: str, branch_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_default_dataset_service().create_branch(dataset_rid, branch_id, payload)


def delete_dataset_branch(dataset_rid: str, branch_id: str) -> None:
    get_default_dataset_service().delete_branch(dataset_rid, branch_id)


def sync_object_type_backing_datasets(
    *,
    object_types: dict[str, Any],
    object_type_names: list[str] | None = None,
) -> dict[str, Any]:
    return get_default_dataset_service().sync_object_type_backing_datasets(
        object_types=object_types,
        object_type_names=object_type_names,
    )


def _dataset_rid(name: str, parent_folder_rid: str, object_type: str | None) -> str:
    digest = hashlib.sha256(f"{parent_folder_rid}\0{name}\0{object_type or ''}".encode("utf-8")).hexdigest()[:20]
    return f"ri.foundry.main.dataset.{digest}"


def _dataset_table_name(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    ascii_name = re.sub(r"[^a-zA-Z0-9_]+", "_", to_snake_case(name)).strip("_").lower()
    if not ascii_name or not re.match(r"^[a-zA-Z_]", ascii_name):
        ascii_name = f"dataset_{digest}"
    if len(ascii_name) > 63:
        ascii_name = f"{ascii_name[:48].rstrip('_')}_{digest}"
    validate_sql_identifier(ascii_name, kind="table")
    return ascii_name


def _schema_columns_from_object_type(object_schema: dict[str, Any]) -> list[dict[str, Any]]:
    properties = object_schema.get("properties") or {}
    if not isinstance(properties, dict):
        return []
    columns: list[dict[str, Any]] = []
    for fallback_name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            continue
        name = str(property_schema.get("apiName") or fallback_name).strip()
        validate_sql_identifier(name, kind="column")
        columns.append(
            {
                "name": name,
                "dataType": property_schema.get("dataType") or {"type": "string"},
                "required": bool(property_schema.get("required", False)),
            }
        )
    return columns


def _object_schema_from_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, dict[str, Any]] = {}
    for column in dataset.get("schema") or []:
        name = str(column.get("name") or "").strip()
        validate_sql_identifier(name, kind="column")
        properties[name] = {
            "apiName": name,
            "dataType": column.get("dataType") or {"type": "string"},
            "required": bool(column.get("required", False)),
        }
    return {
        "apiName": dataset.get("objectType") or dataset.get("name") or "",
        "primaryKeyPropertyApiNames": list(dataset.get("primaryKey") or []),
        "properties": properties,
    }


def _require_object_type_schema(object_type: str, object_types: dict[str, Any]) -> dict[str, Any]:
    object_schema = object_types.get(object_type)
    if not isinstance(object_schema, dict):
        raise DatasetNotFoundError(f"ObjectType not found: {object_type}")
    return object_schema


def _dataset_column_names(dataset: dict[str, Any]) -> list[str]:
    columns: list[str] = []
    for column in dataset.get("schema") or []:
        name = str(column.get("name") or "").strip()
        if name:
            validate_sql_identifier(name, kind="column")
            columns.append(name)
    return columns


def _filter_row_for_dataset(dataset: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    allowed = set(_dataset_column_names(dataset))
    if not allowed:
        return dict(row)
    return {key: value for key, value in row.items() if key in allowed}


def _result_mappings(result: Any) -> list[dict[str, Any]]:
    if hasattr(result, "mappings"):
        return [dict(row) for row in result.mappings().all()]
    rows = result.fetchall() if hasattr(result, "fetchall") else []
    return [dict(row) if isinstance(row, dict) else dict(enumerate(row)) for row in rows]


def _rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    output = io.StringIO()
    headers = columns or _union_row_keys(rows)
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _union_row_keys(rows: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def _serialize_object_rows(rows: list[dict[str, Any]], object_schema: dict[str, Any]) -> bytes:
    columns = [column["name"] for column in _schema_columns_from_object_type(object_schema)]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return output.getvalue().encode("utf-8-sig")


def _current_object_rows(object_type: str) -> list[dict[str, Any]]:
    import data_connector

    return data_connector.get_object_data(object_type)


def _generic_column_map(fieldnames: list[str]) -> dict[str, str]:
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for index, header in enumerate(fieldnames, start=1):
        base = re.sub(r"[^a-zA-Z0-9_]+", "_", to_snake_case(str(header or ""))).strip("_").lower()
        if not base or not re.match(r"^[a-zA-Z_]", base):
            base = f"column_{index}"
        candidate = base[:63]
        suffix = 2
        while candidate in used:
            tail = f"_{suffix}"
            candidate = f"{base[:63 - len(tail)]}{tail}"
            suffix += 1
        validate_sql_identifier(candidate, kind="column")
        used.add(candidate)
        mapping[header] = candidate
    return mapping


def _safe_upload_file_name(file_name: str | None) -> str:
    raw = str(file_name or "upload.csv").replace("\\", "/").split("/")[-1].strip()
    if not raw:
        raw = "upload.csv"
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", raw)
    return safe[:120] or "upload.csv"


def _safe_path_segment(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)


def _transaction_response(transaction: dict[str, Any]) -> dict[str, Any]:
    return {
        "datasetRid": transaction.get("datasetRid"),
        "transactionRid": transaction.get("transactionRid"),
        "transactionType": transaction.get("transactionType"),
        "status": transaction.get("status"),
        "createdTime": transaction.get("createdTime"),
    }


def _scalar_count(result: Any) -> int:
    first = result.first() if hasattr(result, "first") else None
    if first is None:
        return 0
    if isinstance(first, dict):
        return int(first.get("existing_count") or 0)
    try:
        return int(first[0])
    except Exception:
        return int(first or 0)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _current_preview_branch_context() -> Any | None:
    try:
        from preview_branch import get_current_preview_branch
    except Exception:
        return None
    return get_current_preview_branch()


def _dataset_branch_rid(branch_id: str) -> str:
    safe = _safe_path_segment(branch_id or "main")
    return f"ri.foundry.main.branch.{safe}"
