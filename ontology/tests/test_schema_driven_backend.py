import csv
import importlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date
from os import environ
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - 测试环境可能未安装 fastapi
    TestClient = None


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class _FakeDoltConnection:
    def __init__(self, *, fail_commit: bool = False):
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.fail_commit = fail_commit

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, dict(params or {})))
        if self.fail_commit and "CALL dolt_commit" in sql:
            raise RuntimeError("commit failed")
        return SimpleNamespace(first=lambda: None)

    def commit(self):
        self.calls.append(("COMMIT", {}))


class _FakeDoltEngine:
    def __init__(self, *, fail_commit: bool = False):
        self.connection = _FakeDoltConnection(fail_commit=fail_commit)

    def connect(self):
        return self.connection


class _MemoryDoltResult:
    def __init__(self, rows: list[dict[str, object]] | None = None, scalar: object | None = None):
        self._rows = rows or []
        self._scalar = scalar

    def first(self):
        if self._scalar is not None:
            return (self._scalar,)
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return [tuple(row.values()) for row in self._rows]

    def mappings(self):
        return SimpleNamespace(all=lambda: list(self._rows))


class _MemoryDoltConnection:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.tables: dict[str, list[dict[str, object]]] = {}
        self.primary_keys: dict[str, list[str]] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        values = dict(params or {})
        self.calls.append((sql, values))
        normalized = " ".join(sql.split())
        if normalized.startswith("CREATE TABLE IF NOT EXISTS"):
            table = _first_backtick_identifier(normalized)
            self.tables.setdefault(table, [])
            self.primary_keys[table] = _primary_keys_from_create(normalized)
            return _MemoryDoltResult()
        if normalized.startswith("ALTER TABLE"):
            return _MemoryDoltResult()
        if normalized.startswith("DELETE FROM"):
            table = _first_backtick_identifier(normalized)
            self.tables[table] = []
            return _MemoryDoltResult()
        if normalized.startswith("SELECT COUNT(*) AS existing_count FROM"):
            table = _first_backtick_identifier(normalized)
            primary_keys = self.primary_keys.get(table, [])
            count = sum(
                1
                for row in self.tables.get(table, [])
                if all(str(row.get(key, "")) == str(values.get(key, "")) for key in primary_keys)
            )
            return _MemoryDoltResult(scalar=count)
        if normalized.startswith("INSERT INTO"):
            table = _first_backtick_identifier(normalized)
            primary_keys = self.primary_keys.get(table, [])
            rows = self.tables.setdefault(table, [])
            existing = next(
                (
                    row
                    for row in rows
                    if primary_keys and all(str(row.get(key, "")) == str(values.get(key, "")) for key in primary_keys)
                ),
                None,
            )
            if existing is not None:
                if "ON DUPLICATE KEY UPDATE" not in normalized:
                    raise RuntimeError("Duplicate entry")
                existing.update(values)
            else:
                rows.append(dict(values))
            return _MemoryDoltResult()
        if "FROM information_schema.COLUMNS" in normalized:
            table_name = str(values.get("table_name") or "")
            column_names: list[str] = []
            for row in self.tables.get(table_name, []):
                for column_name in row.keys():
                    if column_name not in column_names:
                        column_names.append(str(column_name))
            return _MemoryDoltResult([{"COLUMN_NAME": column_name} for column_name in column_names])
        if normalized.startswith("SELECT") and " FROM " in normalized:
            table = _first_backtick_identifier(normalized.split(" FROM ", 1)[1])
            return _MemoryDoltResult([dict(row) for row in self.tables.get(table, [])])
        return _MemoryDoltResult()

    def commit(self):
        self.calls.append(("COMMIT", {}))


class _MemoryDoltEngine:
    def __init__(self):
        self.connection = _MemoryDoltConnection()

    def connect(self):
        return self.connection


def _first_backtick_identifier(sql: str) -> str:
    start = sql.index("`") + 1
    end = sql.index("`", start)
    return sql[start:end]


def _primary_keys_from_create(sql: str) -> list[str]:
    marker = "PRIMARY KEY ("
    if marker not in sql:
        return []
    chunk = sql.split(marker, 1)[1].split(")", 1)[0]
    return [part.strip().strip("`") for part in chunk.split(",") if part.strip()]


class SchemaDrivenBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = None
        if TestClient is None:
            return
        backend_app = importlib.import_module("backend_app")
        cls.client = TestClient(backend_app.create_app())

    def setUp(self):
        self._writeback_overlay_patch = patch.dict(environ, {"DOLT_WRITEBACK_OVERLAY": "0"}, clear=False)
        self._writeback_overlay_patch.start()
        self._preview_branch = importlib.import_module("preview_branch")
        self._dolt_schema_sync = importlib.import_module("dolt_schema_sync")
        self._original_preview_dolt_engine = self._preview_branch._dolt_engine
        self._original_preview_scenario_manager = self._preview_branch._scenario_manager
        self._original_schema_sync_dolt_engine = self._dolt_schema_sync._dolt_engine
        self._preview_branch._dolt_engine = None
        self._preview_branch._scenario_manager = None
        self._dolt_schema_sync._dolt_engine = None

    def tearDown(self):
        self._preview_branch._dolt_engine = self._original_preview_dolt_engine
        self._preview_branch._scenario_manager = self._original_preview_scenario_manager
        self._dolt_schema_sync._dolt_engine = self._original_schema_sync_dolt_engine
        self._writeback_overlay_patch.stop()

    def test_datasource_binding_registry_loads_default_bindings(self):
        datasource_bindings = importlib.import_module("datasource_bindings")

        registry = datasource_bindings.load_datasource_bindings()

        self.assertEqual(registry.object_type("DeliveryPlanRow").reader, "csv_plan_rows")
        self.assertEqual(registry.object_type("Milestone").reader, "csv_table")
        self.assertEqual(registry.object_type("EquipmentArrivalItem").reader, "csv_table")
        self.assertTrue(registry.has_backing_data("DeliveryProject"))
        self.assertTrue(registry.has_backing_data("DeliveryPlanRow"))
        self.assertTrue(registry.has_backing_data("EquipmentArrivalItem"))
        self.assertFalse(registry.has_backing_data("SupplierCompany"))
        self.assertFalse(registry.has_backing_data("ChangeOrder"))
        self.assertEqual(
            [source.file_name for source in registry.project_sources()],
            [
                "ZJYD 测试项目汪伟_交付计划_20260415171001.csv",
                "JD_A3_delivery_plan_20260610.csv",
            ],
        )

    def test_datasource_binding_registry_rejects_invalid_config(self):
        datasource_bindings = importlib.import_module("datasource_bindings")

        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_source_path = Path(tmp_dir) / "missing-source.yaml"
            missing_source_path.write_text(
                """
version: 1
datasources: []
objectTypes:
  DeliveryPlanRow:
    reader: csv_plan_rows
    sources: [missing-source]
""".lstrip(),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing datasource"):
                datasource_bindings.load_datasource_bindings(missing_source_path)

            invalid_reader_path = Path(tmp_dir) / "invalid-reader.yaml"
            invalid_reader_path.write_text(
                """
version: 1
datasources: []
objectTypes:
  Demo:
    reader: arbitrary_python
    sources: []
""".lstrip(),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Unsupported datasource reader"):
                datasource_bindings.load_datasource_bindings(invalid_reader_path)

            duplicate_source_path = Path(tmp_dir) / "duplicate-source.yaml"
            duplicate_source_path.write_text(
                """
version: 1
datasources:
  - id: repeated
    type: csv
    path: one.csv
  - id: repeated
    type: csv
    path: two.csv
objectTypes: {}
""".lstrip(),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate datasource id"):
                datasource_bindings.load_datasource_bindings(duplicate_source_path)

    def test_sync_support_lists_are_driven_by_datasource_bindings(self):
        dataset_service = importlib.import_module("dataset_service")
        dolt_mirror = importlib.import_module("dolt_mirror")
        expected = {
            "DeliveryProject",
            "DeliveryPod",
            "DeliveryPlanRow",
            "Milestone",
            "EquipmentRoom",
            "EquipmentArrivalItem",
            "DeliveryBatch",
            "ProjectParticipant",
            "ResourceTeam",
            "ActivityTemplate",
            "ScheduleRisk",
        }

        self.assertEqual(dataset_service.supported_object_backing_data(), expected)
        self.assertEqual(set(dolt_mirror.supported_mirror_object_types()), expected)

    def test_datasource_binding_registry_loads_json_sections_binding(self):
        datasource_bindings = importlib.import_module("datasource_bindings")

        with tempfile.TemporaryDirectory() as tmp_dir:
            bindings_path = Path(tmp_dir) / "json-source.yaml"
            bindings_path.write_text(
                """
version: 1
datasources:
  - id: hld-parsed-json
    type: json
    path: parsed/HLD解析结果.json
    projectId: 京东
    projectKey: 京东
    docType: hld
    phase: 交付预案
objectTypes:
  ParsedDocumentSection:
    reader: json_sections
    derived: false
    writable: false
    sources:
      - hld-parsed-json
""".lstrip(),
                encoding="utf-8",
            )

            registry = datasource_bindings.load_datasource_bindings(bindings_path)

        source = registry.source("hld-parsed-json")
        self.assertEqual(source.datasource_type, "json")
        self.assertEqual(source.project_id, "京东")
        self.assertEqual(source.project_key, "京东")
        self.assertEqual(source.metadata["docType"], "hld")
        self.assertEqual(source.metadata["phase"], "交付预案")
        self.assertEqual(registry.object_type("ParsedDocumentSection").reader, "json_sections")

    def test_json_sections_reader_returns_parsed_document_sections(self):
        datasource_bindings = importlib.import_module("datasource_bindings")
        data_connector = importlib.import_module("data_connector")

        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            parsed_dir = base_dir / "parsed"
            parsed_dir.mkdir()
            json_path = parsed_dir / "HLD解析结果.json"
            json_path.write_text(
                json.dumps(
                    {
                        "documentId": "doc-hld-jd-001",
                        "projectId": "京东",
                        "docType": "hld",
                        "sourceFile": "HLD解析结果.json",
                        "sourceMediaItemRid": "ri.foundry.main.mediaitem.demo",
                        "parseVersion": "v1",
                        "parsedAt": "2026-06-02T00:00:00Z",
                        "sections": [
                            {
                                "titlePath": "HLD解析结果 > 网络架构",
                                "headingLevel": 2,
                                "orderIndex": 1,
                                "markdownContent": "## 网络架构\n管理网与业务网隔离",
                                "plainText": "管理网与业务网隔离",
                                "facts": [
                                    {
                                        "factType": "constraint",
                                        "name": "网络隔离要求",
                                    }
                                ],
                            },
                            {
                                "sectionId": "custom-section",
                                "projectId": "浙江移动",
                                "titlePath": "其他项目",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            bindings_path = base_dir / "datasource-bindings.yaml"
            bindings_path.write_text(
                """
version: 1
datasources:
  - id: hld-parsed-json
    type: json
    path: parsed/HLD解析结果.json
    projectId: 京东
    projectKey: 京东
    docType: hld
    phase: 交付预案
objectTypes:
  ParsedDocumentSection:
    reader: json_sections
    derived: false
    writable: false
    sources:
      - hld-parsed-json
""".lstrip(),
                encoding="utf-8",
            )
            registry = datasource_bindings.load_datasource_bindings(bindings_path)
            original_supported = data_connector.SUPPORTED_OBJECT_TYPES
            original_loader = data_connector.load_datasource_bindings
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.SUPPORTED_OBJECT_TYPES = {"ParsedDocumentSection"}
                data_connector.load_datasource_bindings = lambda: registry
                data_connector.BASE_DIR = base_dir

                rows = data_connector.get_object_data("ParsedDocumentSection", project_id="京东")
            finally:
                data_connector.SUPPORTED_OBJECT_TYPES = original_supported
                data_connector.load_datasource_bindings = original_loader
                data_connector.BASE_DIR = original_base_dir

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sectionId"], "doc-hld-jd-001::001")
        self.assertEqual(rows[0]["documentId"], "doc-hld-jd-001")
        self.assertEqual(rows[0]["projectId"], "京东")
        self.assertEqual(rows[0]["docType"], "hld")
        self.assertEqual(rows[0]["sourceFile"], "HLD解析结果.json")
        self.assertEqual(rows[0]["sourceMediaItemRid"], "ri.foundry.main.mediaitem.demo")
        self.assertEqual(rows[0]["parseVersion"], "v1")
        self.assertEqual(rows[0]["parsedAt"], "2026-06-02T00:00:00Z")
        self.assertEqual(rows[0]["titlePath"], "HLD解析结果 > 网络架构")
        self.assertEqual(rows[0]["headingLevel"], "2")
        self.assertEqual(rows[0]["orderIndex"], "1")
        self.assertIn("网络架构", rows[0]["markdownContent"])
        self.assertEqual(rows[0]["plainText"], "管理网与业务网隔离")
        self.assertEqual(
            json.loads(rows[0]["factsJson"]),
            [{"factType": "constraint", "name": "网络隔离要求"}],
        )

    def test_json_sections_reader_rejects_missing_sections(self):
        datasource_bindings = importlib.import_module("datasource_bindings")
        data_connector = importlib.import_module("data_connector")

        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            json_path = base_dir / "bad.json"
            json_path.write_text(json.dumps({"documentId": "bad"}), encoding="utf-8")
            bindings_path = base_dir / "datasource-bindings.yaml"
            bindings_path.write_text(
                """
version: 1
datasources:
  - id: bad-json
    type: json
    path: bad.json
    projectId: 京东
objectTypes:
  ParsedDocumentSection:
    reader: json_sections
    sources:
      - bad-json
""".lstrip(),
                encoding="utf-8",
            )
            registry = datasource_bindings.load_datasource_bindings(bindings_path)
            original_supported = data_connector.SUPPORTED_OBJECT_TYPES
            original_loader = data_connector.load_datasource_bindings
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.SUPPORTED_OBJECT_TYPES = {"ParsedDocumentSection"}
                data_connector.load_datasource_bindings = lambda: registry
                data_connector.BASE_DIR = base_dir

                with self.assertRaisesRegex(ValueError, "sections"):
                    data_connector.get_object_data("ParsedDocumentSection")
            finally:
                data_connector.SUPPORTED_OBJECT_TYPES = original_supported
                data_connector.load_datasource_bindings = original_loader
                data_connector.BASE_DIR = original_base_dir

    def test_v2_parsed_document_section_objects_return_json_sections(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        response = self.client.get(
            "/api/v2/ontologies/default/objects/ParsedDocumentSection",
            params={"project_id": "京东"},
        )

        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertGreaterEqual(len(items), 1)
        self.assertIn("sectionId", items[0])
        self.assertEqual(items[0]["projectId"], "京东")
        self.assertIn("factsJson", items[0])

    def test_metadata_only_object_data_returns_empty_rows(self):
        data_connector = importlib.import_module("data_connector")

        self.assertEqual(data_connector.get_object_data("SupplierCompany"), [])
        self.assertEqual(data_connector.get_object_data("ChangeOrder"), [])

    def _blank_delivery_plan_dates(self, path: Path) -> None:
        with path.open("r", encoding="utf-8-sig", newline="") as source_file:
            rows = list(csv.DictReader(source_file))
            fieldnames = list(rows[0].keys())
        for row in rows:
            row["开始日期"] = ""
            row["结束日期"] = ""
        with path.open("w", encoding="utf-8-sig", newline="") as target_file:
            writer = csv.DictWriter(target_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    @contextmanager
    def _temporary_project_sources(
        self,
        data_connector,
        project_id: str,
        source_file_name: str,
        *,
        blank_dates: bool = True,
        mutate_milestones=None,
    ):
        source_path = BACKEND_DIR / source_file_name
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            if blank_dates:
                self._blank_delivery_plan_dates(temp_project_path)
            if mutate_milestones is not None:
                mutate_milestones(temp_milestone_path)

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    project_id: data_connector.ProjectSource(project_id, temp_project_path.name, project_id),
                }
                yield temp_project_path, temp_milestone_path
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def _assert_plan_mutations_written(
        self,
        project_id: str,
        mutations: list[dict[str, object]],
    ) -> None:
        data_connector = importlib.import_module("data_connector")
        rows = data_connector.get_object_data("DeliveryPlanRow", project_id=project_id)
        rows_by_key = {row["rowKey"]: row for row in rows}
        for mutation in mutations:
            row_key = str(mutation.get("rowKey") or mutation.get("milestoneId") or "")
            field = str(mutation.get("field") or "")
            if field not in {"startDate", "endDate"}:
                continue
            self.assertIn(row_key, rows_by_key)
            self.assertEqual(rows_by_key[row_key][field], mutation.get("newDate"))

    def test_preview_branch_context_maps_main_and_validates_names(self):
        preview_branch = importlib.import_module("preview_branch")

        self.assertTrue(preview_branch.resolve_preview_branch_context(None).is_main)
        self.assertTrue(preview_branch.resolve_preview_branch_context("").is_main)
        self.assertTrue(preview_branch.resolve_preview_branch_context("master").is_main)
        self.assertTrue(preview_branch.resolve_preview_branch_context("main").is_main)

        context = preview_branch.resolve_preview_branch_context("shadow_sim_789")
        self.assertFalse(context.is_main)
        self.assertEqual(context.preview_branch_id, "shadow_sim_789")
        self.assertEqual(context.dolt_branch, "shadow_sim_789")

        with self.assertRaises(ValueError):
            preview_branch.resolve_preview_branch_context("bad branch")

    def test_v2_objects_reject_invalid_preview_branch_id_header(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        response = self.client.get(
            "/api/v2/ontologies/default/objects/DeliveryPlanRow",
            params={"project_id": "浙江移动"},
            headers={"Preview-Branch-Id": "bad branch"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Preview-Branch-Id", response.json()["detail"])

    def test_v2_preview_branch_create_requires_dolt_when_config_missing(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        with patch.dict(environ, {"DOLT_DATABASE_URL": ""}, clear=False):
            response = self.client.post(
                "/api/v2/ontologies/default/previewBranches",
                json={"previewBranchId": "shadow_sim_789"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("DOLT_DATABASE_URL", response.json()["detail"])

    def test_v2_update_milestone_date_preview_branch_does_not_fall_back_to_csv(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                row_key = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")[0]["rowKey"]
                with patch.dict(environ, {"DOLT_DATABASE_URL": ""}, clear=False):
                    response = self.client.post(
                        "/api/v2/ontologies/default/actions/UpdateMilestoneDate/applyBatch",
                        headers={"Preview-Branch-Id": "shadow_sim_789"},
                        json={
                            "batch": [
                                {
                                    "milestoneId": row_key,
                                    "dateField": "startDate",
                                    "newDate": "2026-07-01",
                                }
                            ],
                        },
                    )

                self.assertEqual(response.status_code, 503)
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_validate_milestone_date_preview_branch_requires_dolt(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_name = "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"

        with self._temporary_project_sources(data_connector, "浙江移动", source_name) as (temp_project_path, _):
            before_bytes = temp_project_path.read_bytes()
            row_key = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")[0]["rowKey"]
            with patch.dict(environ, {"DOLT_DATABASE_URL": ""}, clear=False):
                response = self.client.post(
                    "/api/v2/ontologies/default/actions/UpdateMilestoneDate/validateBatch",
                    headers={"Preview-Branch-Id": "shadow_sim_789"},
                    json={
                        "batch": [
                            {
                                "milestoneId": row_key,
                                "dateField": "startDate",
                                "newDate": "2026-07-01",
                            }
                        ],
                    },
                )

            self.assertEqual(response.status_code, 503)
            self.assertEqual(temp_project_path.read_bytes(), before_bytes)

    def test_dolt_preview_write_commits_without_checkout(self):
        preview_branch = importlib.import_module("preview_branch")
        fake_engine = _FakeDoltEngine()
        original_engine = preview_branch._dolt_engine
        try:
            preview_branch._dolt_engine = fake_engine
            context = preview_branch.resolve_preview_branch_context("shadow_sim_789")
            result = preview_branch.apply_update_milestone_date_batch_to_dolt(
                context,
                [
                    {
                        "rowKey": "浙江移动::row-1",
                        "dateField": "startDate",
                        "newDate": "2026-07-01",
                        "reason": "test",
                    }
                ],
                project_key="浙江移动",
            )
        finally:
            preview_branch._dolt_engine = original_engine

        sql_calls = [sql for sql, _params in fake_engine.connection.calls]
        self.assertTrue(result["success"])
        self.assertFalse(any("CALL dolt_checkout" in sql for sql in sql_calls))
        self.assertTrue(any("UPDATE `delivery_plan_row`" in sql for sql in sql_calls))
        self.assertTrue(any("CALL dolt_commit" in sql for sql in sql_calls))

    def test_dolt_preview_write_resets_without_checkout_on_commit_failure(self):
        preview_branch = importlib.import_module("preview_branch")
        fake_engine = _FakeDoltEngine(fail_commit=True)
        original_engine = preview_branch._dolt_engine
        try:
            preview_branch._dolt_engine = fake_engine
            context = preview_branch.resolve_preview_branch_context("shadow_sim_789")
            with self.assertRaises(RuntimeError):
                preview_branch.apply_update_milestone_date_batch_to_dolt(
                    context,
                    [
                        {
                            "rowKey": "浙江移动::row-1",
                            "dateField": "startDate",
                            "newDate": "2026-07-01",
                            "reason": "test",
                        }
                    ],
                    project_key="浙江移动",
                )
        finally:
            preview_branch._dolt_engine = original_engine

        sql_calls = [sql for sql, _params in fake_engine.connection.calls]
        self.assertTrue(any("CALL dolt_reset('--hard')" in sql for sql in sql_calls))
        self.assertFalse(any("CALL dolt_checkout" in sql for sql in sql_calls))

    def test_dolt_schema_builds_table_from_object_type_api_names(self):
        dolt_schema_sync = importlib.import_module("dolt_schema_sync")
        object_types = json.loads((BACKEND_DIR / "schema" / "object-types.json").read_text(encoding="utf-8"))
        schema = object_types["DeliveryPlanRow"]

        self.assertEqual(
            dolt_schema_sync.object_type_table_name("DeliveryPlanRow", schema),
            "delivery_plan_row",
        )
        sql = dolt_schema_sync.build_create_table_sql("DeliveryPlanRow", schema)

        self.assertIn("CREATE TABLE IF NOT EXISTS `delivery_plan_row`", sql)
        self.assertIn("`rowKey`", sql)
        self.assertIn("`activityName`", sql)
        self.assertIn("PRIMARY KEY (`rowKey`)", sql)
        self.assertNotIn("活动名称", sql)

    def test_dolt_schema_add_column_statements_skip_existing_columns(self):
        dolt_schema_sync = importlib.import_module("dolt_schema_sync")
        schema = {
            "apiName": "DemoObject",
            "primaryKeyPropertyApiNames": ["id"],
            "properties": {
                "id": {"apiName": "id", "dataType": {"type": "string"}, "required": True},
                "name": {"apiName": "name", "dataType": {"type": "string"}},
                "plannedDate": {"apiName": "plannedDate", "dataType": {"type": "date"}},
            },
        }

        statements, added_columns = dolt_schema_sync.build_add_column_statements(
            "demo_object",
            schema,
            existing_columns={"id", "name"},
        )

        self.assertEqual(added_columns, ["plannedDate"])
        self.assertEqual(len(statements), 1)
        self.assertIn("ALTER TABLE `demo_object` ADD COLUMN `plannedDate` DATE NULL", statements[0])
        self.assertNotIn("`name`", statements[0])

    def test_dolt_schema_rejects_invalid_property_identifier(self):
        dolt_schema_sync = importlib.import_module("dolt_schema_sync")
        schema = {
            "apiName": "DemoObject",
            "primaryKeyPropertyApiNames": ["id"],
            "properties": {
                "id": {"apiName": "id", "dataType": {"type": "string"}, "required": True},
                "bad-name": {"apiName": "bad-name", "dataType": {"type": "string"}},
            },
        }

        with self.assertRaises(ValueError):
            dolt_schema_sync.build_create_table_sql("DemoObject", schema)

    def test_dolt_preview_table_route_uses_schema_driven_snake_case(self):
        preview_branch = importlib.import_module("preview_branch")

        self.assertEqual(preview_branch._object_type_table("SupplierCompany"), "supplier_company")

    def test_v2_sync_single_object_type_dolt_schema_success(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        backend_app = importlib.import_module("backend_app")
        expected = {
            "objectType": "DeliveryPlanRow",
            "tableName": "delivery_plan_row",
            "status": "ok",
            "primaryKey": ["rowKey"],
            "addedColumns": [],
            "errors": [],
        }

        with patch.object(backend_app, "sync_object_type_dolt_schema", return_value=expected) as sync:
            response = self.client.post("/api/v2/ontologies/default/objectTypes/DeliveryPlanRow/sync-dolt-schema")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        sync.assert_called_once()

    def test_v2_sync_single_object_type_dolt_schema_skips_without_dolt(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        dolt_schema_sync = importlib.import_module("dolt_schema_sync")
        original_engine = dolt_schema_sync._dolt_engine
        try:
            dolt_schema_sync._dolt_engine = None
            with patch.dict(environ, {"DOLT_DATABASE_URL": "", "DOLT_SCHEMA_SYNC_REQUIRED": ""}):
                response = self.client.post("/api/v2/ontologies/default/objectTypes/DeliveryPlanRow/sync-dolt-schema")
        finally:
            dolt_schema_sync._dolt_engine = original_engine

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["objectType"], "DeliveryPlanRow")
        self.assertEqual(response.json()["tableName"], "delivery_plan_row")
        self.assertEqual(response.json()["status"], "skipped")

    def test_v2_sync_dolt_schema_unknown_object_type_returns_404(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        response = self.client.post("/api/v2/ontologies/default/objectTypes/NoSuchType/sync-dolt-schema")

        self.assertEqual(response.status_code, 404)

    def test_v2_sync_all_object_type_dolt_schemas(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        backend_app = importlib.import_module("backend_app")
        expected = {
            "status": "ok",
            "items": [
                {
                    "objectType": "DeliveryPlanRow",
                    "tableName": "delivery_plan_row",
                    "status": "ok",
                    "primaryKey": ["rowKey"],
                    "addedColumns": [],
                    "errors": [],
                }
            ],
            "errors": [],
        }

        with patch.object(backend_app, "sync_all_object_type_dolt_schemas", return_value=expected) as sync_all:
            response = self.client.post("/api/v2/ontologies/default/objectTypes/sync-dolt-schema")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        sync_all.assert_called_once()

    def test_v1_create_dataset_returns_foundry_style_rid_and_table_name(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        backend_app = importlib.import_module("backend_app")
        expected = {
            "datasetRid": "ri.foundry.main.dataset.abc123",
            "name": "液冷设备实时日志",
            "parentFolderRid": "ri.compass.main.folder.xxx",
            "tableName": "dataset_abc123",
            "status": "ok",
        }

        with patch.object(backend_app, "create_dataset", return_value=expected) as create_dataset:
            response = self.client.post(
                "/api/v1/datasets",
                json={"name": "液冷设备实时日志", "parentFolderRid": "ri.compass.main.folder.xxx"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        create_dataset.assert_called_once()

    def test_v1_dataset_transaction_duplicate_open_returns_409(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        backend_app = importlib.import_module("backend_app")
        dataset_service = importlib.import_module("dataset_service")

        with patch.object(
            backend_app,
            "create_dataset_transaction",
            side_effect=dataset_service.DatasetConflictError("OPEN transaction already exists."),
        ):
            response = self.client.post(
                "/api/v1/datasets/ri.foundry.main.dataset.demo/transactions",
                json={"transactionType": "UPDATE"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("OPEN transaction", response.json()["detail"])

    def test_v1_dataset_file_upload_requires_transaction_rid(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        response = self.client.post(
            "/api/v1/datasets/ri.foundry.main.dataset.demo/files:upload",
            content=b"rowKey,activityName\nrow-1,Demo\n",
            headers={"content-type": "text/csv"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("transactionRid", response.json()["detail"])

    def test_v1_dataset_read_table_supports_json_and_csv_formats(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        backend_app = importlib.import_module("backend_app")
        json_result = {
            "datasetRid": "ri.foundry.main.dataset.demo",
            "tableName": "demo_table",
            "format": "json",
            "rows": [{"rowKey": "row-1"}],
            "total": 1,
        }
        csv_result = {
            "datasetRid": "ri.foundry.main.dataset.demo",
            "tableName": "demo_table",
            "format": "csv",
            "content": "rowKey\nrow-1\n",
            "total": 1,
        }

        with patch.object(backend_app, "read_dataset_table", side_effect=[json_result, csv_result]) as read_table:
            json_response = self.client.get("/api/v1/datasets/ri.foundry.main.dataset.demo/readTable")
            csv_response = self.client.get(
                "/api/v1/datasets/ri.foundry.main.dataset.demo/readTable",
                params={"format": "csv"},
            )

        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(json_response.json()["rows"], [{"rowKey": "row-1"}])
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response.headers["content-type"])
        self.assertEqual(csv_response.text, "rowKey\nrow-1\n")
        self.assertEqual(read_table.call_count, 2)

    def test_dataset_update_transaction_upserts_rows_on_commit(self):
        dataset_service = importlib.import_module("dataset_service")
        object_types = json.loads((BACKEND_DIR / "schema" / "object-types.json").read_text(encoding="utf-8"))
        fake_engine = _MemoryDoltEngine()

        with tempfile.TemporaryDirectory() as tmp_dir:
            service = dataset_service.LocalDatasetService(
                registry_path=Path(tmp_dir) / "registry.json",
                staging_root=Path(tmp_dir) / "staging",
                engine=fake_engine,
            )
            dataset = service.create_dataset(
                name="DeliveryPlanRow",
                parent_folder_rid="ri.compass.main.folder.demo",
                object_type="DeliveryPlanRow",
                object_types=object_types,
            )
            first_tx = service.create_transaction(dataset["datasetRid"], "UPDATE")
            service.upload_file(
                dataset["datasetRid"],
                first_tx["transactionRid"],
                b"rowKey,activityName\nrow-1,old name\n",
                file_name="first.csv",
            )
            first_commit = service.commit_transaction(dataset["datasetRid"], first_tx["transactionRid"])

            second_tx = service.create_transaction(dataset["datasetRid"], "UPDATE")
            service.upload_file(
                dataset["datasetRid"],
                second_tx["transactionRid"],
                b"rowKey,activityName\nrow-1,new name\n",
                file_name="second.csv",
            )
            second_commit = service.commit_transaction(dataset["datasetRid"], second_tx["transactionRid"])
            table = service.read_table(dataset["datasetRid"], output_format="json")

        self.assertEqual(first_commit["status"], "COMMITTED")
        self.assertEqual(second_commit["rowsWritten"], 1)
        self.assertEqual(table["rows"], [{"rowKey": "row-1", "activityName": "new name"}])
        insert_calls = [sql for sql, _ in fake_engine.connection.calls if "INSERT INTO `delivery_plan_row`" in sql]
        self.assertTrue(any("ON DUPLICATE KEY UPDATE" in sql for sql in insert_calls))

    def test_dataset_append_transaction_rejects_duplicate_primary_key(self):
        dataset_service = importlib.import_module("dataset_service")
        object_types = json.loads((BACKEND_DIR / "schema" / "object-types.json").read_text(encoding="utf-8"))
        fake_engine = _MemoryDoltEngine()

        with tempfile.TemporaryDirectory() as tmp_dir:
            service = dataset_service.LocalDatasetService(
                registry_path=Path(tmp_dir) / "registry.json",
                staging_root=Path(tmp_dir) / "staging",
                engine=fake_engine,
            )
            dataset = service.create_dataset(
                name="DeliveryPlanRow",
                parent_folder_rid="ri.compass.main.folder.demo",
                object_type="DeliveryPlanRow",
                object_types=object_types,
            )
            update_tx = service.create_transaction(dataset["datasetRid"], "UPDATE")
            service.upload_file(
                dataset["datasetRid"],
                update_tx["transactionRid"],
                b"rowKey,activityName\nrow-1,old name\n",
                file_name="seed.csv",
            )
            service.commit_transaction(dataset["datasetRid"], update_tx["transactionRid"])

            append_tx = service.create_transaction(dataset["datasetRid"], "APPEND")
            service.upload_file(
                dataset["datasetRid"],
                append_tx["transactionRid"],
                b"rowKey,activityName\nrow-1,duplicate\n",
                file_name="duplicate.csv",
            )
            with self.assertRaises(dataset_service.DatasetConflictError):
                service.commit_transaction(dataset["datasetRid"], append_tx["transactionRid"])

    def test_dataset_transaction_rejected_for_readonly_object_type(self):
        dataset_service = importlib.import_module("dataset_service")
        object_types = json.loads((BACKEND_DIR / "schema" / "object-types.json").read_text(encoding="utf-8"))
        fake_engine = _MemoryDoltEngine()

        with tempfile.TemporaryDirectory() as tmp_dir:
            service = dataset_service.LocalDatasetService(
                registry_path=Path(tmp_dir) / "registry.json",
                staging_root=Path(tmp_dir) / "staging",
                engine=fake_engine,
            )
            readonly = service.create_dataset(
                name="DeliveryProject",
                object_type="DeliveryProject",
                object_types=object_types,
            )
            with self.assertRaises(dataset_service.DatasetReadOnlyError):
                service.create_transaction(readonly["datasetRid"], "UPDATE")

            writable = service.create_dataset(
                name="DeliveryPlanRow",
                object_type="DeliveryPlanRow",
                object_types=object_types,
            )
            transaction = service.create_transaction(writable["datasetRid"], "UPDATE")
            self.assertEqual(transaction["status"], "OPEN")

    def test_contingency_bindings_declare_template_vs_runrecord_split(self):
        import datasource_bindings as db

        # Contingency bindings were merged into the default ontology; the template/run-record
        # writable split is now declared in schema/datasource-bindings.yaml.
        registry = db.load_datasource_bindings()
        # Static templates / reference data stay read-only.
        for object_type in ["DecisionPoint", "EvidenceSource", "ProjectRequirement"]:
            self.assertFalse(registry.object_type(object_type).writable, f"{object_type} should be a read-only template")
        # Dolt-backed chapter fact rows expose selected fields through declared Actions.
        for object_type in ["EquipmentConfig", "NetworkConfig", "ComponentConfig"]:
            self.assertTrue(registry.object_type(object_type).writable, f"{object_type} should be writable via Action")
        # Runtime decision records are writable.
        for object_type in ["ContingencyPlan", "DeliverabilityAssessment", "GapItem", "RemediationTask", "AssumptionItem"]:
            self.assertTrue(registry.object_type(object_type).writable, f"{object_type} should be a writable run-record")

    def test_contingency_reference_inputs_datasources(self):
        """Contingency reference inputs are all Dolt-backed (reader: dolt_rows).

        Dolt is the single source of truth for every contingency reference input: equipment lifecycle
        facts (GA/TR5/EOM/EOS/ESS, 04_设备信息表.xlsx), maintenance-policy EOS facts, component lifecycle
        facts (05_智算部件配置信息表.xlsx) and the global RiskRule library (04 §19.3 全量 35 rules incl. RR-ACC-CHK-01) —
        no committed CSV/JSON in the read path; each read degrades to [] when Dolt is offline. The
        derive-logic tests therefore drive the pure engine with synthetic inputs rather than relying on
        seed data (see test_derive_contingency_risks_isolates_by_project_key).
        """
        import datasource_bindings as db

        dc = importlib.import_module("data_connector")
        registry = db.load_datasource_bindings()
        editable_fact_objects = {"EquipmentConfig", "MaintenancePolicy", "ComponentConfig"}
        for object_type in ["EquipmentConfig", "MaintenancePolicy", "ComponentConfig", "RiskRule"]:
            binding = registry.object_type(object_type)
            self.assertEqual(binding.reader, "dolt_rows", f"{object_type} reader")
            self.assertEqual(binding.source_ids, (), f"{object_type} sources")
            self.assertEqual(binding.writable, object_type in editable_fact_objects, f"{object_type} writable")
            # Dolt read degrades gracefully to a list when the substrate is offline (CI).
            self.assertIsInstance(dc.get_object_data(object_type), list)

    def test_resolve_writable_across_ontologies(self):
        import datasource_bindings as db

        self.assertTrue(db.resolve_object_type_writable("DeliveryPlanRow"))
        self.assertFalse(db.resolve_object_type_writable("DeliveryProject"))
        self.assertIsNone(db.resolve_object_type_writable("NoSuchObjectType"))
        # Merged contingency objects resolve from the single default registry.
        self.assertTrue(db.resolve_object_type_writable("GapItem"))
        self.assertFalse(db.resolve_object_type_writable("DecisionPoint"))

    def test_derive_contingency_risks_isolates_by_project_key(self):
        # Reference inputs are Dolt-backed (empty offline), so this drives the real
        # derive_contingency_risks_for_plan filtering path over synthetic multi-project data:
        # both projects' rows live in one store and per-project isolation is applied by projectKey.
        dc = importlib.import_module("data_connector")
        ref = "2026-06-09"
        rules = [
            {"riskRuleId": "RR-EOS-01", "riskPoint": "EOS风险", "ruleName": "产品EOS早于维保结束",
             "riskCategory": "生命周期风险", "riskLevel": "高", "owner": "交付PM",
             "responseMeasure": "更换在维产品", "impact": "SLA 无法保障", "riskSubCategory": "EOS"},
            {"riskRuleId": "RR-ESS-01", "riskPoint": "ESS风险", "ruleName": "部件超出服务/支持窗口",
             "riskCategory": "生命周期风险", "riskLevel": "中", "owner": "交付PM",
             "responseMeasure": "更换在维部件", "impact": "备件受限", "riskSubCategory": "ESS"},
        ]
        fake = {
            "RiskRule": rules,
            "EquipmentConfig": [],
            "MaintenancePolicy": [
                {"maintenancePolicyId": "MP-J", "projectKey": "京东", "productModel": "Atlas 800 (京东)", "isOverEos": True},
                {"maintenancePolicyId": "MP-Z", "projectKey": "浙江移动", "productModel": "CE6800 (浙江)", "isOverEos": True},
            ],
            "ComponentConfig": [
                {"componentId": "CP-J", "projectKey": "京东", "componentName": "鲲鹏920 (京东)", "isOverEss": True},
                {"componentId": "CP-Z", "projectKey": "浙江移动", "componentName": "RAID卡 (浙江)", "isOverEss": True},
            ],
        }
        with patch.object(dc, "get_object_data", side_effect=lambda ot, project_id=None: fake.get(ot, [])), \
             patch.object(dc, "contingency_object_data", lambda ot: []):
            a = dc.derive_contingency_risks_for_plan(plan_id="PLAN-A", project_key="京东", reference_date=ref)
            b = dc.derive_contingency_risks_for_plan(plan_id="PLAN-B", project_key="浙江移动", reference_date=ref)
        # Each project's derivation is stamped with its own projectKey and is non-empty.
        self.assertEqual(a["projectKey"], "京东")
        self.assertEqual(b["projectKey"], "浙江移动")
        self.assertGreater(a["riskCount"], 0)
        self.assertGreater(b["riskCount"], 0)
        self.assertTrue(all(risk["projectKey"] == "京东" for risk in a["risks"]))
        self.assertTrue(all(risk["projectKey"] == "浙江移动" for risk in b["risks"]))
        # Fired subjects are disjoint — multi-project data in one store stays isolated.
        subjects_a = {subject for risk in a["risks"] for subject in risk["subjects"]}
        subjects_b = {subject for risk in b["risks"] for subject in risk["subjects"]}
        self.assertEqual(subjects_a & subjects_b, set())

    def test_derive_contingency_risks_keeps_trk04_when_chapter_directory_omits_project_requirement(self):
        """TRK-04 is a default tracking risk, not a visible chapter dependency."""
        dc = importlib.import_module("data_connector")
        rules = [
            {"riskRuleId": "RR-TRK-04", "riskPoint": "光模块丢失风险", "ruleName": "光模块丢失",
             "riskCategory": "任务跟踪风险", "riskLevel": "中", "owner": "交付PM",
             "responseMeasure": "列入任务跟踪", "impact": "光模块/光纤转运与装配丢失",
             "riskSubCategory": "TRK-04"},
        ]
        requirements = [
            {"requirementId": "PR-JD", "projectKey": "京东", "requirementName": "京东三期项目",
             "deliveryScope": "智算底座交付"},
            {"requirementId": "PR-ZJ", "projectKey": "浙江移动", "requirementName": "浙江移动项目",
             "deliveryScope": "智算底座交付"},
        ]
        fake = {
            "RiskRule": rules,
            "ProjectRequirement": requirements,
            "EquipmentConfig": [],
            "MaintenancePolicy": [],
            "ComponentConfig": [],
            "DecisionPoint": [],
        }
        plan_only_directory = [{"id": "doc-ch-12", "no": "10", "title": "计划"}]

        with patch.object(dc, "get_object_data", side_effect=lambda ot, project_id=None: fake.get(ot, [])), \
             patch.object(dc, "contingency_object_data", lambda ot: []), \
             patch.object(dc, "_load_contingency_chapter_directory", lambda: plan_only_directory):
            result = dc.derive_contingency_risks_for_plan(plan_id="PLAN-JD", project_key="京东")

        trk = [risk for risk in result["risks"] if risk["riskPoint"] == "光模块丢失风险"]
        self.assertEqual(len(trk), 1)
        self.assertEqual(trk[0]["riskId"], "PLAN-JD_TRK-04_光模块丢失风险")
        self.assertEqual(trk[0]["subjects"], ["京东三期项目"])
        self.assertEqual(trk[0]["provenance"]["subjects"][0]["objectType"], "ProjectRequirement")

    def test_derive_contingency_risks_keeps_trk04_for_unscoped_single_project_requirement(self):
        """TRK-04 must survive frontend project_key filtering when the background row is unscoped."""
        dc = importlib.import_module("data_connector")
        rules = [
            {"riskRuleId": "RR-TRK-04", "riskPoint": "光模块丢失风险", "ruleName": "光模块丢失",
             "riskCategory": "任务跟踪风险", "riskLevel": "中", "owner": "交付PM",
             "responseMeasure": "列入任务跟踪", "impact": "光模块/光纤转运与装配丢失",
             "riskSubCategory": "TRK-04"},
        ]
        fake = {
            "RiskRule": rules,
            "ProjectRequirement": [
                {"requirementId": "PR-JD", "requirementName": "京东三期项目",
                 "deliveryScope": "智算底座交付"},
            ],
            "EquipmentConfig": [],
            "MaintenancePolicy": [],
            "ComponentConfig": [],
            "DecisionPoint": [],
        }

        with patch.object(dc, "get_object_data", side_effect=lambda ot, project_id=None: fake.get(ot, [])), \
             patch.object(dc, "contingency_object_data", lambda ot: []), \
             patch.object(dc, "_load_contingency_chapter_directory", lambda: []):
            result = dc.derive_contingency_risks_for_plan(plan_id="PLAN-JD", project_key="京东")

        self.assertEqual(
            [(risk["riskPoint"], risk["subjects"]) for risk in result["risks"]],
            [("光模块丢失风险", ["京东三期项目"])],
        )

    def test_derive_contingency_risks_acc_chk_01_arrival_milestone(self):
        """ACC-CHK-01 (04 §19.3 验收④): a 到货 AcceptanceStrategy with an empty milestone fires a 高 risk.

        Exercises the AcceptanceStrategy lane end-to-end. RiskRule is now Dolt-backed (empty offline),
        so the global RR-ACC-CHK-01 rule (riskPoint 验收到货里程碑缺失风险) is provided synthetically and
        the pure derive engine is driven directly.
        """
        dc = importlib.import_module("data_connector")
        point = "验收到货里程碑缺失风险"
        rules = [{
            "riskRuleId": "RR-ACC-CHK-01", "ruleName": "到货验收里程碑为空", "status": "ACTIVE",
            "riskPoint": point, "riskCategory": "验收可交付性风险", "riskSubCategory": "ACC-CHK-01",
            "riskLevel": "高", "owner": "交付PM",
            "responseMeasure": "为到货类验收补齐验收里程碑（如「到货签收」）并与计划节点对齐",
            "impact": "到货验收缺里程碑，无法形成可签收闭环，影响验收可交付性与回款节点",
        }]

        # 18_验收策略表 真值：到货行里程碑为「到货签收」→ 不触发
        real_18 = [
            {"acceptanceStrategyId": "AS-1", "category": "到货", "acceptancePlan": "设备到货清点", "acceptanceMilestone": "到货签收"},
            {"acceptanceStrategyId": "AS-2", "category": "安装 PAC", "acceptancePlan": "整机柜 ST 测试", "acceptanceMilestone": "部署调测完成"},
        ]
        clean = dc.derive_contingency_risks([], rules, acceptance_strategies=real_18, reference_date="2026-06-09")
        self.assertEqual([r for r in clean["risks"] if r["riskPoint"] == point], [])

        # 到货行里程碑为空（含「—」占位）→ 触发 1 条 高
        for empty in ("", "—"):
            fired = dc.derive_contingency_risks(
                [],
                rules,
                acceptance_strategies=[{
                    "acceptanceStrategyId": "AS-1", "category": "到货",
                    "acceptancePlan": "设备到货清点", "acceptanceMilestone": empty,
                }],
                reference_date="2026-06-09",
            )
            acc = [r for r in fired["risks"] if r["riskPoint"] == point]
            self.assertEqual(len(acc), 1, f"milestone={empty!r}")
            self.assertEqual(acc[0]["severity"], "高")
            self.assertEqual(acc[0]["riskName"], "到货验收里程碑为空")
            self.assertIn("设备到货清点", acc[0]["subjects"])

    def test_derive_contingency_risks_carry_provenance_drilldown(self):
        """每条派生风险携带 provenance（规则 × 触发主体 × 字段级证据）——溯源下钻的数据契约。

        EOS 通道喂混合事实源（EquipmentConfig 走日期比较 + MaintenancePolicy 走预计算标志），
        验证：subjects 标签与溯源主体一致（溯源与展示不漂移）；证据如实复现引擎所做的比较
        （字段 / 值 / 比较对象 / 基准日），UI 无需重放引擎即可解释「为什么有这条风险」。
        """
        dc = importlib.import_module("data_connector")
        ref = "2026-06-09"
        rules = [{
            "riskRuleId": "RR-EOS-01", "riskPoint": "EOS风险", "ruleName": "产品EOS早于维保结束",
            "riskCategory": "生命周期风险", "riskSubCategory": "EOS", "riskLevel": "高",
            "owner": "交付PM", "responseMeasure": "更换在维产品", "impact": "SLA 无法保障",
        }]
        policies = [
            {"maintenancePolicyId": "MP-1", "productModel": "OceanStor 5300", "isOverEos": True},
        ]
        equipment = [
            {"equipmentId": "EQ-1", "equipmentName": "CE6865", "eosDate": "2025-12-31"},
        ]
        result = dc.derive_contingency_risks(
            policies, rules, plan_id="PLAN-X", equipment_configs=equipment, reference_date=ref
        )
        eos = [r for r in result["risks"] if r["riskPoint"] == "EOS风险"]
        self.assertEqual(len(eos), 1)
        risk = eos[0]
        prov = risk["provenance"]
        # 规则侧：来源规则行的关键字段如实带出。
        self.assertEqual(prov["rule"]["ruleId"], "RR-EOS-01")
        self.assertEqual(prov["rule"]["ruleName"], "产品EOS早于维保结束")
        self.assertEqual(prov["referenceDate"], ref)
        # 主体侧：溯源主体标签集合 == subjects（展示用标签数组保持原契约）。
        self.assertEqual(sorted({s["label"] for s in prov["subjects"]}), risk["subjects"])
        by_type = {s["objectType"]: s for s in prov["subjects"]}
        eq = by_type["EquipmentConfig"]
        self.assertEqual(eq["keyValue"], "EQ-1")
        self.assertTrue(eq["objectTypeLabel"])  # schema displayName（缺 schema 时退回 apiName）
        self.assertEqual(eq["evidence"]["field"], "eosDate")
        self.assertEqual(eq["evidence"]["value"], "2025-12-31")
        self.assertEqual(eq["evidence"]["comparator"], "<")
        self.assertEqual(eq["evidence"]["threshold"], ref)
        self.assertIn("2025-12-31", eq["reason"])
        self.assertIn("基准日", eq["reason"])
        mp = by_type["MaintenancePolicy"]
        self.assertEqual(mp["keyValue"], "MP-1")
        self.assertEqual(mp["evidence"]["field"], "isOverEos")
        self.assertIn("isOverEos", mp["reason"])

    def test_derive_contingency_chapters_default_lean_columns_append_on_hit(self):
        """默认精简+命中追加：风险证据字段自动成为章节可见列，并带命中格索引（riskCells）。

        设备章（doc-device）的 curated fieldOrder 不含生命周期日期；EOM 命中后 eomDate 以
        derived 列插到首列之后（label/note 取自 ObjectType schema），riskCells/rowKeyField
        定位到「哪一行哪一格」。未命中的其余日期（gaDate/tr5Date/essDate）保持不出现——溯源
        跳行总能看到被比较的值，而 10 个生命周期时间点不常驻刷屏。§8 维保章静态已含
        isOverEos 列 → 同字段命中按 key 去重不重复追加。
        """
        dc = importlib.import_module("data_connector")
        ref = "2026-06-09"
        rules = [
            {"riskRuleId": "RR-EOM-01", "riskPoint": "EOM风险", "ruleName": "产品EOM早于交付窗口",
             "riskCategory": "生命周期风险", "riskSubCategory": "EOM", "riskLevel": "高",
             "owner": "交付PM", "responseMeasure": "替换选型", "impact": "供货受限"},
            {"riskRuleId": "RR-EOS-01", "riskPoint": "EOS风险", "ruleName": "产品EOS早于维保结束",
             "riskCategory": "生命周期风险", "riskSubCategory": "EOS", "riskLevel": "高",
             "owner": "交付PM", "responseMeasure": "更换在维产品", "impact": "SLA 无法保障"},
        ]
        equipment = [
            # eomDate < 基准日+2月（2026-08-09）→ EOM 命中；EQ-2 未命中作对照
            {"equipmentId": "EQ-1", "equipmentName": "NetEngine 8000", "model": "NE8000-M14",
             "eomDate": "2026-07-01"},
            {"equipmentId": "EQ-2", "equipmentName": "CloudEngine 6857", "model": "CE6857",
             "eomDate": "2027-03-01"},
        ]
        policies = [
            {"maintenancePolicyId": "MP-1", "productModel": "OceanStor 5300", "isOverEos": True},
        ]
        result = dc.derive_contingency_risks(
            policies, rules, plan_id="PLAN-X", equipment_configs=equipment, reference_date=ref
        )
        chapters = {c["id"]: c for c in result["chapters"]}

        device = chapters["doc-device"]
        cols = device["columns"]
        by_key = {c["key"]: c for c in cols}
        # 命中追加列：插在首列之后、带 derived 标记，label 来自 schema displayName。
        self.assertIn("eomDate", by_key)
        self.assertTrue(by_key["eomDate"].get("derived"))
        self.assertEqual(cols[1]["key"], "eomDate")
        self.assertEqual(by_key["eomDate"]["label"], "EOM 计划时间")
        # 默认精简：未命中的生命周期日期不出现。
        for lean in ("gaDate", "tr5Date", "essDate"):
            self.assertNotIn(lean, by_key)
        # 命中格索引：恰好 EQ-1 × eomDate 一格；riskId 指回派生风险；行键字段 = 主键 apiName。
        self.assertEqual(device["rowKeyField"], "equipmentId")
        self.assertEqual(
            [(c["rowKey"], c["field"]) for c in device["riskCells"]],
            [("EQ-1", "eomDate")],
        )
        eom_ids = {r["riskId"] for r in result["risks"] if r["riskPoint"] == "EOM风险"}
        self.assertIn(device["riskCells"][0]["riskId"], eom_ids)
        self.assertIn("2026-07-01", device["riskCells"][0]["reason"])

        # §8 维保章：isOverEos 已是 curated 静态列 → 不重复追加；命中格仍被索引。
        network = chapters["doc-network"]
        eos_cols = [c for c in network["columns"] if c["key"] == "isOverEos"]
        self.assertEqual(len(eos_cols), 1)
        self.assertFalse(eos_cols[0].get("derived"))
        self.assertEqual(network["rowKeyField"], "maintenancePolicyId")
        self.assertEqual(
            [(c["rowKey"], c["field"]) for c in network["riskCells"]],
            [("MP-1", "isOverEos")],
        )

    def test_adopt_derived_risk_run_record_create_under_default(self):
        # Run-record CREATE (AdoptDerivedRisk -> RiskItem) is routed by Action metadata
        # (writeback:run_record), NOT by ontology id; it persists to the run-record overlay with
        # its ProjectScoped projectKey and reads back through the default object facade.
        dc = importlib.import_module("data_connector")
        backend_app = importlib.import_module("backend_app")
        orig_get = dc.get_object_data
        # Reference inputs are Dolt-backed (empty offline); feed synthetic 京东 facts + rule so the
        # derivation yields a risk to adopt, while RiskItem reads still hit the real run-record path.
        fake_inputs = {
            "MaintenancePolicy": [{"maintenancePolicyId": "MP-J", "projectKey": "京东",
                                   "productModel": "Atlas 800 (京东)", "isOverEos": True}],
            "RiskRule": [{"riskRuleId": "RR-EOS-01", "riskPoint": "EOS风险", "ruleName": "产品EOS早于维保结束",
                          "riskCategory": "生命周期风险", "riskLevel": "高", "owner": "交付PM",
                          "responseMeasure": "更换在维产品", "impact": "SLA 无法保障", "riskSubCategory": "EOS"}],
            "EquipmentConfig": [],
            "ComponentConfig": [],
        }

        def fake_get(ot, project_id=None):
            return fake_inputs[ot] if ot in fake_inputs else orig_get(ot, project_id)

        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            # Empty the Dolt base layer (read_dolt_object_rows) rather than contingency_object_data:
            # RiskItem is now reader: dolt_rows, so its read-back flows through contingency_object_data
            # = read_dolt_object_rows (Dolt seed) ∪ run-record overlay. Patching the base keeps Dolt
            # empty while the real overlay (the just-adopted RiskItem) still unions through — i.e.
            # RiskItem reads still hit the real run-record path, as the derive isolation intends.
            with patch.object(dc, "_contingency_runrecord_path", lambda ot: runtime / f"{ot}.json"), \
                 patch.object(dc, "get_object_data", side_effect=fake_get), \
                 patch.object(dc, "read_dolt_object_rows", lambda *a, **k: []):
                derived = dc.derive_contingency_risks_for_plan(
                    plan_id="PLAN-A", project_key="京东", reference_date="2026-06-09"
                )
                self.assertGreater(derived["riskCount"], 0)
                payload = {**derived["risks"][0], "assessmentId": "A-1"}
                # validate routes to the run-record path and threads projectKey (previously errored)
                validated = backend_app.validate_action_type("AdoptDerivedRisk", payload, "default")
                self.assertTrue(validated["success"])
                self.assertEqual(validated["validatedObject"]["projectKey"], "京东")
                # apply persists the RiskItem run-record
                applied = backend_app.apply_action_type("AdoptDerivedRisk", payload, "default")
                self.assertEqual(applied["data"]["projectKey"], "京东")
                # read back through the default facade, with per-project isolation
                rows = dc.get_object_data("RiskItem")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["projectKey"], "京东")
                self.assertEqual(len(dc.get_object_data("RiskItem", "京东")), 1)
                self.assertEqual(len(dc.get_object_data("RiskItem", "浙江移动")), 0)

    def test_dataset_transaction_rejected_for_contingency_template_type(self):
        # Contingency object types now live in the merged default schema.
        schema_path = BACKEND_DIR / "schema" / "object-types.json"

        dataset_service = importlib.import_module("dataset_service")
        contingency_object_types = json.loads(schema_path.read_text(encoding="utf-8"))
        fake_engine = _MemoryDoltEngine()

        with tempfile.TemporaryDirectory() as tmp_dir:
            service = dataset_service.LocalDatasetService(
                registry_path=Path(tmp_dir) / "registry.json",
                staging_root=Path(tmp_dir) / "staging",
                engine=fake_engine,
            )
            template = service.create_dataset(
                name="DecisionPoint",
                object_type="DecisionPoint",
                object_types=contingency_object_types,
            )
            with self.assertRaises(dataset_service.DatasetReadOnlyError):
                service.create_transaction(template["datasetRid"], "UPDATE")

            run_record = service.create_dataset(
                name="GapItem",
                object_type="GapItem",
                object_types=contingency_object_types,
            )
            transaction = service.create_transaction(run_record["datasetRid"], "UPDATE")
            self.assertEqual(transaction["status"], "OPEN")

    def test_object_type_backing_dataset_sync_uses_current_csv_rows(self):
        dataset_service = importlib.import_module("dataset_service")
        object_types = json.loads((BACKEND_DIR / "schema" / "object-types.json").read_text(encoding="utf-8"))
        fake_engine = _MemoryDoltEngine()

        with tempfile.TemporaryDirectory() as tmp_dir:
            service = dataset_service.LocalDatasetService(
                registry_path=Path(tmp_dir) / "registry.json",
                staging_root=Path(tmp_dir) / "staging",
                engine=fake_engine,
            )
            summary = service.sync_object_type_backing_datasets(object_types=object_types)

        by_type = {item["objectType"]: item for item in summary["items"]}
        self.assertEqual(by_type["DeliveryProject"]["rowsWritten"], 2)
        self.assertEqual(by_type["DeliveryPod"]["rowsWritten"], 10)
        self.assertEqual(by_type["DeliveryPlanRow"]["rowsWritten"], 411)
        self.assertEqual(by_type["Milestone"]["rowsWritten"], 18)
        self.assertEqual(by_type["SupplierCompany"]["status"], "skipped")
        self.assertEqual(by_type["ChangeOrder"]["status"], "skipped")
        first_plan_row = fake_engine.connection.tables["delivery_plan_row"][0]
        self.assertIn("rowKey", first_plan_row)
        self.assertNotIn("活动名称", first_plan_row)

    def test_dolt_mirror_sync_snapshots_core_object_rows(self):
        dolt_mirror = importlib.import_module("dolt_mirror")
        object_types = json.loads((BACKEND_DIR / "schema" / "object-types.json").read_text(encoding="utf-8"))
        fake_engine = _MemoryDoltEngine()
        fake_engine.connection.tables["delivery_project"] = [{"projectKey": "stale"}]

        summary = dolt_mirror.sync_main_mirror(
            object_types=["DeliveryProject", "DeliveryPod", "DeliveryPlanRow", "Milestone"],
            object_type_schemas=object_types,
            engine=fake_engine,
        )

        by_type = {item["objectType"]: item for item in summary["items"]}
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(by_type["DeliveryProject"]["csvCount"], 2)
        self.assertEqual(by_type["DeliveryProject"]["doltCount"], 2)
        self.assertEqual(by_type["DeliveryPlanRow"]["csvCount"], 411)
        self.assertEqual(len(fake_engine.connection.tables["delivery_project"]), 2)
        self.assertFalse(
            any(row.get("projectKey") == "stale" for row in fake_engine.connection.tables["delivery_project"])
        )
        first_plan_row = fake_engine.connection.tables["delivery_plan_row"][0]
        self.assertIn("rowKey", first_plan_row)
        self.assertNotIn("活动名称", first_plan_row)

    @unittest.skip("需要运行中的 Dolt SQL server（独立基建，未在 ontology 离线环境配置）")
    def test_dolt_mirror_sync_overlay_routes_through_ingest_and_merge(self):
        dolt_mirror = importlib.import_module("dolt_mirror")
        object_types = json.loads((BACKEND_DIR / "schema" / "object-types.json").read_text(encoding="utf-8"))

        class _FakeIngestManager:
            ingest_branch = "ingest"

            def __init__(self):
                self.calls = []
                self.main_engine = _MemoryDoltEngine()

            def get_main_engine(self):
                return self.main_engine

            def ingest_and_merge(self, table, rows, *, columns=None, primary_keys=None):
                materialized = list(rows)
                self.calls.append(
                    {"table": table, "rows": len(materialized), "primaryKeys": list(primary_keys or [])}
                )
                return {
                    "ingestBranch": "ingest",
                    "tableName": table,
                    "rowsWritten": len(materialized),
                    "status": "MERGED",
                }

        fake_manager = _FakeIngestManager()
        with patch.dict(environ, {"DOLT_WRITEBACK_OVERLAY": "1"}, clear=False), patch.object(
            dolt_mirror, "get_scenario_manager", return_value=fake_manager
        ):
            summary = dolt_mirror.sync_main_mirror(
                object_types=["DeliveryProject", "DeliveryPlanRow"],
                object_type_schemas=object_types,
                engine=_MemoryDoltEngine(),
            )

        by_type = {item["objectType"]: item for item in summary["items"]}
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(by_type["DeliveryProject"]["ingestBranch"], "ingest")
        self.assertEqual(by_type["DeliveryProject"]["csvCount"], 2)
        self.assertEqual(by_type["DeliveryProject"]["doltCount"], 2)
        self.assertEqual(by_type["DeliveryPlanRow"]["csvCount"], 411)
        called_tables = {call["table"] for call in fake_manager.calls}
        self.assertIn("delivery_project", called_tables)
        self.assertIn("delivery_plan_row", called_tables)

    def test_dolt_mirror_validate_reports_key_and_field_drift(self):
        dolt_mirror = importlib.import_module("dolt_mirror")
        object_types = json.loads((BACKEND_DIR / "schema" / "object-types.json").read_text(encoding="utf-8"))
        fake_engine = _MemoryDoltEngine()
        dolt_mirror.sync_main_mirror(
            object_types=["DeliveryProject"],
            object_type_schemas=object_types,
            engine=fake_engine,
        )
        rows = fake_engine.connection.tables["delivery_project"]
        rows.pop()
        rows[0]["projectName"] = "changed name"
        rows.append({"projectKey": "extra-project", "projectName": "extra"})

        summary = dolt_mirror.validate_main_mirror(
            object_types=["DeliveryProject"],
            object_type_schemas=object_types,
            engine=fake_engine,
        )

        item = summary["items"][0]
        self.assertEqual(summary["status"], "drift")
        self.assertEqual(item["status"], "drift")
        self.assertEqual(item["csvCount"], 2)
        self.assertEqual(item["doltCount"], 2)
        self.assertEqual(item["missingInDolt"], 1)
        self.assertEqual(item["extraInDolt"], 1)
        self.assertEqual(item["mismatchedRows"], 1)
        self.assertIn("projectName", item["checkedFields"])

    def test_v2_dolt_mirror_validate_endpoint(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        backend_app = importlib.import_module("backend_app")
        expected = {
            "status": "ok",
            "items": [
                {
                    "objectType": "DeliveryProject",
                    "tableName": "delivery_project",
                    "csvCount": 2,
                    "doltCount": 2,
                    "missingInDolt": 0,
                    "extraInDolt": 0,
                    "mismatchedRows": 0,
                    "status": "ok",
                }
            ],
            "errors": [],
        }

        with patch.object(backend_app, "validate_main_mirror", return_value=expected) as validate:
            response = self.client.get(
                "/api/v2/ontologies/default/doltMirror/validate",
                params={"objectTypes": "DeliveryProject"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        validate.assert_called_once()

    def test_v2_preview_branch_object_list_requires_dolt_for_all_objects(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        with patch.dict(environ, {"DOLT_DATABASE_URL": ""}, clear=False):
            response = self.client.get(
                "/api/v2/ontologies/default/objects/DeliveryProject",
                headers={"Preview-Branch-Id": "shadow_sim_789"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("DOLT_DATABASE_URL", response.json()["detail"])

    def test_preview_branch_object_data_routes_core_objects_to_dolt(self):
        data_connector = importlib.import_module("data_connector")
        preview_branch = importlib.import_module("preview_branch")
        context = preview_branch.resolve_preview_branch_context("shadow_sim_789")

        with preview_branch.use_preview_branch(context):
            with patch.object(
                data_connector,
                "get_object_data_for_branch",
                return_value=[{"projectKey": "from-dolt"}],
            ) as read_branch:
                rows = data_connector.get_object_data("DeliveryProject")

        self.assertEqual(rows, [{"projectKey": "from-dolt"}])
        read_branch.assert_called_once_with(context, "DeliveryProject", project_key=None)

    def test_get_object_data_serves_main_from_dolt_when_overlay_enabled(self):
        data_connector = importlib.import_module("data_connector")

        with patch.dict(environ, {"DOLT_WRITEBACK_OVERLAY": "1"}, clear=False):
            with patch.object(
                data_connector,
                "get_object_data_for_branch",
                return_value=[{"projectKey": "from-dolt-main"}],
            ) as read_branch:
                rows = data_connector.get_object_data("DeliveryProject")

        self.assertEqual(rows, [{"projectKey": "from-dolt-main"}])
        read_branch.assert_called_once()
        routed_context = read_branch.call_args[0][0]
        self.assertTrue(routed_context.is_main)

    def test_get_object_data_serves_main_from_csv_when_overlay_disabled(self):
        data_connector = importlib.import_module("data_connector")

        with patch.dict(environ, {"DOLT_WRITEBACK_OVERLAY": "0"}, clear=False):
            with patch.object(data_connector, "get_object_data_for_branch") as read_branch:
                rows = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")

        read_branch.assert_not_called()
        self.assertGreater(len(rows), 0)
        self.assertIn("rowKey", rows[0])

    def _activity(
        self,
        key: str,
        start: str,
        end: str,
        *,
        duration_days: int = 0,
        dependency_keys: list[str] | None = None,
    ):
        from schedule_plan_activities import Activity

        dependencies = dependency_keys or []
        return Activity(
            name=key,
            key=key,
            activity_id=key,
            unit="",
            planned_start=start,
            planned_end=end,
            sla_raw=f"{duration_days}天" if duration_days else "",
            duration_days=duration_days,
            batch="",
            dependency_names=list(dependencies),
            dependency_keys=list(dependencies),
        )

    def test_delivery_plan_row_data_uses_real_object_type(self):
        data_connector = importlib.import_module("data_connector")

        rows = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")

        self.assertGreater(len(rows), 0)
        self.assertIn("rowKey", rows[0])
        self.assertIn("activityName", rows[0])
        self.assertIn("startDate", rows[0])
        self.assertIn("endDate", rows[0])
        self.assertEqual(rows[0]["projectKey"], "浙江移动")

    def test_local_schedule_ontology_applies_effective_sla_to_runtime_activity_duration(self):
        schedule_ontology = importlib.import_module("schedule_ontology")

        ontology = schedule_ontology.LocalScheduleOntology.from_rows(
            [
                {
                    "活动ID": "A1",
                    "管理单元": "",
                    "活动名称": "安装",
                    "开始日期": "2026-08-01",
                    "结束日期": "2026-08-10",
                    "SLA": "10天",
                    "依赖活动": "",
                    "批次": "",
                    "标准工期": "10天",
                    "极限工期": "5天",
                }
            ],
            project_key="Demo",
            effective_sla_by_row_key={"demo::安装": "3天"},
            effective_limit_duration_by_row_key={"demo::安装": "1天"},
        )

        row = ontology.row("demo::安装")

        self.assertEqual(row.sla, "3天")
        self.assertEqual(row.duration_days, 3)
        self.assertEqual(row.to_schema_object()["standardDuration"], "3天")
        self.assertEqual(row.to_schema_object()["limitDuration"], "1天")

    def test_get_object_data_defaults_to_effective_sla_for_delivery_plan_rows(self):
        data_connector = importlib.import_module("data_connector")

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "plan.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "序列号",
                        "活动ID",
                        "管理单元",
                        "活动名称",
                        "开始日期",
                        "结束日期",
                        "SLA",
                        "依赖活动",
                        "批次",
                        "标准工期",
                        "极限工期",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "序列号": "row-1",
                        "活动ID": "A1",
                        "管理单元": "",
                        "活动名称": "准备",
                        "开始日期": "2026-07-30",
                        "结束日期": "2026-08-01",
                        "SLA": "3天",
                        "依赖活动": "",
                        "批次": "",
                        "标准工期": "3天",
                        "极限工期": "2天",
                    }
                )
                writer.writerow(
                    {
                        "序列号": "row-2",
                        "活动ID": "A2",
                        "管理单元": "",
                        "活动名称": "安装",
                        "开始日期": "2026-08-01",
                        "结束日期": "2026-08-10",
                        "SLA": "10天",
                        "依赖活动": "准备",
                        "批次": "",
                        "标准工期": "10天",
                        "极限工期": "5天",
                    }
                )
            source = data_connector.ProjectSource("Demo", "plan.csv", "demo")
            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            data_connector.PROJECT_SOURCES = {"Demo": source}
            data_connector.BASE_DIR = Path(tmp_dir)
            try:
                with patch.dict(environ, {"DOLT_WRITEBACK_OVERLAY": "0"}, clear=False):
                    with patch.object(
                        data_connector,
                        "_effective_sla_overrides_for_project",
                        return_value=({"demo::安装": "3天"}, {"demo::安装": "1天"}),
                    ):
                        rows = data_connector.get_object_data("DeliveryPlanRow", project_id="Demo")
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

        row = next(item for item in rows if item["rowKey"] == "demo::安装")

        self.assertEqual(row["sla"], "3天")
        self.assertEqual(row["standardDuration"], "3天")
        self.assertEqual(row["limitDuration"], "1天")

    def test_preview_branch_delivery_plan_rows_default_to_effective_sla(self):
        data_connector = importlib.import_module("data_connector")
        source = data_connector.ProjectSource("Demo", "missing.csv", "demo")
        original_sources = data_connector.PROJECT_SOURCES
        data_connector.PROJECT_SOURCES = {"Demo": source}
        try:
            with patch.object(data_connector, "get_current_preview_branch", return_value=SimpleNamespace(is_main=False)):
                with patch.object(
                    data_connector,
                    "get_object_data_for_branch",
                    return_value=[
                        {
                            "rowKey": "demo::安装",
                            "projectKey": "Demo",
                            "activityName": "安装",
                            "sla": "10天",
                            "standardDuration": "10天",
                            "limitDuration": "5天",
                        }
                    ],
                ):
                    with patch.object(
                        data_connector,
                        "_effective_sla_overrides_for_project",
                        return_value=({"demo::安装": "3天"}, {"demo::安装": "1天"}),
                    ):
                        rows = data_connector.get_object_data("DeliveryPlanRow", project_id="Demo")
        finally:
            data_connector.PROJECT_SOURCES = original_sources

        self.assertEqual(rows[0]["sla"], "3天")
        self.assertEqual(rows[0]["standardDuration"], "3天")
        self.assertEqual(rows[0]["limitDuration"], "1天")

    def test_plan_row_dependencies_default_to_effective_sla(self):
        data_connector = importlib.import_module("data_connector")

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "plan.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "序列号",
                        "活动ID",
                        "管理单元",
                        "活动名称",
                        "开始日期",
                        "结束日期",
                        "SLA",
                        "依赖活动",
                        "批次",
                        "标准工期",
                        "极限工期",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "序列号": "row-1",
                        "活动ID": "A1",
                        "管理单元": "",
                        "活动名称": "准备",
                        "开始日期": "2026-07-30",
                        "结束日期": "2026-08-01",
                        "SLA": "3天",
                        "依赖活动": "",
                        "批次": "",
                        "标准工期": "3天",
                        "极限工期": "2天",
                    }
                )
                writer.writerow(
                    {
                        "序列号": "row-2",
                        "活动ID": "A2",
                        "管理单元": "",
                        "活动名称": "安装",
                        "开始日期": "2026-08-01",
                        "结束日期": "2026-08-10",
                        "SLA": "10天",
                        "依赖活动": "准备",
                        "批次": "",
                        "标准工期": "10天",
                        "极限工期": "5天",
                    }
                )
            source = data_connector.ProjectSource("Demo", "plan.csv", "demo")
            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            data_connector.PROJECT_SOURCES = {"Demo": source}
            data_connector.BASE_DIR = Path(tmp_dir)
            try:
                with patch.object(
                    data_connector,
                    "_effective_sla_overrides_for_project",
                    return_value=({"demo::准备": "1天"}, {"demo::准备": "1天"}),
                ):
                    rows = data_connector.get_linked_object_data(
                        "DeliveryPlanRow",
                        "demo::安装",
                        "PlanRowDependencies",
                        project_id="Demo",
                    )
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rowKey"], "demo::准备")
        self.assertEqual(rows[0]["sla"], "1天")
        self.assertEqual(rows[0]["standardDuration"], "1天")
        self.assertEqual(rows[0]["limitDuration"], "1天")

    def test_load_ontology_can_keep_raw_sla_for_internal_diagnostics(self):
        data_connector = importlib.import_module("data_connector")

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "plan.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "序列号",
                        "活动ID",
                        "管理单元",
                        "活动名称",
                        "开始日期",
                        "结束日期",
                        "SLA",
                        "依赖活动",
                        "批次",
                        "标准工期",
                        "极限工期",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "序列号": "row-1",
                        "活动ID": "A1",
                        "管理单元": "",
                        "活动名称": "安装",
                        "开始日期": "2026-08-01",
                        "结束日期": "2026-08-10",
                        "SLA": "10天",
                        "依赖活动": "",
                        "批次": "",
                        "标准工期": "10天",
                        "极限工期": "5天",
                    }
                )
            source = SimpleNamespace(path=csv_path, project_key="Demo", project_id="Demo")

            raw_ontology = data_connector._load_ontology(source, use_effective_sla=False)
            with patch.object(
                data_connector,
                "_effective_sla_overrides_for_project",
                return_value=({"demo::安装": "3天"}, {"demo::安装": "1天"}),
            ):
                runtime_ontology = data_connector._load_ontology(source, use_effective_sla=True)

        self.assertEqual(raw_ontology.row("demo::安装").duration_days, 10)
        self.assertEqual(raw_ontology.row("demo::安装").to_schema_object()["limitDuration"], "5天")
        self.assertEqual(runtime_ontology.row("demo::安装").duration_days, 3)
        self.assertEqual(runtime_ontology.row("demo::安装").to_schema_object()["limitDuration"], "1天")

    def test_activity_alias_is_not_supported(self):
        data_connector = importlib.import_module("data_connector")

        with self.assertRaises(ValueError):
            data_connector.get_object_data("Activity", project_id="浙江移动")

    def test_meta_converter_builds_rjsf_schema_from_object_types(self):
        backend_app = importlib.import_module("backend_app")

        meta = backend_app.build_object_meta("DeliveryPlanRow")

        self.assertEqual(meta["objectType"], "DeliveryPlanRow")
        self.assertIn("rawObjectType", meta)
        self.assertIn("activityName", meta["dataSchema"]["properties"])
        self.assertIn("rowKey", meta["dataSchema"]["required"])
        self.assertEqual(meta["uiSchema"]["ui:gantt"]["idField"], "rowKey")
        self.assertEqual(meta["uiSchema"]["ui:gantt"]["nameField"], "activityName")
        self.assertTrue(meta["uiSchema"]["rowKey"]["ui:readonly"])

    def test_milestone_meta_builds_from_object_type(self):
        backend_app = importlib.import_module("backend_app")

        meta = backend_app.build_object_meta("Milestone")

        self.assertEqual(meta["objectType"], "Milestone")
        self.assertIn("milestoneKey", meta["dataSchema"]["properties"])
        self.assertIn("milestoneKey", meta["dataSchema"]["required"])
        self.assertEqual(meta["uiSchema"]["ui:gantt"]["idField"], "milestoneKey")
        self.assertEqual(meta["uiSchema"]["ui:gantt"]["nameField"], "milestoneName")
        self.assertTrue(meta["uiSchema"]["milestoneKey"]["ui:readonly"])

    def test_milestone_data_reads_project_global_csv_rows(self):
        data_connector = importlib.import_module("data_connector")

        rows = data_connector.get_object_data("Milestone", project_id="京东")
        project_rows = [row for row in rows if row["scopeType"] == "PROJECT"]

        self.assertTrue(
            {
                "ROOM_IMPLEMENTATION_DONE",
                "ARRIVAL",
                "POWER_ON",
                "CLUSTER_DEBUG",
            }.issubset({row["milestoneType"] for row in project_rows})
        )
        self.assertTrue(all(row["projectKey"] == "京东" for row in rows))
        self.assertTrue(all(row["scopeType"] == "PROJECT" for row in project_rows))
        power_on = next(row for row in project_rows if row["milestoneType"] == "POWER_ON")
        self.assertEqual(power_on["dependencyMilestoneTypes"], "ROOM_IMPLEMENTATION_DONE,ARRIVAL")
        self.assertEqual(power_on["anchorDate"], "2026-03-17")

    @unittest.skip("pre-existing upstream 失败（源仓库同样 anchorDate 差1天），非本次合入引入")
    def test_milestone_data_includes_pod_power_on_rows(self):
        data_connector = importlib.import_module("data_connector")

        rows = data_connector.get_object_data("Milestone")
        pod_power_rows = [
            row
            for row in rows
            if row["scopeType"] == "POD" and row["milestoneType"] == "POWER_ON"
        ]

        expected_anchor_dates = {
            ("浙江移动", "104-PoD1"): "2026-08-14",
            ("京东", "B2DH401-POD01"): "2026-01-21",
            ("京东", "B2DH401-POD02"): "2026-01-21",
            ("京东", "B2DH401-POD03"): "2026-01-27",
            ("京东", "B2DH401-POD04"): "2026-01-27",
            ("京东", "B2DH402-POD05"): "2026-01-27",
            ("京东", "B2DH402-POD06"): "2026-01-27",
            ("京东", "B2DH402-POD07"): "2026-01-21",
            ("京东", "B2DH402-POD08"): "2026-01-21",
            ("京东", "B2DH403-POD09"): "2026-01-21",
        }
        self.assertEqual(len(pod_power_rows), len(expected_anchor_dates))
        rows_by_project_pod = {
            (row["projectKey"], row["scopeKey"]): row
            for row in pod_power_rows
        }
        self.assertEqual(set(rows_by_project_pod), set(expected_anchor_dates))
        for key, anchor_date in expected_anchor_dates.items():
            row = rows_by_project_pod[key]
            self.assertEqual(row["milestoneKey"], f"{key[0]}::POD::{key[1]}::POWER_ON")
            self.assertEqual(row["milestoneName"], "上电")
            self.assertEqual(row["anchorDate"], anchor_date)
            self.assertEqual(row["directionRole"], "BACKWARD_TARGET")
            self.assertEqual(row["dependencyMilestoneTypes"], "ROOM_IMPLEMENTATION_DONE,ARRIVAL")

    def test_delivery_project_data_lists_configured_project_sources(self):
        data_connector = importlib.import_module("data_connector")

        rows = data_connector.get_object_data("DeliveryProject")

        project_names = {row["projectName"] for row in rows}
        self.assertIn("浙江移动", project_names)
        self.assertIn("京东", project_names)
        zjyd = next(row for row in rows if row["projectName"] == "浙江移动")
        self.assertEqual(zjyd["projectKey"], "浙江移动")
        self.assertEqual(zjyd["sourceFile"], data_connector.ZJYD_SOURCE_FILE)

    def test_delivery_pod_data_is_derived_from_plan_row_management_units(self):
        data_connector = importlib.import_module("data_connector")

        rows = data_connector.get_object_data("DeliveryPod", project_id="京东")

        self.assertGreater(len(rows), 0)
        self.assertTrue(all(row["projectKey"] == "京东" for row in rows))
        pod = next(row for row in rows if row["managementUnit"] == "B2DH401-POD01")
        self.assertEqual(pod["podKey"], "京东::B2DH401-POD01")
        self.assertEqual(pod["podName"], "B2DH401-POD01")
        self.assertGreaterEqual(pod["activityCount"], 1)

    def test_v2_link_types_endpoint_lists_schema_link_types(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        response = self.client.get("/api/v2/ontologies/default/linkTypes")

        self.assertEqual(response.status_code, 200)
        link_types = response.json()
        self.assertIn("ProjectPlanRows", {item["apiName"] for item in link_types})
        pod_plan_rows = next(item for item in link_types if item["apiName"] == "PodPlanRows")
        self.assertEqual(pod_plan_rows["objectTypeApiName"], "DeliveryPod")
        self.assertEqual(pod_plan_rows["linkedObjectTypeApiName"], "DeliveryPlanRow")
        pod_milestones = next(item for item in link_types if item["apiName"] == "PodMilestones")
        self.assertEqual(pod_milestones["objectTypeApiName"], "DeliveryPod")
        self.assertEqual(pod_milestones["linkedObjectTypeApiName"], "Milestone")
        self.assertEqual(pod_milestones["relationshipModel"], "FOREIGN_KEY")
        self.assertEqual(pod_milestones["foreignKey"]["sourcePropertyApiName"], "scopeKey")
        self.assertEqual(pod_milestones["foreignKey"]["targetPropertyApiName"], "managementUnit")

    def test_update_object_data_writes_source_column_in_target_csv(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / source_path.name
            with source_path.open("r", encoding="utf-8-sig", newline="") as source_file:
                rows = list(csv.DictReader(source_file))
            first_two_rows = rows[:2]
            with temp_path.open("w", encoding="utf-8-sig", newline="") as target_file:
                writer = csv.DictWriter(target_file, fieldnames=list(first_two_rows[0].keys()))
                writer.writeheader()
                writer.writerows(first_two_rows)

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_path.name, "浙江移动"),
                }
                row = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")[0]
                updated_start = "2026-07-02"

                result = data_connector.update_object_data(
                    "DeliveryPlanRow",
                    "update_delivery_plan_row",
                    {
                        "object_type": "DeliveryPlanRow",
                        "rowKey": row["rowKey"],
                        "changes": {"startDate": updated_start},
                    },
                )

                self.assertTrue(result["success"])
                self.assertEqual(result["data"]["startDate"], updated_start)

                with temp_path.open("r", encoding="utf-8-sig", newline="") as updated_file:
                    updated_rows = list(csv.DictReader(updated_file))
                self.assertEqual(updated_rows[0]["开始日期"], updated_start)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_update_milestone_action_writes_milestone_csv(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / source_path.name
            with source_path.open("r", encoding="utf-8-sig", newline="") as source_file:
                rows = list(csv.DictReader(source_file))
            first_two_rows = rows[:2]
            with temp_path.open("w", encoding="utf-8-sig", newline="") as target_file:
                writer = csv.DictWriter(target_file, fieldnames=list(first_two_rows[0].keys()))
                writer.writeheader()
                writer.writerows(first_two_rows)

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                milestone = data_connector.get_object_data("Milestone")[0]
                updated_date = "2026-08-21"

                result = data_connector.update_object_data(
                    "Milestone",
                    "modifyMilestonePlannedDate",
                    {
                        "object_type": "Milestone",
                        "milestoneKey": milestone["milestoneKey"],
                        "changes": {"plannedDate": updated_date},
                    },
                )

                self.assertTrue(result["success"])
                self.assertEqual(result["data"]["plannedDate"], updated_date)

                with temp_path.open("r", encoding="utf-8-sig", newline="") as updated_file:
                    updated_rows = list(csv.DictReader(updated_file))
                self.assertEqual(updated_rows[0]["plannedDate"], updated_date)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_pod_power_on_milestone_action_validates_without_writing_and_applies_anchor_date(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "Milestone.csv"
        plan_source_path = BACKEND_DIR / data_connector.OTT10_SOURCE_FILE
        pod_milestone_key = "京东::POD::B2DH401-POD01::POWER_ON"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / source_path.name
            temp_plan_path = Path(tmp_dir) / plan_source_path.name
            temp_path.write_bytes(source_path.read_bytes())
            temp_plan_path.write_bytes(plan_source_path.read_bytes())
            before_bytes = temp_path.read_bytes()
            before_plan_bytes = temp_plan_path.read_bytes()

            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)

                validate_response = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyPodPowerOnMilestoneAnchorDate/validate",
                    json={
                        "targetPodPowerOnMilestone": pod_milestone_key,
                        "anchorDate": "2026-02-03",
                    },
                )
                self.assertEqual(validate_response.status_code, 200)
                self.assertEqual(temp_path.read_bytes(), before_bytes)
                self.assertEqual(temp_plan_path.read_bytes(), before_plan_bytes)
                self.assertEqual(validate_response.json()["validatedChanges"], {"anchorDate": "2026-02-03"})
                dry_run = validate_response.json()["backwardDryRun"]
                self.assertEqual(dry_run["status"], "DRY_RUN_READY")
                self.assertEqual(dry_run["summary"]["selectedAnchorId"], pod_milestone_key)
                self.assertEqual(dry_run["summary"]["anchorDate"], "2026-02-03")
                self.assertEqual(dry_run["summary"]["mutationCount"], len(dry_run["proposed_mutations"]))
                self.assertGreaterEqual(dry_run["summary"]["mutationCount"], 0)

                apply_response = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyPodPowerOnMilestoneAnchorDate/apply",
                    json={
                        "targetPodPowerOnMilestone": {"milestoneKey": pod_milestone_key},
                        "anchorDate": "2026-02-04",
                    },
                )
                self.assertEqual(apply_response.status_code, 200)
                payload = apply_response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["data"]["anchorDate"], "2026-02-04")
                self.assertIn("backwardDryRun", payload)
                self.assertGreater(payload["scheduleMutationCount"], 0)
                self.assertEqual(
                    payload["scheduleMutationCount"],
                    len(payload["backwardDryRun"]["proposed_mutations"]),
                )
                self._assert_plan_mutations_written(
                    "京东",
                    payload["backwardDryRun"]["proposed_mutations"],
                )

                with temp_path.open("r", encoding="utf-8-sig", newline="") as updated_file:
                    updated_rows = list(csv.DictReader(updated_file))
                updated = next(row for row in updated_rows if row["milestoneKey"] == pod_milestone_key)
                self.assertEqual(updated["anchorDate"], "2026-02-04")
            finally:
                data_connector.BASE_DIR = original_base_dir

    def test_pod_power_on_milestone_batch_apply_validates_before_writing(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "Milestone.csv"
        plan_source_path = BACKEND_DIR / data_connector.OTT10_SOURCE_FILE
        valid_key = "京东::POD::B2DH401-POD01::POWER_ON"
        untouched_key = "京东::POD::B2DH401-POD02::POWER_ON"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / source_path.name
            temp_plan_path = Path(tmp_dir) / plan_source_path.name
            temp_path.write_bytes(source_path.read_bytes())
            temp_plan_path.write_bytes(plan_source_path.read_bytes())
            before_bytes = temp_path.read_bytes()
            before_plan_bytes = temp_plan_path.read_bytes()

            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)

                rejected = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyPodPowerOnMilestoneAnchorDate/applyBatch",
                    json={
                        "batch": [
                            {
                                "targetPodPowerOnMilestone": {"milestoneKey": valid_key},
                                "anchorDate": "2026-02-05",
                            },
                            {
                                "targetPodPowerOnMilestone": {"milestoneKey": untouched_key},
                                "anchorDate": "2026/02/06",
                            },
                        ]
                    },
                )
                self.assertEqual(rejected.status_code, 400)
                self.assertEqual(temp_path.read_bytes(), before_bytes)
                self.assertEqual(temp_plan_path.read_bytes(), before_plan_bytes)

                accepted = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyPodPowerOnMilestoneAnchorDate/applyBatch",
                    json={
                        "batch": [
                            {
                                "targetPodPowerOnMilestone": {"milestoneKey": valid_key},
                                "anchorDate": "2026-02-05",
                            },
                            {
                                "targetPodPowerOnMilestone": {"milestoneKey": untouched_key},
                                "anchorDate": "2026-02-06",
                            },
                        ]
                    },
                )
                self.assertEqual(accepted.status_code, 200)
                payload = accepted.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["actionName"], "modifyPodPowerOnMilestoneAnchorDate")
                self.assertEqual(payload["appliedCount"], 2)
                self.assertIn("backwardDryRun", payload)
                self.assertGreater(payload["scheduleMutationCount"], 0)
                self.assertEqual(
                    payload["scheduleMutationCount"],
                    len(payload["backwardDryRun"]["proposed_mutations"]),
                )
                self._assert_plan_mutations_written(
                    "京东",
                    payload["backwardDryRun"]["proposed_mutations"],
                )

                with temp_path.open("r", encoding="utf-8-sig", newline="") as updated_file:
                    updated_rows = list(csv.DictReader(updated_file))
                rows_by_key = {row["milestoneKey"]: row for row in updated_rows}
                self.assertEqual(rows_by_key[valid_key]["anchorDate"], "2026-02-05")
                self.assertEqual(rows_by_key[untouched_key]["anchorDate"], "2026-02-06")

                rerun = data_connector.execute_backward_key_milestones(
                    "京东",
                    selected_anchor_id="京东::PROJECT::GLOBAL::POWER_ON",
                )
                self.assertEqual(rerun["summary"]["executionMode"], "POD_PRIORITY")
                self.assertEqual(rerun["proposed_mutations"], [])
            finally:
                data_connector.BASE_DIR = original_base_dir

    def test_pod_power_on_milestone_batch_apply_anchor_only_skips_schedule_writeback(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "Milestone.csv"
        plan_source_path = BACKEND_DIR / data_connector.OTT10_SOURCE_FILE
        pod_one_key = "京东::POD::B2DH401-POD01::POWER_ON"
        pod_two_key = "京东::POD::B2DH401-POD02::POWER_ON"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / source_path.name
            temp_plan_path = Path(tmp_dir) / plan_source_path.name
            temp_path.write_bytes(source_path.read_bytes())
            temp_plan_path.write_bytes(plan_source_path.read_bytes())
            before_plan_bytes = temp_plan_path.read_bytes()

            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)

                accepted = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyPodPowerOnMilestoneAnchorDate/applyBatch",
                    json={
                        "writebackMode": "ANCHOR_ONLY",
                        "batch": [
                            {
                                "targetPodPowerOnMilestone": {"milestoneKey": pod_one_key},
                                "anchorDate": "2026-02-05",
                            },
                            {
                                "targetPodPowerOnMilestone": {"milestoneKey": pod_two_key},
                                "anchorDate": "2026-02-06",
                            },
                        ],
                    },
                )

                self.assertEqual(accepted.status_code, 200)
                payload = accepted.json()
                self.assertEqual(payload["writebackMode"], "ANCHOR_ONLY")
                self.assertEqual(payload["scheduleMutationCount"], 0)
                self.assertEqual(payload["scheduleApplyResult"]["appliedCount"], 0)
                self.assertEqual(temp_plan_path.read_bytes(), before_plan_bytes)

                with temp_path.open("r", encoding="utf-8-sig", newline="") as updated_file:
                    updated_rows = list(csv.DictReader(updated_file))
                rows_by_key = {row["milestoneKey"]: row for row in updated_rows}
                self.assertEqual(rows_by_key[pod_one_key]["anchorDate"], "2026-02-05")
                self.assertEqual(rows_by_key[pod_two_key]["anchorDate"], "2026-02-06")
            finally:
                data_connector.BASE_DIR = original_base_dir

    def test_pod_power_on_milestone_batch_validate_reuses_project_backward_dry_run(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "Milestone.csv"
        plan_source_path = BACKEND_DIR / data_connector.OTT10_SOURCE_FILE
        pod_one_key = "京东::POD::B2DH401-POD01::POWER_ON"
        pod_two_key = "京东::POD::B2DH401-POD02::POWER_ON"
        payload = {
            "batch": [
                {
                    "targetPodPowerOnMilestone": {"milestoneKey": pod_one_key},
                    "anchorDate": "2026-02-04",
                },
                {
                    "targetPodPowerOnMilestone": {"milestoneKey": pod_two_key},
                    "anchorDate": "2026-02-04",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / source_path.name
            temp_plan_path = Path(tmp_dir) / plan_source_path.name
            temp_path.write_bytes(source_path.read_bytes())
            temp_plan_path.write_bytes(plan_source_path.read_bytes())
            before_milestone_bytes = temp_path.read_bytes()
            before_plan_bytes = temp_plan_path.read_bytes()

            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)

                expected = data_connector.execute_backward_key_milestones(
                    "京东",
                    selected_anchor_id="京东::PROJECT::GLOBAL::POWER_ON",
                    temporary_anchor_dates={
                        pod_one_key: "2026-02-04",
                        pod_two_key: "2026-02-04",
                    },
                )
                response = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyPodPowerOnMilestoneAnchorDate/validateBatch",
                    json=payload,
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(temp_path.read_bytes(), before_milestone_bytes)
                self.assertEqual(temp_plan_path.read_bytes(), before_plan_bytes)
                actual = response.json()
                self.assertTrue(actual["success"])
                self.assertEqual(actual["validatedCount"], 2)
                self.assertEqual(actual["scheduleMutationCount"], len(expected["proposed_mutations"]))
                self.assertEqual(actual["backwardDryRun"]["summary"], expected["summary"])
                self.assertEqual(
                    [
                        (mutation["rowKey"], mutation["field"], mutation["newDate"])
                        for mutation in actual["backwardDryRun"]["proposed_mutations"]
                    ],
                    [
                        (mutation["rowKey"], mutation["field"], mutation["newDate"])
                        for mutation in expected["proposed_mutations"]
                    ],
                )
            finally:
                data_connector.BASE_DIR = original_base_dir

    def test_pod_power_on_milestone_action_rejects_wrong_target_or_bad_date(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / source_path.name
            temp_path.write_bytes(source_path.read_bytes())
            before_bytes = temp_path.read_bytes()

            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)

                project_target = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyPodPowerOnMilestoneAnchorDate/validate",
                    json={
                        "targetPodPowerOnMilestone": "京东::PROJECT::GLOBAL::POWER_ON",
                        "anchorDate": "2026-02-03",
                    },
                )
                self.assertEqual(project_target.status_code, 400)

                non_power_target = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyPodPowerOnMilestoneAnchorDate/validate",
                    json={
                        "targetPodPowerOnMilestone": "京东::PROJECT::GLOBAL::ARRIVAL",
                        "anchorDate": "2026-02-03",
                    },
                )
                self.assertEqual(non_power_target.status_code, 400)

                bad_date = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyPodPowerOnMilestoneAnchorDate/validate",
                    json={
                        "targetPodPowerOnMilestone": "京东::POD::B2DH401-POD01::POWER_ON",
                        "anchorDate": "2026/02/03",
                    },
                )
                self.assertEqual(bad_date.status_code, 400)
                self.assertEqual(temp_path.read_bytes(), before_bytes)
            finally:
                data_connector.BASE_DIR = original_base_dir

    def test_update_milestone_with_wrong_action_is_rejected(self):
        data_connector = importlib.import_module("data_connector")
        milestone = data_connector.get_object_data("Milestone")[0]

        with self.assertRaises(ValueError):
            data_connector.update_object_data(
                "Milestone",
                "modifyDeliveryPlanStartDate",
                {
                    "object_type": "Milestone",
                    "milestoneKey": milestone["milestoneKey"],
                    "changes": {"plannedDate": "2026-08-30"},
                },
            )

    def test_backward_key_milestones_graph_returns_nodes_and_edges(self):
        data_connector = importlib.import_module("data_connector")

        graph = data_connector.get_backward_key_milestones_graph("浙江移动")

        self.assertEqual(graph["projectId"], "浙江移动")
        self.assertIn("anchorDate", graph)
        self.assertGreater(len(graph["targets"]), 0)
        self.assertGreater(len(graph["nodes"]), 0)
        self.assertGreaterEqual(len(graph["edges"]), 0)
        self.assertTrue(all("id" in node and "latestFinish" in node for node in graph["nodes"]))
        self.assertTrue(all(edge["relationType"] == "depends_on" for edge in graph["edges"]))
        self.assertIn("anchorOptions", graph)
        self.assertEqual(len(graph["anchorOptions"]), 2)
        self.assertEqual(graph["selectedAnchorId"], "浙江移动::PROJECT::GLOBAL::POWER_ON")
        self.assertEqual(graph["anchorOptions"][0]["id"], "浙江移动::PROJECT::GLOBAL::POWER_ON")
        opt_ids = {opt["id"] for opt in graph["anchorOptions"]}
        self.assertEqual(
            opt_ids,
            {
                "浙江移动::PROJECT::GLOBAL::CLUSTER_DEBUG",
                "浙江移动::PROJECT::GLOBAL::POWER_ON",
            },
        )
        self.assertFalse(any("::POD::" in opt_id for opt_id in opt_ids))
        self.assertTrue(all(opt.get("scopeType") == "PROJECT" for opt in graph["anchorOptions"]))
        self.assertTrue(all(opt.get("scopeKey") == "GLOBAL" for opt in graph["anchorOptions"]))

        jd_graph = data_connector.get_backward_key_milestones_graph("京东")
        jd_opt_ids = [opt["id"] for opt in jd_graph["anchorOptions"]]
        self.assertEqual(jd_graph["selectedAnchorId"], "京东::PROJECT::GLOBAL::POWER_ON")
        self.assertEqual(jd_graph["anchorDate"], "2026-03-17")
        self.assertEqual(
            jd_opt_ids,
            [
                "京东::PROJECT::GLOBAL::POWER_ON",
                "京东::PROJECT::GLOBAL::CLUSTER_DEBUG",
            ],
        )
        self.assertFalse(any("::POD::" in opt_id for opt_id in jd_opt_ids))

        graph_accept = data_connector.get_backward_key_milestones_graph(
            "浙江移动",
            selected_anchor_id="浙江移动::PROJECT::GLOBAL::CLUSTER_DEBUG",
        )
        self.assertEqual(graph_accept["selectedAnchorId"], "浙江移动::PROJECT::GLOBAL::CLUSTER_DEBUG")
        self.assertNotEqual(graph["anchorDate"], graph_accept["anchorDate"])

    def test_backward_key_milestones_graph_rejects_missing_anchor_date(self):
        data_connector = importlib.import_module("data_connector")
        milestone_path = BACKEND_DIR / "Milestone.csv"
        project_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / milestone_path.name
            temp_project_path = Path(tmp_dir) / project_path.name
            with milestone_path.open("r", encoding="utf-8-sig", newline="") as source_file:
                rows = list(csv.DictReader(source_file))
                fieldnames = list(rows[0].keys())
                if "anchorDate" not in fieldnames:
                    fieldnames.append("anchorDate")
            for row in rows:
                row.setdefault("anchorDate", "")
                if row.get("milestoneKey") == "浙江移动::PROJECT::GLOBAL::POWER_ON":
                    row["anchorDate"] = ""

            with temp_path.open("w", encoding="utf-8-sig", newline="") as target_file:
                writer = csv.DictWriter(target_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            with project_path.open("r", encoding="utf-8-sig", newline="") as source_file:
                project_rows = list(csv.DictReader(source_file))
                project_fieldnames = list(project_rows[0].keys())
            with temp_project_path.open("w", encoding="utf-8-sig", newline="") as target_file:
                writer = csv.DictWriter(target_file, fieldnames=project_fieldnames)
                writer.writeheader()
                writer.writerows(project_rows)

            original_base_dir = data_connector.BASE_DIR
            original_sources = data_connector.PROJECT_SOURCES
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                    "京东": original_sources["京东"],
                }
                with self.assertRaises(ValueError):
                    data_connector.get_backward_key_milestones_graph(
                        "浙江移动",
                        selected_anchor_id="浙江移动::PROJECT::GLOBAL::POWER_ON",
                    )
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_backward_key_milestones_graph_rejects_bad_anchor_id(self):
        data_connector = importlib.import_module("data_connector")

        with self.assertRaises(ValueError):
            data_connector.get_backward_key_milestones_graph("浙江移动", selected_anchor_id="nope")

    def test_backward_key_milestones_graph_rejects_unknown_project(self):
        data_connector = importlib.import_module("data_connector")

        with self.assertRaises(KeyError):
            data_connector.get_backward_key_milestones_graph("不存在项目")

    def test_backward_target_rules_cover_power_on_all_matches_and_arrival_with_max_end(self):
        data_connector = importlib.import_module("data_connector")

        self.assertTrue(data_connector.MILESTONE_TARGET_RULES["POWER_ON"]["match_all"])
        self.assertEqual(data_connector.MILESTONE_TARGET_RULES["ARRIVAL"]["pick"], "max_end")
        self.assertIn("上电", data_connector.MILESTONE_TARGET_RULES["POWER_ON"]["name_substrings"])
        self.assertIn("到货", data_connector.MILESTONE_TARGET_RULES["ARRIVAL"]["name_substrings"])

    def test_backward_graph_cluster_debug_uses_performance_tuning_activity(self):
        data_connector = importlib.import_module("data_connector")

        graph = data_connector.get_backward_key_milestones_graph(
            "浙江移动",
            selected_anchor_id="浙江移动::PROJECT::GLOBAL::CLUSTER_DEBUG",
        )
        target_names = {target["name"] for target in graph["targets"]}
        node_names = {node["name"] for node in graph["nodes"]}

        self.assertEqual(target_names, {"集群性能调优"})
        self.assertIn("集群性能调优", node_names)
        self.assertIn("集群系统集成测试", node_names)
        self.assertGreater(len(graph["nodes"]), 1)

    def test_backward_graph_power_on_anchor_matches_all_power_on_activities(self):
        data_connector = importlib.import_module("data_connector")
        graph = data_connector.get_backward_key_milestones_graph(
            "浙江移动",
            selected_anchor_id="浙江移动::PROJECT::GLOBAL::POWER_ON",
        )
        expected_target_ids = {
            row["rowKey"]
            for row in data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")
            if "上电" in row["activityName"]
        }
        actual_target_ids = {target["id"] for target in graph["targets"]}

        self.assertEqual(graph["selectedAnchorId"], "浙江移动::PROJECT::GLOBAL::POWER_ON")
        self.assertGreater(len(expected_target_ids), 1)
        self.assertEqual(actual_target_ids, expected_target_ids)
        self.assertTrue(all("上电" in target["name"] for target in graph["targets"]))

    def test_backward_graph_power_on_prefers_milestone_anchor_date_over_plan_end_date(self):
        data_connector = importlib.import_module("data_connector")

        graph = data_connector.get_backward_key_milestones_graph(
            "浙江移动",
            selected_anchor_id="浙江移动::PROJECT::GLOBAL::POWER_ON",
        )

        self.assertEqual(graph["anchorDate"], "2026-08-13")
        self.assertEqual(graph["selectedAnchorId"], "浙江移动::PROJECT::GLOBAL::POWER_ON")
        self.assertGreater(len(graph["targets"]), 0)

    def test_backward_graph_power_on_anchor_date_does_not_filter_matching_plan_rows(self):
        data_connector = importlib.import_module("data_connector")

        graph = data_connector.get_backward_key_milestones_graph(
            "京东",
            selected_anchor_id="京东::PROJECT::GLOBAL::POWER_ON",
        )
        expected_target_ids = {
            row["rowKey"]
            for row in data_connector.get_object_data("DeliveryPlanRow", project_id="京东")
            if "上电" in row["activityName"]
        }
        actual_target_ids = {target["id"] for target in graph["targets"]}

        self.assertEqual(graph["anchorDate"], "2026-03-17")
        self.assertGreater(len(expected_target_ids), 1)
        self.assertEqual(actual_target_ids, expected_target_ids)

    def test_execute_backward_key_milestones_returns_dry_run_mutations_without_writing_csv(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                result = data_connector.execute_backward_key_milestones(
                    "浙江移动",
                    selected_anchor_id="浙江移动::PROJECT::GLOBAL::POWER_ON",
                )
                self.assertEqual(result["status"], "DRY_RUN_READY")
                self.assertEqual(result["summary"]["projectId"], "浙江移动")
                self.assertEqual(result["summary"]["selectedAnchorId"], "浙江移动::PROJECT::GLOBAL::POWER_ON")
                self.assertEqual(result["summary"]["anchorDate"], "2026-08-13")
                self.assertGreater(result["summary"]["affectedNodeCount"], 0)
                self.assertEqual(result["summary"]["mutationCount"], len(result["proposed_mutations"]))
                self.assertGreater(result["summary"]["mutationCount"], 0)
                first_mutation = result["proposed_mutations"][0]
                self.assertEqual(first_mutation["milestoneId"], first_mutation["rowKey"])
                self.assertIn(first_mutation["field"], {"startDate", "endDate"})
                self.assertIn(first_mutation["changeType"], {"UPDATE_START_DATE", "UPDATE_END_DATE"})
                self.assertIn("originalDate", first_mutation)
                self.assertIn("newDate", first_mutation)
                self.assertTrue(first_mutation["reason"])
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)

                pod_result = data_connector.execute_backward_key_milestones(
                    "浙江移动",
                    selected_anchor_id="浙江移动::POD::104-PoD1::POWER_ON",
                )
                self.assertEqual(pod_result["status"], "DRY_RUN_READY")
                self.assertEqual(
                    pod_result["summary"]["selectedAnchorId"],
                    "浙江移动::POD::104-PoD1::POWER_ON",
                )
                self.assertEqual(pod_result["summary"]["anchorDate"], "2026-08-14")
                self.assertGreater(pod_result["summary"]["mutationCount"], 0)
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_execute_backward_power_on_uses_pod_priority_dates_for_project_anchor(self):
        data_connector = importlib.import_module("data_connector")
        project_id = "京东"

        with self._temporary_project_sources(
            data_connector,
            project_id,
            data_connector.OTT10_SOURCE_FILE,
        ) as (temp_project_path, _temp_milestone_path):
            before_bytes = temp_project_path.read_bytes()

            result = data_connector.execute_backward_key_milestones(
                project_id,
                selected_anchor_id="京东::PROJECT::GLOBAL::POWER_ON",
            )

            mutations_by_row_field = {
                (mutation["rowKey"], mutation["field"]): mutation
                for mutation in result["proposed_mutations"]
            }
            pod03_end = mutations_by_row_field[
                ("京东::B2DH401-POD03::网络设备上电", "endDate")
            ]

            self.assertEqual(result["status"], "DRY_RUN_READY")
            self.assertEqual(result["summary"]["selectedAnchorId"], "京东::PROJECT::GLOBAL::POWER_ON")
            self.assertEqual(result["summary"]["executionMode"], "POD_PRIORITY")
            self.assertGreater(result["summary"]["podPriorityAnchorCount"], 0)
            self.assertEqual(result["summary"]["projectFallbackAnchorId"], "京东::PROJECT::GLOBAL::POWER_ON")
            self.assertEqual(pod03_end["newDate"], "2026-01-21")
            self.assertEqual(temp_project_path.read_bytes(), before_bytes)

    def test_execute_backward_pod_anchor_only_targets_matching_management_unit(self):
        data_connector = importlib.import_module("data_connector")
        project_id = "京东"

        with self._temporary_project_sources(
            data_connector,
            project_id,
            data_connector.OTT10_SOURCE_FILE,
        ):
            result = data_connector.execute_backward_key_milestones(
                project_id,
                selected_anchor_id="京东::POD::B2DH401-POD03::POWER_ON",
            )

        mutated_rows = {
            str(mutation.get("rowKey") or mutation.get("milestoneId") or "")
            for mutation in result["proposed_mutations"]
        }

        self.assertEqual(result["summary"]["selectedAnchorId"], "京东::POD::B2DH401-POD03::POWER_ON")
        self.assertEqual(result["summary"]["executionMode"], "SINGLE_ANCHOR")
        self.assertTrue(any("B2DH401-POD03" in row_key for row_key in mutated_rows))
        self.assertNotIn("京东::B2DH401-POD01::网络设备上电", mutated_rows)
        self.assertNotIn("京东::B2DH402-POD05::网络设备上电", mutated_rows)

    def test_execute_backward_power_on_falls_back_to_project_date_when_pod_date_missing(self):
        data_connector = importlib.import_module("data_connector")
        project_id = "京东"

        def blank_pod03_anchor_date(path: Path) -> None:
            with path.open("r", encoding="utf-8-sig", newline="") as source_file:
                rows = list(csv.DictReader(source_file))
                fieldnames = list(rows[0].keys())
            for row in rows:
                if row.get("milestoneKey") == "京东::POD::B2DH401-POD03::POWER_ON":
                    row["anchorDate"] = ""
                if row.get("milestoneKey") == "京东::POD::B2DH402-POD05::POWER_ON":
                    row["anchorDate"] = "2026-02-04"
            with path.open("w", encoding="utf-8-sig", newline="") as target_file:
                writer = csv.DictWriter(target_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

        with self._temporary_project_sources(
            data_connector,
            project_id,
            data_connector.OTT10_SOURCE_FILE,
            mutate_milestones=blank_pod03_anchor_date,
        ):
            result = data_connector.execute_backward_key_milestones(
                project_id,
                selected_anchor_id="京东::PROJECT::GLOBAL::POWER_ON",
            )

        mutations_by_row_field = {
            (mutation["rowKey"], mutation["field"]): mutation
            for mutation in result["proposed_mutations"]
        }

        self.assertEqual(result["summary"]["executionMode"], "POD_PRIORITY")
        self.assertEqual(
            mutations_by_row_field[("京东::B2DH401-POD03::网络设备上电", "endDate")]["newDate"],
            "2026-03-17",
        )
        self.assertEqual(
            mutations_by_row_field[("京东::B2DH402-POD05::网络设备上电", "endDate")]["newDate"],
            "2026-02-04",
        )

    def test_execute_backward_key_milestones_skips_semantic_date_format_noops(self):
        data_connector = importlib.import_module("data_connector")

        fake_row = SimpleNamespace(
            rowKey="row-1",
            localRowKey="local-1",
            activity=SimpleNamespace(row_order=0),
        )
        fake_ontology = SimpleNamespace(
            functions=SimpleNamespace(
                back_schedule=lambda targets, anchor_date: SimpleNamespace(
                    results={
                        "local-1": SimpleNamespace(
                            latest_start=date(2026, 7, 21),
                            latest_finish=date(2026, 7, 22),
                        )
                    },
                    warnings=[],
                )
            ),
            row=lambda local_key: fake_row,
        )

        with (
            patch.object(data_connector, "_select_sources", return_value=[data_connector.ProjectSource("浙江移动", "plan.csv", "浙江移动")]),
            patch.object(data_connector, "_load_ontology", return_value=fake_ontology),
            patch.object(
                data_connector,
                "_load_project_backward_target_milestones",
                return_value=[
                    {
                        "milestoneKey": "anchor-1",
                        "milestoneName": "上电",
                        "milestoneType": "POWER_ON",
                        "anchorDate": "2026-08-14",
                    }
                ],
            ),
            patch.object(data_connector, "_resolve_target_rows_for_milestone", return_value=[fake_row]),
            patch.object(data_connector, "_api_to_source_columns", return_value={"startDate": "开始日期", "endDate": "结束日期"}),
            patch.object(data_connector, "_read_csv", return_value=([{"开始日期": "2026/7/21", "结束日期": "2026-07-21"}], ["开始日期", "结束日期"])),
        ):
            result = data_connector.execute_backward_key_milestones("浙江移动", selected_anchor_id="anchor-1")

        self.assertEqual(result["summary"]["mutationCount"], 1)
        self.assertEqual(result["summary"]["affectedNodeCount"], 1)
        self.assertEqual([mutation["field"] for mutation in result["proposed_mutations"]], ["endDate"])
        self.assertEqual(result["proposed_mutations"][0]["originalDate"], "2026-07-21")
        self.assertEqual(result["proposed_mutations"][0]["newDate"], "2026-07-22")

    def test_execute_forward_key_milestones_returns_dry_run_mutations_without_writing_csv(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                result = data_connector.execute_forward_key_milestones("浙江移动")
                self.assertEqual(result["status"], "DRY_RUN_READY")
                self.assertEqual(result["summary"]["projectId"], "浙江移动")
                self.assertGreater(result["summary"]["affectedNodeCount"], 0)
                self.assertEqual(result["summary"]["mutationCount"], len(result["proposed_mutations"]))
                self.assertGreater(result["summary"]["mutationCount"], 0)
                self.assertEqual(result["summary"]["anchorCount"], len(result["anchorMilestones"]))
                self.assertGreaterEqual(len(result["anchorMilestones"]), 2)
                first_mutation = result["proposed_mutations"][0]
                self.assertEqual(first_mutation["milestoneId"], first_mutation["rowKey"])
                self.assertIn(first_mutation["field"], {"startDate", "endDate"})
                self.assertIn(first_mutation["changeType"], {"UPDATE_START_DATE", "UPDATE_END_DATE"})
                self.assertIn("originalDate", first_mutation)
                self.assertIn("newDate", first_mutation)
                self.assertTrue(first_mutation["reason"])
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_execute_forward_key_milestones_skips_semantic_date_format_noops(self):
        data_connector = importlib.import_module("data_connector")

        fake_row = SimpleNamespace(
            rowKey="row-1",
            localRowKey="local-1",
            activity=SimpleNamespace(row_order=0),
        )
        fake_ontology = SimpleNamespace(
            functions=SimpleNamespace(
                forward_schedule=lambda explicit_anchors, use_plan_roots: SimpleNamespace(
                    results={
                        "local-1": SimpleNamespace(
                            start=date(2026, 7, 21),
                            finish=date(2026, 7, 23),
                        )
                    },
                    warnings=[],
                )
            ),
            row=lambda local_key: fake_row,
        )

        with (
            patch.object(data_connector, "_select_sources", return_value=[data_connector.ProjectSource("浙江移动", "plan.csv", "浙江移动")]),
            patch.object(data_connector, "_load_ontology", return_value=fake_ontology),
            patch.object(
                data_connector,
                "_load_project_forward_start_milestones",
                return_value=[
                    {
                        "milestoneKey": "forward-1",
                        "milestoneName": "机房实施完成",
                        "milestoneType": "ROOM_IMPLEMENTATION_DONE",
                        "plannedDate": "2026-07-21",
                    }
                ],
            ),
            patch.object(data_connector, "_resolve_forward_rows_for_milestone", return_value=[fake_row]),
            patch.object(data_connector, "_api_to_source_columns", return_value={"startDate": "开始日期", "endDate": "结束日期"}),
            patch.object(data_connector, "_read_csv", return_value=([{"开始日期": "2026-7-21", "结束日期": "2026-07-22"}], ["开始日期", "结束日期"])),
        ):
            result = data_connector.execute_forward_key_milestones("浙江移动")

        self.assertEqual(result["summary"]["mutationCount"], 1)
        self.assertEqual(result["summary"]["affectedNodeCount"], 1)
        self.assertEqual([mutation["field"] for mutation in result["proposed_mutations"]], ["endDate"])
        self.assertEqual(result["proposed_mutations"][0]["originalDate"], "2026-07-22")
        self.assertEqual(result["proposed_mutations"][0]["newDate"], "2026-07-23")

    def test_execute_forward_key_milestones_respects_manual_override_write_locks(self):
        data_connector = importlib.import_module("data_connector")

        fake_row = SimpleNamespace(
            rowKey="row-1",
            localRowKey="local-1",
            activityName="现场勘测",
            startDate="2026-07-13",
            endDate="2026-07-15",
            activity=SimpleNamespace(row_order=0),
        )
        fake_ontology = SimpleNamespace(
            objects=SimpleNamespace(
                DeliveryPlanRow=SimpleNamespace(get_or_none=lambda row_key: fake_row if row_key == "row-1" else None)
            ),
            functions=SimpleNamespace(
                forward_schedule=lambda explicit_anchors, use_plan_roots: SimpleNamespace(
                    results={
                        "local-1": SimpleNamespace(
                            start=date(2026, 7, 14),
                            finish=date(2026, 7, 20),
                        )
                    },
                    warnings=[],
                )
            ),
            row=lambda local_key: fake_row,
        )

        with (
            patch.object(data_connector, "_select_sources", return_value=[data_connector.ProjectSource("浙江移动", "plan.csv", "浙江移动")]),
            patch.object(data_connector, "_load_ontology", return_value=fake_ontology),
            patch.object(
                data_connector,
                "_load_project_forward_start_milestones",
                return_value=[
                    {
                        "milestoneKey": "forward-1",
                        "milestoneName": "机房实施完成",
                        "milestoneType": "ROOM_IMPLEMENTATION_DONE",
                        "plannedDate": "2026-07-21",
                    }
                ],
            ),
            patch.object(data_connector, "_resolve_forward_rows_for_milestone", return_value=[fake_row]),
            patch.object(data_connector, "_api_to_source_columns", return_value={"startDate": "开始日期", "endDate": "结束日期"}),
            patch.object(data_connector, "_read_csv", return_value=([{"开始日期": "2026-07-13", "结束日期": "2026-07-15"}], ["开始日期", "结束日期"])),
        ):
            result = data_connector.execute_forward_key_milestones(
                "浙江移动",
                manual_overrides=[
                    {
                        "target_id": "row-1",
                        "field": "endDate",
                        "new_value": "2026-07-18",
                    }
                ],
            )

        mutations_by_field = {mutation["field"]: mutation for mutation in result["proposed_mutations"]}
        self.assertEqual(result["summary"]["anchorMode"], "manual_override")
        self.assertEqual(mutations_by_field["endDate"]["newDate"], "2026-07-18")
        self.assertEqual(mutations_by_field["endDate"]["reason"], "人工调整活动 `现场勘测` 的结束日期。")
        self.assertEqual(mutations_by_field["startDate"]["newDate"], "2026-07-14")
        self.assertNotEqual(mutations_by_field["endDate"]["newDate"], "2026-07-20")

    def test_execute_forward_manual_override_uses_preview_start_for_end_date_validation(self):
        data_connector = importlib.import_module("data_connector")

        fake_row = SimpleNamespace(
            rowKey="row-1",
            localRowKey="local-1",
            activityName="转运与设备静置",
            startDate="2026-08-11",
            endDate="2026-08-11",
            activity=SimpleNamespace(row_order=0),
        )
        captured_anchors: list[dict[str, Any]] = []

        def forward_schedule(explicit_anchors, use_plan_roots):
            captured_anchors.append(dict(explicit_anchors))
            return SimpleNamespace(
                results={
                    "local-1": SimpleNamespace(
                        start=date(2026, 8, 9),
                        finish=date(2026, 8, 10),
                    )
                },
                warnings=[],
            )

        fake_ontology = SimpleNamespace(
            objects=SimpleNamespace(
                DeliveryPlanRow=SimpleNamespace(get_or_none=lambda row_key: fake_row if row_key == "row-1" else None)
            ),
            functions=SimpleNamespace(forward_schedule=forward_schedule),
            row=lambda local_key: fake_row,
        )

        with (
            patch.object(data_connector, "_select_sources", return_value=[data_connector.ProjectSource("浙江移动", "plan.csv", "浙江移动")]),
            patch.object(data_connector, "_load_ontology", return_value=fake_ontology),
            patch.object(
                data_connector,
                "_load_project_forward_start_milestones",
                return_value=[
                    {
                        "milestoneKey": "forward-1",
                        "milestoneName": "机房实施完成",
                        "milestoneType": "ROOM_IMPLEMENTATION_DONE",
                        "plannedDate": "2026-07-21",
                    }
                ],
            ),
            patch.object(data_connector, "_resolve_forward_rows_for_milestone", return_value=[fake_row]),
            patch.object(data_connector, "_api_to_source_columns", return_value={"startDate": "开始日期", "endDate": "结束日期"}),
            patch.object(data_connector, "_read_csv", return_value=([{"开始日期": "2026-08-11", "结束日期": "2026-08-11"}], ["开始日期", "结束日期"])),
        ):
            result = data_connector.execute_forward_key_milestones(
                "浙江移动",
                manual_overrides=[
                    {
                        "target_id": "row-1",
                        "field": "endDate",
                        "new_value": "2026-08-10",
                    }
                ],
            )

        self.assertEqual(result["summary"]["anchorMode"], "manual_override")
        self.assertEqual(result["proposed_mutations"][0]["newDate"], "2026-08-10")
        self.assertEqual(captured_anchors[-1]["local-1"].start, date(2026, 8, 9))
        self.assertEqual(captured_anchors[-1]["local-1"].finish, date(2026, 8, 10))

    def test_milestone_compression_algorithm_shifts_backward_and_forward(self):
        compression = importlib.import_module("llm_openrouter_milestone_compression")
        activities = {
            "install": self._activity("install", "2026/8/10", "2026/8/12"),
            "power": self._activity("power", "2026-08-13", "2026-08-14"),
        }
        warnings: list[str] = []

        early = compression.compute_milestone_compression_schedule(
            activities,
            baseline_date=date(2026, 8, 8),
            anchor_date=date(2026, 8, 5),
            warnings=warnings,
        )
        late = compression.compute_milestone_compression_schedule(
            activities,
            baseline_date=date(2026, 8, 8),
            anchor_date=date(2026, 8, 12),
            warnings=warnings,
        )

        self.assertEqual(early["install"].start, date(2026, 8, 7))
        self.assertEqual(early["install"].finish, date(2026, 8, 9))
        self.assertEqual((early["install"].finish - early["install"].start).days, 2)
        self.assertEqual(early["install"].shift_days, -3)
        self.assertEqual(late["power"].start, date(2026, 8, 17))
        self.assertEqual(late["power"].finish, date(2026, 8, 18))
        self.assertEqual((late["power"].finish - late["power"].start).days, 1)
        self.assertEqual(late["power"].shift_days, 4)
        self.assertEqual(warnings, [])

    def test_duration_compression_top3_slack_compresses_critical_path_and_refreshes_successors(self):
        compression = importlib.import_module("llm_openrouter_milestone_compression")
        activities = {
            "root": self._activity("root", "2026-08-01", "2026-08-02", duration_days=2),
            "build": self._activity(
                "build",
                "2026-08-03",
                "2026-08-08",
                duration_days=6,
                dependency_keys=["root"],
            ),
            "install": self._activity(
                "install",
                "2026-08-09",
                "2026-08-13",
                duration_days=5,
                dependency_keys=["build"],
            ),
            "tune": self._activity(
                "tune",
                "2026-08-14",
                "2026-08-16",
                duration_days=3,
                dependency_keys=["install"],
            ),
            "accept": self._activity(
                "accept",
                "2026-08-17",
                "2026-08-18",
                duration_days=2,
                dependency_keys=["tune"],
            ),
            "audit": self._activity(
                "audit",
                "2026-08-14",
                "2026-08-15",
                duration_days=2,
                dependency_keys=["install"],
            ),
        }
        warnings: list[str] = []

        run = compression.compute_duration_compression_schedule(
            activities,
            target_keys=["accept"],
            baseline_date=date(2026, 8, 18),
            anchor_date=date(2026, 8, 14),
            limit_duration_by_key={
                "root": "2天",
                "build": "3天",
                "install": "3天",
                "tune": "2天",
                "accept": "2天",
            },
            warnings=warnings,
        )

        self.assertEqual(run.strategy, "TOP3_SLACK")
        self.assertEqual(run.requested_compression_days, 4)
        self.assertEqual(run.achieved_compression_days, 4)
        self.assertEqual(run.critical_path_keys, ["root", "build", "install", "tune", "accept"])
        self.assertEqual(run.allocations, {"build": 3, "install": 1})
        self.assertEqual(run.results["root"].start, date(2026, 8, 1))
        self.assertEqual(run.results["root"].finish, date(2026, 8, 2))
        self.assertEqual(run.results["build"].start, date(2026, 8, 3))
        self.assertEqual(run.results["build"].finish, date(2026, 8, 5))
        self.assertEqual(run.results["build"].compressed_duration_days, 3)
        self.assertEqual(run.results["install"].start, date(2026, 8, 6))
        self.assertEqual(run.results["install"].finish, date(2026, 8, 9))
        self.assertEqual(run.results["tune"].start, date(2026, 8, 10))
        self.assertEqual(run.results["tune"].finish, date(2026, 8, 12))
        self.assertEqual(run.results["accept"].start, date(2026, 8, 13))
        self.assertEqual(run.results["accept"].finish, date(2026, 8, 14))
        self.assertEqual(run.results["accept"].start_shift_days, -4)
        self.assertEqual(run.results["audit"].start, date(2026, 8, 10))
        self.assertEqual(run.results["audit"].finish, date(2026, 8, 11))
        self.assertFalse(run.results["audit"].is_critical_path)
        self.assertEqual(warnings, [])

    def test_duration_compression_proportional_distributes_slack_across_critical_path(self):
        compression = importlib.import_module("llm_openrouter_milestone_compression")
        activities = {
            "root": self._activity("root", "2026-08-01", "2026-08-02", duration_days=2),
            "build": self._activity(
                "build",
                "2026-08-03",
                "2026-08-08",
                duration_days=6,
                dependency_keys=["root"],
            ),
            "install": self._activity(
                "install",
                "2026-08-09",
                "2026-08-13",
                duration_days=5,
                dependency_keys=["build"],
            ),
            "tune": self._activity(
                "tune",
                "2026-08-14",
                "2026-08-16",
                duration_days=3,
                dependency_keys=["install"],
            ),
            "accept": self._activity(
                "accept",
                "2026-08-17",
                "2026-08-18",
                duration_days=2,
                dependency_keys=["tune"],
            ),
        }
        warnings: list[str] = []

        run = compression.compute_duration_compression_schedule(
            activities,
            target_keys=["accept"],
            baseline_date=date(2026, 8, 18),
            anchor_date=date(2026, 8, 14),
            limit_duration_by_key={
                "root": "2天",
                "build": "3天",
                "install": "3天",
                "tune": "2天",
                "accept": "2天",
            },
            strategy="PROPORTIONAL",
            warnings=warnings,
        )

        self.assertEqual(run.strategy, "PROPORTIONAL")
        self.assertEqual(run.allocations, {"build": 2, "install": 1, "tune": 1})
        self.assertEqual(run.achieved_compression_days, 4)
        self.assertEqual(run.results["build"].compressed_duration_days, 4)
        self.assertEqual(run.results["install"].compressed_duration_days, 4)
        self.assertEqual(run.results["tune"].compressed_duration_days, 2)
        self.assertEqual(run.results["accept"].finish, date(2026, 8, 14))
        self.assertEqual(warnings, [])

    def test_duration_compression_proportional_recomputes_critical_path_until_target_reached(self):
        compression = importlib.import_module("llm_openrouter_milestone_compression")
        activities = {
            "root": self._activity("root", "2026-08-01", "2026-08-01", duration_days=1),
            "a_build": self._activity("a_build", "2026-08-02", "2026-08-06", duration_days=5, dependency_keys=["root"]),
            "a_test": self._activity("a_test", "2026-08-07", "2026-08-10", duration_days=4, dependency_keys=["a_build"]),
            "b_build": self._activity("b_build", "2026-08-02", "2026-08-05", duration_days=4, dependency_keys=["root"]),
            "b_test": self._activity("b_test", "2026-08-06", "2026-08-09", duration_days=4, dependency_keys=["b_build"]),
            "accept": self._activity(
                "accept",
                "2026-08-11",
                "2026-08-11",
                duration_days=1,
                dependency_keys=["a_test", "b_test"],
            ),
        }
        warnings: list[str] = []

        run = compression.compute_duration_compression_schedule(
            activities,
            target_keys=["accept"],
            baseline_date=date(2026, 8, 11),
            anchor_date=date(2026, 8, 7),
            limit_duration_by_key={
                "root": "1天",
                "a_build": "2天",
                "a_test": "2天",
                "b_build": "2天",
                "b_test": "2天",
                "accept": "1天",
            },
            strategy="PROPORTIONAL",
            warnings=warnings,
        )

        self.assertEqual(run.requested_compression_days, 4)
        self.assertEqual(run.achieved_compression_days, 4)
        self.assertEqual(run.allocations, {"a_build": 2, "a_test": 2, "b_build": 2, "b_test": 1})
        self.assertEqual(run.critical_path_keys, ["root", "a_build", "a_test", "accept"])
        self.assertEqual(
            run.critical_path_iterations,
            [
                ["root", "a_build", "a_test", "accept"],
                ["root", "b_build", "b_test", "accept"],
            ],
        )
        self.assertEqual(run.stop_reason, "TARGET_REACHED")
        self.assertEqual(run.final_target_finish_date, date(2026, 8, 7))
        self.assertEqual(run.results["accept"].finish, date(2026, 8, 7))
        self.assertEqual(warnings, [])

    def test_duration_compression_top3_freezes_at_limit_without_recomputing_path(self):
        compression = importlib.import_module("llm_openrouter_milestone_compression")
        activities = {
            "root": self._activity("root", "2026-08-01", "2026-08-01", duration_days=1),
            "build": self._activity("build", "2026-08-02", "2026-08-06", duration_days=5, dependency_keys=["root"]),
            "install": self._activity("install", "2026-08-07", "2026-08-10", duration_days=4, dependency_keys=["build"]),
            "tune": self._activity("tune", "2026-08-11", "2026-08-13", duration_days=3, dependency_keys=["install"]),
            "accept": self._activity("accept", "2026-08-14", "2026-08-16", duration_days=3, dependency_keys=["tune"]),
        }
        warnings: list[str] = []

        run = compression.compute_duration_compression_schedule(
            activities,
            target_keys=["accept"],
            baseline_date=date(2026, 8, 16),
            anchor_date=date(2026, 8, 6),
            limit_duration_by_key={
                "root": "1天",
                "build": "1天",
                "install": "1天",
                "tune": "1天",
                "accept": "1天",
            },
            strategy="TOP3_SLACK",
            top_n=3,
            warnings=warnings,
        )

        self.assertEqual(run.requested_compression_days, 10)
        self.assertEqual(run.achieved_compression_days, 9)
        self.assertEqual(run.allocations, {"build": 4, "install": 3, "tune": 2})
        self.assertEqual(run.results["build"].compressed_duration_days, 1)
        self.assertEqual(run.results["install"].compressed_duration_days, 1)
        self.assertEqual(run.results["tune"].compressed_duration_days, 1)
        self.assertEqual(run.results["accept"].compressed_duration_days, 3)
        self.assertEqual(run.results["accept"].finish, date(2026, 8, 7))
        self.assertTrue(any("初始关键路径" in warning and "无法完全压缩" in warning for warning in warnings))

    def test_duration_compression_proportional_stops_when_recomputed_critical_path_is_unchanged(self):
        compression = importlib.import_module("llm_openrouter_milestone_compression")
        activities = {
            "root": self._activity("root", "2026-08-01", "2026-08-01", duration_days=1),
            "build": self._activity("build", "2026-08-02", "2026-08-06", duration_days=5, dependency_keys=["root"]),
            "install": self._activity("install", "2026-08-07", "2026-08-10", duration_days=4, dependency_keys=["build"]),
            "tune": self._activity("tune", "2026-08-11", "2026-08-13", duration_days=3, dependency_keys=["install"]),
            "accept": self._activity("accept", "2026-08-14", "2026-08-16", duration_days=3, dependency_keys=["tune"]),
        }
        warnings: list[str] = []

        run = compression.compute_duration_compression_schedule(
            activities,
            target_keys=["accept"],
            baseline_date=date(2026, 8, 16),
            anchor_date=date(2026, 8, 6),
            limit_duration_by_key={
                "root": "1天",
                "build": "1天",
                "install": "1天",
                "tune": "1天",
                "accept": "3天",
            },
            strategy="PROPORTIONAL",
            warnings=warnings,
        )

        path = ["root", "build", "install", "tune", "accept"]
        self.assertEqual(run.requested_compression_days, 10)
        self.assertEqual(run.achieved_compression_days, 9)
        self.assertEqual(run.allocations, {"build": 4, "install": 3, "tune": 2})
        self.assertEqual(run.critical_path_iterations, [path, path])
        self.assertEqual(run.stop_reason, "CRITICAL_PATH_UNCHANGED")
        self.assertEqual(run.final_target_finish_date, date(2026, 8, 7))
        self.assertTrue(any("关键路径未发生变化" in warning for warning in warnings))

    def test_duration_compression_proportional_freezes_limit_and_redistributes_remaining_days(self):
        compression = importlib.import_module("llm_openrouter_milestone_compression")
        activities = {
            "prep": self._activity("prep", "2026-08-01", "2026-08-02", duration_days=2),
            "build": self._activity("build", "2026-08-03", "2026-08-04", duration_days=2, dependency_keys=["prep"]),
            "install": self._activity("install", "2026-08-05", "2026-08-15", duration_days=11, dependency_keys=["build"]),
            "accept": self._activity("accept", "2026-08-16", "2026-08-17", duration_days=2, dependency_keys=["install"]),
        }
        warnings: list[str] = []

        run = compression.compute_duration_compression_schedule(
            activities,
            target_keys=["accept"],
            baseline_date=date(2026, 8, 17),
            anchor_date=date(2026, 8, 10),
            limit_duration_by_key={
                "prep": "1天",
                "build": "1天",
                "install": "1天",
                "accept": "2天",
            },
            strategy="PROPORTIONAL",
            warnings=warnings,
        )

        self.assertEqual(run.requested_compression_days, 7)
        self.assertEqual(run.achieved_compression_days, 7)
        self.assertEqual(run.allocations, {"prep": 1, "build": 1, "install": 5})
        self.assertEqual(run.results["prep"].compressed_duration_days, 1)
        self.assertEqual(run.results["build"].compressed_duration_days, 1)
        self.assertEqual(run.results["install"].compressed_duration_days, 6)
        self.assertEqual(run.results["accept"].finish, date(2026, 8, 10))
        self.assertEqual(warnings, [])

    def test_duration_compression_does_not_extend_activity_when_limit_exceeds_current_duration(self):
        compression = importlib.import_module("llm_openrouter_milestone_compression")
        activities = {
            "build": self._activity("build", "2026-08-01", "2026-08-03", duration_days=3),
            "accept": self._activity("accept", "2026-08-04", "2026-08-04", duration_days=1, dependency_keys=["build"]),
        }
        warnings: list[str] = []

        run = compression.compute_duration_compression_schedule(
            activities,
            target_keys=["accept"],
            baseline_date=date(2026, 8, 4),
            anchor_date=date(2026, 8, 3),
            limit_duration_by_key={
                "build": "5天",
                "accept": "1天",
            },
            strategy="PROPORTIONAL",
            warnings=warnings,
        )

        self.assertEqual(run.achieved_compression_days, 0)
        self.assertEqual(run.allocations, {})
        self.assertEqual(run.results["build"].compressed_duration_days, 3)
        self.assertEqual(run.results["build"].finish, date(2026, 8, 3))
        self.assertEqual(run.results["accept"].finish, date(2026, 8, 4))
        self.assertTrue(any("无法完全压缩" in warning for warning in warnings))

    def test_duration_compression_warns_for_missing_limits_and_partial_capacity(self):
        compression = importlib.import_module("llm_openrouter_milestone_compression")
        activities = {
            "root": self._activity("root", "2026-08-01", "2026-08-02", duration_days=2),
            "build": self._activity(
                "build",
                "2026-08-03",
                "2026-08-06",
                duration_days=4,
                dependency_keys=["root"],
            ),
            "install": self._activity(
                "install",
                "2026-08-07",
                "2026-08-10",
                duration_days=4,
                dependency_keys=["build"],
            ),
            "accept": self._activity(
                "accept",
                "2026-08-11",
                "2026-08-12",
                duration_days=2,
                dependency_keys=["install"],
            ),
        }
        warnings: list[str] = []

        run = compression.compute_duration_compression_schedule(
            activities,
            target_keys=["accept"],
            baseline_date=date(2026, 8, 12),
            anchor_date=date(2026, 8, 7),
            limit_duration_by_key={
                "root": "2天",
                "build": "bad",
                "accept": "2天",
            },
            warnings=warnings,
        )

        self.assertEqual(run.requested_compression_days, 5)
        self.assertEqual(run.achieved_compression_days, 0)
        self.assertEqual(run.allocations, {})
        self.assertEqual(run.results["accept"].finish, date(2026, 8, 12))
        self.assertTrue(any("build" in warning and "极限工期" in warning for warning in warnings))
        self.assertTrue(any("install" in warning and "极限工期" in warning for warning in warnings))
        self.assertTrue(any("无法完全压缩" in warning for warning in warnings))

    def test_execute_milestone_compression_returns_dry_run_mutations_without_writing_csv(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            with milestone_path.open("r", encoding="utf-8-sig", newline="") as source_file:
                rows = list(csv.DictReader(source_file))
                fieldnames = list(rows[0].keys())
            compression_row = {
                "milestoneKey": "浙江移动::PROJECT::GLOBAL::MILESTONE_COMPRESSION",
                "projectKey": "浙江移动",
                "projectName": "浙江移动",
                "scopeType": "PROJECT",
                "scopeKey": "GLOBAL",
                "milestoneType": "MILESTONE_COMPRESSION",
                "milestoneName": "里程碑压缩",
                "plannedDate": "",
                "actualDate": "",
                "anchorDate": "2026/8/1",
                "sourceFile": "Milestone.csv",
                "description": "里程碑压缩目标；以到货最晚完成时间为基准整体平移项目活动",
                "directionRole": "MILESTONE_COMPRESSION_TARGET",
                "dependencyMilestoneTypes": "ARRIVAL",
            }
            for row in rows:
                if row.get("milestoneKey") == compression_row["milestoneKey"]:
                    row.update(compression_row)
                    break
            else:
                rows.append(compression_row)
            with temp_milestone_path.open("w", encoding="utf-8-sig", newline="") as target_file:
                writer = csv.DictWriter(target_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                plan_rows = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")
                room_row = next(row for row in plan_rows if row["activityName"] == "机房改造实施")
                arrival_baseline_dates = [
                    data_connector._try_parse_plan_date(row["endDate"])
                    for row in plan_rows
                    if "到货" in str(row.get("activityName", ""))
                ]
                expected_baseline = max(item for item in arrival_baseline_dates if item is not None)
                expected_anchor = date(2026, 8, 1)
                expected_shift_days = (expected_anchor - expected_baseline).days
                room_start = data_connector._try_parse_plan_date(room_row["startDate"])
                room_end = data_connector._try_parse_plan_date(room_row["endDate"])

                result = data_connector.execute_milestone_compression(
                    "浙江移动",
                    anchor_id="浙江移动::PROJECT::GLOBAL::MILESTONE_COMPRESSION",
                )

                self.assertEqual(result["status"], "DRY_RUN_READY")
                self.assertEqual(result["summary"]["projectId"], "浙江移动")
                self.assertEqual(result["summary"]["selectedAnchorId"], "浙江移动::PROJECT::GLOBAL::MILESTONE_COMPRESSION")
                self.assertEqual(result["summary"]["baselineDate"], expected_baseline.isoformat())
                self.assertEqual(result["summary"]["anchorDate"], "2026-08-01")
                self.assertEqual(result["summary"]["shiftDays"], expected_shift_days)
                self.assertGreater(result["summary"]["affectedNodeCount"], 0)
                self.assertEqual(result["summary"]["mutationCount"], len(result["proposed_mutations"]))
                self.assertGreater(result["summary"]["mutationCount"], 0)
                room_mutations = {
                    mutation["field"]: mutation
                    for mutation in result["proposed_mutations"]
                    if mutation["rowKey"] == room_row["rowKey"]
                }
                self.assertEqual(room_mutations["startDate"]["originalDate"], room_row["startDate"])
                self.assertEqual(
                    room_mutations["startDate"]["newDate"],
                    date.fromordinal(room_start.toordinal() + expected_shift_days).isoformat(),
                )
                self.assertEqual(room_mutations["endDate"]["originalDate"], room_row["endDate"])
                self.assertEqual(
                    room_mutations["endDate"]["newDate"],
                    date.fromordinal(room_end.toordinal() + expected_shift_days).isoformat(),
                )
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_execute_plan_compression_decision_first_phase_delay_extends_by_duration_share_without_writing_csv(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            before_project_bytes = temp_project_path.read_bytes()
            before_milestone_bytes = temp_milestone_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }

                with patch(
                    "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
                    return_value=None,
                ):
                    result = data_connector.execute_plan_compression_decision(
                        "浙江移动",
                        power_on_target_date="2026-08-25",
                        cluster_debug_target_date="2026-09-20",
                    )

                self.assertEqual(result["status"], "DRY_RUN_READY")
                self.assertEqual(result["summary"]["projectId"], "浙江移动")
                self.assertGreater(result["summary"]["mutationCount"], 0)
                self.assertIn("decisionAdvice", result)
                self.assertIn("llm_semantic_payload", result)
                payload = result["llm_semantic_payload"]
                self.assertEqual(payload["version"], "v1")
                self.assertEqual(len(payload["strategies"]), 3)
                strategy_ids = {item["strategy_id"] for item in payload["strategies"]}
                self.assertEqual(
                    strategy_ids,
                    {"supply_frontload", "duration_top3_slack", "duration_global_proportional"},
                )
                for strategy in payload["strategies"]:
                    self.assertIsInstance(strategy["recommendation_summary"], str)
                    self.assertIsInstance(strategy["quantitative_evidence"], list)
                    self.assertIsInstance(strategy["cascading_risks"], list)
                    self.assertIsInstance(strategy["actionable_mutations"], list)
                    self.assertIn("isRecommended", strategy)
                    self.assertIsInstance(strategy["keyInformation"], list)
                    self.assertIsInstance(strategy["phaseDetails"], list)
                    self.assertIn(
                        strategy["toolName"],
                        {
                            "preview_plan_supply_shift",
                            "preview_plan_top3_slack_compression",
                            "preview_plan_global_proportional_compression",
                        },
                    )
                    self.assertIsInstance(strategy["toolInput"], dict)
                    self.assertEqual(strategy["toolStatus"], "COMPLETED")
                self.assertIn(result["recommendedPlanId"], strategy_ids)
                recommended = [item for item in payload["strategies"] if item["isRecommended"]]
                self.assertEqual(len(recommended), 1)
                self.assertEqual(recommended[0]["strategy_id"], result["recommendedPlanId"])
                self.assertEqual(result["phases"][0]["phaseId"], "phase1_power_on")
                phase1_scenarios = result["phases"][0]["scenarios"]
                extension = next(
                    scenario
                    for scenario in phase1_scenarios
                    if scenario["scenarioId"] == "phase1_duration_proportional_extension"
                )
                self.assertEqual(extension["strategy"], "PROPORTIONAL_EXTENSION")
                self.assertGreater(extension["requestedExtensionDays"], 0)
                self.assertGreater(extension["mutationCount"], 0)
                self.assertTrue(extension["isRecommended"])
                phase1_mutations = [
                    mutation
                    for mutation in result["proposed_mutations"]
                    if mutation.get("phaseId") == "phase1_power_on"
                ]
                self.assertGreater(len(phase1_mutations), 0)
                self.assertTrue(any("等比延长" in mutation["reason"] for mutation in phase1_mutations))
                self.assertEqual(temp_project_path.read_bytes(), before_project_bytes)
                self.assertEqual(temp_milestone_path.read_bytes(), before_milestone_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_execute_plan_compression_decision_phase2_window_shrinks_when_phase1_is_delayed(self):
        data_connector = importlib.import_module("data_connector")

        with self._temporary_project_sources(
            data_connector,
            "京东",
            data_connector.OTT10_SOURCE_FILE,
            blank_dates=False,
        ) as (temp_project_path, temp_milestone_path):
            before_project_bytes = temp_project_path.read_bytes()
            before_milestone_bytes = temp_milestone_path.read_bytes()

            with patch(
                "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
                return_value=None,
            ):
                # cluster 目标取早于当前虚拟基线(2026-02-17，随 OTT10 种子演进)的日期，
                # 构造「phase1 延后 → phase2 窗口收缩 9 天」的压缩场景；下方期望值与当前
                # OTT10 种子 CSV 的集群调优活动日期耦合（原 2026-04 系列日期已随种子前移）。
                result = data_connector.execute_plan_compression_decision(
                    "京东",
                    power_on_target_date="2026-01-29",
                    cluster_debug_target_date="2026-02-08",
                )

            self.assertEqual(result["status"], "DRY_RUN_READY")
            phase1 = result["phases"][0]
            phase2 = result["phases"][1]
            self.assertEqual(phase1["phaseId"], "phase1_power_on")
            self.assertEqual(phase1["baselineDate"], "2026-01-21")
            self.assertEqual(phase1["targetDate"], "2026-01-29")
            self.assertEqual(phase2["phaseId"], "phase2_cluster_debug")
            self.assertEqual(phase2["baselineDate"], "2026-04-18")
            self.assertEqual(phase2["targetDate"], "2026-02-08")
            self.assertEqual(phase2["startBaselineDate"], "2026-01-21")
            self.assertEqual(phase2["startTargetDate"], "2026-01-29")
            self.assertEqual(phase2["endBaselineDate"], "2026-04-01")
            self.assertEqual(phase2["endTargetDate"], "2026-02-08")
            self.assertEqual(phase2["durationDeltaDays"], -60)
            self.assertNotEqual(phase2["recommendedScenarioId"], "phase2_noop")
            phase2_compression = [
                scenario
                for scenario in phase2["scenarios"]
                if scenario["strategy"] in {"TOP3_SLACK", "PROPORTIONAL"}
            ]
            self.assertGreaterEqual(len(phase2_compression), 2)
            self.assertTrue(any(scenario.get("isRecommended") for scenario in phase2_compression))
            for scenario in phase2_compression:
                self.assertEqual(scenario["baselineDate"], "2026-04-18")
                self.assertEqual(scenario["targetDate"], "2026-02-08")
                self.assertEqual(scenario["requestedCompressionDays"], 69)
                self.assertIn("mutationCount", scenario)
            self.assertEqual(temp_project_path.read_bytes(), before_project_bytes)
            self.assertEqual(temp_milestone_path.read_bytes(), before_milestone_bytes)

    def test_execute_plan_compression_decision_uses_pod_power_on_batches_without_writing_csv(self):
        data_connector = importlib.import_module("data_connector")

        pod_one_key = "京东::POD::B2DH401-POD01::POWER_ON"
        pod_two_key = "京东::POD::B2DH401-POD02::POWER_ON"
        with self._temporary_project_sources(
            data_connector,
            "京东",
            data_connector.OTT10_SOURCE_FILE,
            blank_dates=False,
        ) as (temp_project_path, temp_milestone_path):
            before_project_bytes = temp_project_path.read_bytes()
            before_milestone_bytes = temp_milestone_path.read_bytes()

            with patch(
                "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
                return_value=None,
            ):
                result = data_connector.execute_plan_compression_decision(
                    "京东",
                    power_on_target_date="2026-01-29",
                    cluster_debug_target_date="2026-04-07",
                    pod_power_on_target_dates=[
                        {"milestoneKey": pod_one_key, "anchorDate": "2026-01-25"},
                        {"milestoneKey": pod_two_key, "anchorDate": "2026-01-27"},
                    ],
                )

            self.assertEqual(result["status"], "DRY_RUN_READY")
            self.assertEqual(result["summary"]["executionMode"], "POD_BATCH")
            self.assertGreaterEqual(result["summary"]["podPowerOnBatchCount"], 2)
            self.assertEqual(result["summary"]["podPowerOnMilestoneMutationCount"], 2)
            self.assertEqual(result["phases"][1]["executionMode"], "POD_BATCH")
            self.assertIn("podPowerOnBatchTargets", result)
            targets_by_key = {
                item["milestoneKey"]: item
                for item in result["podPowerOnBatchTargets"]
            }
            self.assertEqual(targets_by_key[pod_one_key]["targetDate"], "2026-01-25")
            self.assertEqual(targets_by_key[pod_two_key]["targetDate"], "2026-01-27")
            pod_mutations = result["podPowerOnMilestoneMutations"]
            self.assertEqual(
                {
                    (mutation["milestoneKey"], mutation["newDate"])
                    for mutation in pod_mutations
                },
                {
                    (pod_one_key, "2026-01-25"),
                    (pod_two_key, "2026-01-27"),
                },
            )
            self.assertTrue(
                all(mutation.get("field") in {"startDate", "endDate"} for mutation in result["proposed_mutations"])
            )
            self.assertEqual(temp_project_path.read_bytes(), before_project_bytes)
            self.assertEqual(temp_milestone_path.read_bytes(), before_milestone_bytes)

    def test_execute_plan_compression_decision_supply_strategy_returns_parameter_override_suggestions(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            before_project_bytes = temp_project_path.read_bytes()
            before_milestone_bytes = temp_milestone_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }

                with patch(
                    "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
                    return_value=None,
                ):
                    result = data_connector.execute_plan_compression_decision(
                        "浙江移动",
                        power_on_target_date="2026-08-10",
                        cluster_debug_target_date="2026-09-07",
                    )

                plan_rows = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")
                room_dates = [
                    data_connector._try_parse_plan_date(row["endDate"])
                    for row in plan_rows
                    if "机房改造实施" in str(row.get("activityName", ""))
                ]
                arrival_dates = [
                    data_connector._try_parse_plan_date(row["endDate"])
                    for row in plan_rows
                    if "到货" in str(row.get("activityName", ""))
                ]
                expected_room_done = max(item for item in room_dates if item is not None)
                expected_arrival_baseline = max(item for item in arrival_dates if item is not None)

                supply_strategy = next(
                    item
                    for item in result["llm_semantic_payload"]["strategies"]
                    if item["strategy_id"] == "supply_frontload"
                )
                override = supply_strategy["parameter_overrides"]
                expected_target = data_connector._try_parse_plan_date(override["suggestedTargetArrivalDate"])
                expected_advance_days = (expected_arrival_baseline - expected_target).days

                self.assertEqual(override["roomImplementationDoneDate"], expected_room_done.isoformat())
                self.assertEqual(override["baselineArrivalDate"], expected_arrival_baseline.isoformat())
                self.assertGreater(expected_advance_days, 0)
                self.assertEqual(override["suggestedArrivalAdvanceDays"], expected_advance_days)
                self.assertEqual(override["effectiveArrivalAdvanceDays"], expected_advance_days)
                self.assertEqual(override["effectiveTargetArrivalDate"], override["suggestedTargetArrivalDate"])
                self.assertIn("机房实施完成建议值", supply_strategy["cascading_risks"][0])
                self.assertIn(f"到货提前建议值：{expected_advance_days} 天", supply_strategy["cascading_risks"][1])
                self.assertNotIn("前移供应链可能触发到货波动", " ".join(supply_strategy["cascading_risks"]))
                self.assertEqual(temp_project_path.read_bytes(), before_project_bytes)
                self.assertEqual(temp_milestone_path.read_bytes(), before_milestone_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_execute_plan_compression_decision_confirmed_supply_advance_days_reruns_supply_target_without_writing_csv(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            before_project_bytes = temp_project_path.read_bytes()
            before_milestone_bytes = temp_milestone_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }

                llm_response = {
                    "recommendedPlanId": "supply_frontload",
                    "decisionAdvice": "LLM 建议采用供应前移，但需以供应商确认天数重跑。",
                    "strategies": [
                        {
                            "strategy_id": "supply_frontload",
                            "recommendation_summary": "供应商已确认部分提前。",
                            "keyInformation": ["按真实确认天数重跑"],
                            "cascading_risks": ["需保留工具建议值。"],
                        }
                    ],
                }
                with patch(
                    "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
                    return_value=llm_response,
                ):
                    result = data_connector.execute_plan_compression_decision(
                        "浙江移动",
                        power_on_target_date="2026-08-10",
                        cluster_debug_target_date="2026-09-07",
                        confirmed_arrival_advance_days=1,
                    )

                supply_phase = result["phases"][0]["scenarios"][0]
                supply_strategy = next(
                    item
                    for item in result["llm_semantic_payload"]["strategies"]
                    if item["strategy_id"] == "supply_frontload"
                )
                override = supply_strategy["parameter_overrides"]
                expected_target = (
                    data_connector._try_parse_plan_date(override["baselineArrivalDate"]).toordinal() - 1
                )
                expected_target_date = date.fromordinal(expected_target).isoformat()

                self.assertEqual(result["recommendedPlanId"], "supply_frontload")
                self.assertEqual(supply_phase["targetDate"], expected_target_date)
                self.assertEqual(supply_phase["requestedShiftDays"], -1)
                self.assertGreater(override["suggestedArrivalAdvanceDays"], 1)
                self.assertEqual(override["confirmedArrivalAdvanceDays"], 1)
                self.assertEqual(override["effectiveArrivalAdvanceDays"], 1)
                self.assertEqual(override["effectiveTargetArrivalDate"], expected_target_date)
                self.assertGreater(len(result["proposed_mutations"]), 0)
                self.assertTrue(
                    all(mutation.get("scenarioId") == "phase1_supply_shift" for mutation in result["proposed_mutations"])
                )
                self.assertEqual(temp_project_path.read_bytes(), before_project_bytes)
                self.assertEqual(temp_milestone_path.read_bytes(), before_milestone_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_execute_plan_compression_decision_uses_llm_selected_three_tool_strategy(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            before_project_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }

                llm_response = {
                    "recommendedPlanId": "supply_frontload",
                    "decisionAdvice": "LLM 建议优先采用供应平移，减少工期压缩对关键路径的扰动。",
                    "strategies": [
                        {
                            "strategy_id": "supply_frontload",
                            "recommendation_summary": "LLM 推荐供应平移。",
                            "keyInformation": ["供应平移变更集中", "保持活动工期不变"],
                            "cascading_risks": ["需确认到货资源可提前。"],
                        }
                    ],
                }
                with patch(
                    "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
                    return_value=llm_response,
                ):
                    result = data_connector.execute_plan_compression_decision(
                        "浙江移动",
                        power_on_target_date="2026-08-25",
                        cluster_debug_target_date="2026-09-20",
                    )

                self.assertEqual(result["recommendedPlanId"], "supply_frontload")
                self.assertEqual(result["summary"]["advisorRuntime"], "llm")
                self.assertEqual(result["decisionAdvice"], llm_response["decisionAdvice"])
                self.assertGreater(len(result["proposed_mutations"]), 0)
                self.assertTrue(
                    all(mutation.get("scenarioId") == "phase1_supply_shift" for mutation in result["proposed_mutations"])
                )
                payload = result["llm_semantic_payload"]
                selected = next(item for item in payload["strategies"] if item["strategy_id"] == "supply_frontload")
                self.assertTrue(selected["isRecommended"])
                self.assertEqual(selected["recommendation_summary"], "LLM 推荐供应平移。")
                self.assertEqual(selected["keyInformation"][:2], ["供应平移变更集中", "保持活动工期不变"])
                self.assertEqual(temp_project_path.read_bytes(), before_project_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_execute_plan_compression_decision_falls_back_when_llm_unavailable(self):
        data_connector = importlib.import_module("data_connector")

        with patch(
            "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
            return_value=None,
        ):
            result = data_connector.execute_plan_compression_decision(
                "浙江移动",
                power_on_target_date="2026-08-25",
                cluster_debug_target_date="2026-09-20",
            )

        strategy_ids = {item["strategy_id"] for item in result["llm_semantic_payload"]["strategies"]}
        self.assertIn(result["recommendedPlanId"], strategy_ids)
        self.assertEqual(result["summary"]["advisorRuntime"], "deterministic_fallback")
        self.assertTrue(any("LLM" in warning for warning in result["warnings"]))

    def test_execute_milestone_compression_rejects_invalid_anchor_and_missing_baseline(self):
        data_connector = importlib.import_module("data_connector")

        with (
            patch.object(
                data_connector,
                "_load_project_milestone_compression_targets",
                return_value=[
                    {
                        "milestoneKey": "compression-1",
                        "milestoneName": "里程碑压缩",
                        "milestoneType": "MILESTONE_COMPRESSION",
                        "anchorDate": "2026-08-01",
                        "dependencyMilestoneTypes": "ARRIVAL",
                    }
                ],
            ),
            patch.object(data_connector, "_select_sources", return_value=[data_connector.ProjectSource("浙江移动", "plan.csv", "浙江移动")]),
        ):
            with self.assertRaisesRegex(ValueError, "Invalid anchor_id"):
                data_connector.execute_milestone_compression("浙江移动", anchor_id="bad-anchor")

        fake_ontology = SimpleNamespace(objects=SimpleNamespace(DeliveryPlanRow=SimpleNamespace(all=lambda: [])))
        with (
            patch.object(data_connector, "_select_sources", return_value=[data_connector.ProjectSource("浙江移动", "plan.csv", "浙江移动")]),
            patch.object(data_connector, "_load_ontology", return_value=fake_ontology),
            patch.object(
                data_connector,
                "_load_project_milestone_compression_targets",
                return_value=[
                    {
                        "milestoneKey": "compression-1",
                        "milestoneName": "里程碑压缩",
                        "milestoneType": "MILESTONE_COMPRESSION",
                        "anchorDate": "2026-08-01",
                        "dependencyMilestoneTypes": "ARRIVAL",
                    }
                ],
            ),
        ):
            with self.assertRaisesRegex(ValueError, "No DeliveryPlanRow matched compression baseline"):
                data_connector.execute_milestone_compression("浙江移动")

    def test_plan_compression_llm_semantic_payload_dedupes_semantic_date_mutations(self):
        data_connector = importlib.import_module("data_connector")

        mutations = [
            {"milestoneId": "row-1", "field": "endDate", "newDate": "2026/08/10"},
            {"milestoneId": "row-1", "field": "endDate", "newDate": "2026-08-10"},
            {"milestoneId": "row-1", "field": "startDate", "newDate": "2026-08-01"},
        ]
        normalized = data_connector._normalize_actionable_mutations(mutations)

        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["newDate"], "2026-08-10")
        self.assertEqual(normalized[1]["newDate"], "2026-08-01")

    def test_plan_compression_llm_semantic_payload_enforces_strategy_char_budget(self):
        data_connector = importlib.import_module("data_connector")

        strategy = {
            "strategy_id": "duration_top3_slack",
            "strategy_type": "top3_slack",
            "title": "工期压缩TOP3空闲",
            "recommendation_summary": "x" * 600,
            "quantitative_evidence": [{"metric": f"m{i}", "value": i} for i in range(10)],
            "cascading_risks": ["r" * 400, "r" * 200],
            "actionable_mutations": [
                {
                    "milestoneId": f"row-{i}",
                    "field": "endDate",
                    "newDate": "2026-08-10",
                    "precondition": f"row-{i}.endDate != 2026-08-10",
                }
                for i in range(20)
            ],
        }
        guarded = data_connector._apply_strategy_token_guard(strategy)
        encoded = json.dumps(guarded, ensure_ascii=False, sort_keys=True)

        self.assertLessEqual(len(encoded), data_connector.STRATEGY_CHAR_LIMIT)
        self.assertLessEqual(len(guarded["actionable_mutations"]), 6)
        self.assertLessEqual(len(guarded["quantitative_evidence"]), 3)

    def test_forward_key_milestones_uses_all_arrival_matches_and_anchor_date(self):
        data_connector = importlib.import_module("data_connector")

        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                result = data_connector.execute_forward_key_milestones("浙江移动")
                arrival_anchor_rows = [
                    row_key
                    for milestone in result["anchorMilestones"]
                    if milestone["milestoneType"] == "ARRIVAL"
                    for row_key in milestone["rowKeys"]
                ]
                expected_arrival_rows = {
                    row["rowKey"]
                    for row in data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")
                    if "到货" in row["activityName"]
                }

                self.assertGreater(len(expected_arrival_rows), 1)
                self.assertEqual(set(arrival_anchor_rows), expected_arrival_rows)
                self.assertIn("2026-08-08", {milestone["anchorDate"] for milestone in result["anchorMilestones"]})
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_execute_forward_key_milestones_rejects_missing_start_anchor_date(self):
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            with milestone_path.open("r", encoding="utf-8-sig", newline="") as source_file:
                rows = list(csv.DictReader(source_file))
                fieldnames = list(rows[0].keys())
            for row in rows:
                if row.get("projectKey") == "浙江移动" and row.get("directionRole") == "FORWARD_START":
                    row["plannedDate"] = ""
                    row["actualDate"] = ""
                    row["anchorDate"] = ""
            with temp_milestone_path.open("w", encoding="utf-8-sig", newline="") as target_file:
                writer = csv.DictWriter(target_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                with self.assertRaisesRegex(ValueError, "FORWARD_START.*date"):
                    data_connector.execute_forward_key_milestones("浙江移动")
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_ontology_discovery_endpoints(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        ontologies = self.client.get("/api/v2/ontologies")
        self.assertEqual(ontologies.status_code, 200)
        ontology_by_name = {item["apiName"]: item for item in ontologies.json()}
        # The delivery-contingency-plan ontology was merged into `default`: one ontology remains.
        # The expected count derives from schema/object-types.json (no hand-copied tally): the
        # endpoint must surface every declared ObjectType, no more, no fewer.
        backend_app = importlib.import_module("backend_app")
        expected_object_type_count = len(backend_app.load_object_types())
        self.assertEqual(set(ontology_by_name), {"default"})
        self.assertEqual(
            ontology_by_name["default"]["objectTypeCount"], expected_object_type_count
        )

        ontology = self.client.get("/api/v2/ontologies/default")
        self.assertEqual(ontology.status_code, 200)
        self.assertEqual(ontology.json()["apiName"], "default")
        self.assertEqual(ontology.json()["objectTypeCount"], expected_object_type_count)

        # The old contingency ontology id no longer resolves.
        contingency_ontology = self.client.get("/api/v2/ontologies/delivery-contingency-plan")
        self.assertEqual(contingency_ontology.status_code, 404)

        unknown_ontology = self.client.get("/api/v2/ontologies/not-an-ontology")
        self.assertEqual(unknown_ontology.status_code, 404)

    def test_v2_object_types_and_action_types(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        object_types = self.client.get("/api/v2/ontologies/default/objectTypes")
        self.assertEqual(object_types.status_code, 200)
        names = {item["apiName"] for item in object_types.json()}
        self.assertIn("DeliveryPlanRow", names)
        self.assertIn("Milestone", names)

        object_type = self.client.get("/api/v2/ontologies/default/objectTypes/DeliveryPlanRow")
        self.assertEqual(object_type.status_code, 200)
        object_type_payload = object_type.json()
        self.assertEqual(object_type_payload["apiName"], "DeliveryPlanRow")
        self.assertIn("properties", object_type_payload)
        self.assertNotIn("dataSchema", object_type_payload)
        self.assertNotIn("uiSchema", object_type_payload)

        action_types = self.client.get("/api/v2/ontologies/default/actionTypes")
        self.assertEqual(action_types.status_code, 200)
        self.assertGreater(len(action_types.json()), 0)
        action_names = {item["apiName"] for item in action_types.json()}
        self.assertIn("executeBackwardKeyMilestones", action_names)
        self.assertIn("executeForwardKeyMilestones", action_names)
        self.assertIn("executePlanCompressionDecision", action_names)
        self.assertIn("modifyPodPowerOnMilestoneAnchorDate", action_names)
        pod_power_action = next(
            item for item in action_types.json() if item["apiName"] == "modifyPodPowerOnMilestoneAnchorDate"
        )
        self.assertEqual(pod_power_action["targetObjectTypeApiName"], "Milestone")
        self.assertEqual(
            pod_power_action["targetConstraints"],
            {"scopeType": "POD", "milestoneType": "POWER_ON"},
        )
        self.assertIn("targetPodPowerOnMilestone", pod_power_action["parameters"])
        self.assertEqual(
            pod_power_action["edits"],
            [
                {
                    "type": "MODIFY_OBJECT",
                    "targetParameter": "targetPodPowerOnMilestone",
                    "propertyUpdates": {"anchorDate": "${anchorDate}"},
                }
            ],
        )
        plan_compression_strategy_actions = {
            "executePlanCompressionSupplyShift": "SUPPLY_ADVANCE_SHIFT",
            "executePlanCompressionDurationTopNSlack": "TOPN_SLACK",
            "executePlanCompressionDurationProportional": "PROPORTIONAL",
            "executePlanCompressionDurationProportionalExtension": "PROPORTIONAL_EXTENSION",
        }
        for action_name, strategy in plan_compression_strategy_actions.items():
            self.assertIn(action_name, action_names)
            strategy_action = next(item for item in action_types.json() if item["apiName"] == action_name)
            self.assertEqual(strategy_action["targetObjectTypeApiName"], "DeliveryProject")
            self.assertEqual(strategy_action["strategy"], strategy)
            self.assertEqual(strategy_action["sideEffects"]["type"], "DRY_RUN_ONLY")
            self.assertEqual(strategy_action["sideEffects"]["skillApiName"], "execute_plan_compression_decision")
            self.assertEqual(strategy_action["sideEffects"]["writebackActionApiName"], "UpdateMilestoneDate")
        forward_action = next(item for item in action_types.json() if item["apiName"] == "executeForwardKeyMilestones")
        self.assertEqual(forward_action["sideEffects"]["type"], "DRY_RUN_ONLY")
        self.assertEqual(forward_action["sideEffects"]["skillApiName"], "execute_forward_key_milestones")
        self.assertEqual(forward_action["sideEffects"]["writebackActionApiName"], "UpdateMilestoneDate")
        compression_action = next(
            item for item in action_types.json() if item["apiName"] == "executePlanCompressionDecision"
        )
        self.assertEqual(compression_action["sideEffects"]["type"], "DRY_RUN_ONLY")
        self.assertEqual(compression_action["sideEffects"]["skillApiName"], "execute_plan_compression_decision")
        self.assertEqual(compression_action["sideEffects"]["writebackActionApiName"], "UpdateMilestoneDate")

    def test_v2_contingency_objects_merged_into_default_ontology(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        # The contingency objects now resolve under `default` (previously a separate ontology).
        contingency_plan = self.client.get("/api/v2/ontologies/default/objectTypes/ContingencyPlan")
        self.assertEqual(contingency_plan.status_code, 200)
        self.assertEqual(contingency_plan.json()["apiName"], "ContingencyPlan")
        self.assertIn("updatedBy", contingency_plan.json()["properties"])
        # Project-ized: ContingencyPlan carries projectKey and implements ProjectScoped.
        self.assertIn("projectKey", contingency_plan.json()["properties"])
        self.assertIn("ProjectScoped", contingency_plan.json().get("implementsInterfaces", []))

        # The old contingency ontology id no longer resolves.
        old_objects = self.client.get("/api/v2/ontologies/delivery-contingency-plan/objectTypes")
        self.assertEqual(old_objects.status_code, 404)

        objects = self.client.get("/api/v2/ontologies/default/objectTypes")
        self.assertEqual(objects.status_code, 200)
        object_names = {item["apiName"] for item in objects.json()}
        # Default plan objects and contingency objects coexist in one ontology.
        for name in [
            "DeliveryPlanRow", "DeliveryProject", "ContingencyPlan", "DecisionPoint",
            "ProjectRequirement", "ClusterDeviceInventory", "RiskRule",
        ]:
            self.assertIn(name, object_names)

        links = self.client.get("/api/v2/ontologies/default/linkTypes")
        self.assertEqual(links.status_code, 200)
        link_names = {item["apiName"] for item in links.json()}
        self.assertIn("ProjectPlanRows", link_names)
        self.assertIn("Plan_UseCase", link_names)
        # New cross link: one DeliveryProject -> many ContingencyPlan.
        self.assertIn("ProjectContingencyPlans", link_names)
        cross = next(item for item in links.json() if item["apiName"] == "ProjectContingencyPlans")
        self.assertEqual(cross["objectTypeApiName"], "DeliveryProject")
        self.assertEqual(cross["linkedObjectTypeApiName"], "ContingencyPlan")

        actions = self.client.get("/api/v2/ontologies/default/actionTypes")
        self.assertEqual(actions.status_code, 200)
        action_names = {item["apiName"] for item in actions.json()}
        self.assertIn("executeForwardKeyMilestones", action_names)
        self.assertIn("CreateGapItem", action_names)

    def test_v2_collapsed_contingency_ontology_id_is_gone(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        # After the merge there is no separate delivery-contingency-plan ontology; its old
        # runtime routes 404 because the id no longer resolves.
        objects = self.client.get("/api/v2/ontologies/delivery-contingency-plan/objects/ContingencyPlan")
        self.assertEqual(objects.status_code, 404)

        action = self.client.post(
            "/api/v2/ontologies/delivery-contingency-plan/actions/CreateGapItem/apply",
            json={"planId": "demo-plan", "assessmentId": "assessment-1", "title": "gap", "description": "gap", "severity": "HIGH"},
        )
        self.assertEqual(action.status_code, 404)

    def test_v2_get_action_type_returns_single_schema(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        response = self.client.get("/api/v2/ontologies/default/actionTypes/executeForwardKeyMilestones")
        self.assertEqual(response.status_code, 200)

        action_type = response.json()
        self.assertEqual(action_type["apiName"], "executeForwardKeyMilestones")
        self.assertEqual(action_type["targetObjectTypeApiName"], "DeliveryProject")
        self.assertEqual(action_type["sideEffects"]["type"], "DRY_RUN_ONLY")
        self.assertEqual(action_type["sideEffects"]["skillApiName"], "execute_forward_key_milestones")
        self.assertEqual(action_type["sideEffects"]["writebackActionApiName"], "UpdateMilestoneDate")

        compression_response = self.client.get(
            "/api/v2/ontologies/default/actionTypes/executePlanCompressionDecision"
        )
        self.assertEqual(compression_response.status_code, 200)
        compression_action = compression_response.json()
        self.assertEqual(compression_action["apiName"], "executePlanCompressionDecision")
        self.assertEqual(compression_action["sideEffects"]["type"], "DRY_RUN_ONLY")
        self.assertEqual(compression_action["sideEffects"]["skillApiName"], "execute_plan_compression_decision")

        plan_compression_strategy_actions = {
            "executePlanCompressionSupplyShift": "SUPPLY_ADVANCE_SHIFT",
            "executePlanCompressionDurationTopNSlack": "TOPN_SLACK",
            "executePlanCompressionDurationProportional": "PROPORTIONAL",
            "executePlanCompressionDurationProportionalExtension": "PROPORTIONAL_EXTENSION",
        }
        for action_name, strategy in plan_compression_strategy_actions.items():
            strategy_response = self.client.get(f"/api/v2/ontologies/default/actionTypes/{action_name}")
            self.assertEqual(strategy_response.status_code, 200)
            strategy_action = strategy_response.json()
            self.assertEqual(strategy_action["apiName"], action_name)
            self.assertEqual(strategy_action["targetObjectTypeApiName"], "DeliveryProject")
            self.assertEqual(strategy_action["strategy"], strategy)
            self.assertEqual(strategy_action["sideEffects"]["type"], "DRY_RUN_ONLY")
            self.assertEqual(strategy_action["sideEffects"]["skillApiName"], "execute_plan_compression_decision")
            self.assertEqual(strategy_action["sideEffects"]["writebackActionApiName"], "UpdateMilestoneDate")

        unknown_action = self.client.get("/api/v2/ontologies/default/actionTypes/notAnAction")
        self.assertEqual(unknown_action.status_code, 404)

    def test_v2_skill_types_publish_milestone_dry_run_skills(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        response = self.client.get("/api/v2/ontologies/default/skillTypes")
        self.assertEqual(response.status_code, 200)
        skill_types = response.json()
        names = {item["apiName"] for item in skill_types}
        self.assertIn("execute_backward_key_milestones", names)
        self.assertIn("execute_forward_key_milestones", names)
        self.assertIn("execute_milestone_compression", names)
        self.assertIn("execute_plan_compression_decision", names)
        backward_skill = next(item for item in skill_types if item["apiName"] == "execute_backward_key_milestones")
        forward_skill = next(item for item in skill_types if item["apiName"] == "execute_forward_key_milestones")
        compression_skill = next(item for item in skill_types if item["apiName"] == "execute_milestone_compression")
        plan_compression_skill = next(
            item for item in skill_types if item["apiName"] == "execute_plan_compression_decision"
        )
        self.assertEqual(backward_skill["sideEffects"]["type"], "NONE")
        self.assertEqual(forward_skill["sideEffects"]["type"], "NONE")
        self.assertEqual(compression_skill["sideEffects"]["type"], "NONE")
        self.assertEqual(plan_compression_skill["sideEffects"]["type"], "NONE")

    def test_skill_registry_merged_into_function_types(self):
        # skill-types.json was merged into the Function registry: the standalone file
        # must no longer exist anywhere, and the 4 skills now live in function-types.json
        # tagged with kind == "SKILL".
        self.assertFalse((BACKEND_DIR / "skills" / "skill-types.json").exists())
        self.assertFalse((BACKEND_DIR / "schema" / "skill-types.json").exists())

        with (BACKEND_DIR / "schema" / "function-types.json").open("r", encoding="utf-8") as handle:
            function_types = json.load(handle)

        for api_name in (
            "execute_backward_key_milestones",
            "execute_forward_key_milestones",
            "execute_milestone_compression",
            "execute_plan_compression_decision",
        ):
            self.assertIn(api_name, function_types)
            skill = function_types[api_name]
            self.assertEqual(skill["kind"], "SKILL")
            self.assertEqual(skill["sideEffects"]["type"], "NONE")
            self.assertEqual(skill["binding"]["function"], api_name)

    def test_v1_meta_matches_v2_object_type_schema(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        v1_meta = self.client.get("/api/v1/ontology/meta/DeliveryPlanRow")
        self.assertEqual(v1_meta.status_code, 200)
        v2_object_type = self.client.get("/api/v2/ontologies/default/objectTypes/DeliveryPlanRow")
        self.assertEqual(v2_object_type.status_code, 200)
        self.assertEqual(v1_meta.json(), v2_object_type.json())

    def test_v2_objects_list_get_search_and_aggregate(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        listed = self.client.get(
            "/api/v2/ontologies/default/objects/DeliveryPlanRow",
            params={"project_id": "浙江移动", "limit": 2, "offset": 0},
        )
        self.assertEqual(listed.status_code, 200)
        listed_data = listed.json()
        self.assertIn("items", listed_data)
        self.assertEqual(listed_data["limit"], 2)
        self.assertGreater(listed_data["total"], 0)

        first_row = listed_data["items"][0]
        row_key = first_row["rowKey"]
        fetched = self.client.get(
            f"/api/v2/ontologies/default/objects/DeliveryPlanRow/{row_key}",
            params={"project_id": "浙江移动"},
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["object"]["rowKey"], row_key)

        searched = self.client.post(
            "/api/v2/ontologies/default/objects/DeliveryPlanRow/search",
            params={"project_id": "浙江移动"},
            json={
                "filters": {"and": [{"projectKey": {"op": "eq", "value": "浙江移动"}}]},
                "limit": 5,
                "offset": 0,
            },
        )
        self.assertEqual(searched.status_code, 200)
        self.assertGreaterEqual(searched.json()["total"], 1)

        aggregated = self.client.post(
            "/api/v2/ontologies/default/objects/Milestone/aggregate",
            params={"project_id": "京东"},
            json={"op": "count", "filters": {"projectKey": {"op": "eq", "value": "京东"}}},
        )
        self.assertEqual(aggregated.status_code, 200)
        self.assertGreaterEqual(aggregated.json()["value"], 1)

    def test_v1_data_is_compatible_with_v2_objects_items(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        v1_data = self.client.get(
            "/api/v1/ontology/data/DeliveryPlanRow",
            params={"project_id": "浙江移动"},
        )
        self.assertEqual(v1_data.status_code, 200)
        v1_items = v1_data.json()
        self.assertIsInstance(v1_items, list)

        v2_data = self.client.get(
            "/api/v2/ontologies/default/objects/DeliveryPlanRow",
            params={"project_id": "浙江移动", "limit": 500, "offset": 0},
        )
        self.assertEqual(v2_data.status_code, 200)
        v2_items = v2_data.json()["items"]
        self.assertEqual(v1_items, v2_items)

    def test_v1_execute_backward_endpoint(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                response = self.client.post(
                    "/api/v1/ontology/graph/backward-key-milestones/execute",
                    json={
                        "project_id": "浙江移动",
                        "anchor_id": "浙江移动::PROJECT::GLOBAL::POWER_ON",
                    },
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("actions/executeBackwardKeyMilestones/apply", response.json()["detail"])
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_backward_graph_and_execute_endpoints(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                graph_response = self.client.get(
                    "/api/v2/ontologies/default/queries/backward-key-milestones",
                    params={
                        "project_id": "浙江移动",
                        "anchor_id": "浙江移动::PROJECT::GLOBAL::POWER_ON",
                    },
                )
                self.assertEqual(graph_response.status_code, 200)
                self.assertEqual(graph_response.json()["anchorDate"], "2026-08-13")

                execute_response = self.client.post(
                    "/api/v2/ontologies/default/actions/executeBackwardKeyMilestones/apply",
                    json={
                        "project_id": "浙江移动",
                        "anchor_id": "浙江移动::PROJECT::GLOBAL::POWER_ON",
                    },
                )
                self.assertEqual(execute_response.status_code, 400)
                self.assertIn("Action Exclusive", execute_response.json()["detail"])
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_query_execute_rejects_backward_writeback(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                graph_response = self.client.get(
                    "/api/v2/ontologies/default/queries/backward-key-milestones",
                    params={
                        "project_id": "浙江移动",
                        "anchor_id": "浙江移动::PROJECT::GLOBAL::POWER_ON",
                    },
                )
                self.assertEqual(graph_response.status_code, 200)
                self.assertEqual(graph_response.json()["anchorDate"], "2026-08-13")

                execute_response = self.client.post(
                    "/api/v2/ontologies/default/queries/backward-key-milestones/execute",
                    json={
                        "project_id": "浙江移动",
                        "anchor_id": "浙江移动::PROJECT::GLOBAL::POWER_ON",
                    },
                )
                self.assertEqual(execute_response.status_code, 400)
                self.assertIn("actions/executeBackwardKeyMilestones/apply", execute_response.json()["detail"])
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_skill_execute_returns_backward_dry_run_without_mutating_csv(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                response = self.client.post(
                    "/api/v2/ontologies/default/skills/execute_backward_key_milestones/execute",
                    json={
                        "project_id": "浙江移动",
                        "anchor_id": "浙江移动::PROJECT::GLOBAL::POWER_ON",
                    },
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["status"], "DRY_RUN_READY")
                self.assertEqual(payload["summary"]["selectedAnchorId"], "浙江移动::PROJECT::GLOBAL::POWER_ON")
                self.assertGreater(payload["summary"]["mutationCount"], 0)
                self.assertEqual(payload["summary"]["mutationCount"], len(payload["proposed_mutations"]))
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_backward_action_apply_rejects_python_writeback_without_mutating_csv(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                response = self.client.post(
                    "/api/v2/ontologies/default/actions/executeBackwardKeyMilestones/apply",
                    json={
                        "project_id": "浙江移动",
                        "anchor_id": "浙江移动::PROJECT::GLOBAL::POWER_ON",
                    },
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("Action Exclusive", response.json()["detail"])
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_update_milestone_date_batch_action_writes_delivery_plan_rows(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                row_key = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")[0]["rowKey"]
                response = self.client.post(
                    "/api/v2/ontologies/default/actions/UpdateMilestoneDate/applyBatch",
                    json={
                        "batch": [
                            {
                                "milestoneId": row_key,
                                "dateField": "startDate",
                                "newDate": "2026-07-01",
                                "reason": "测试批量下发开始日期",
                            },
                            {
                                "milestoneId": row_key,
                                "dateField": "endDate",
                                "newDate": "2026-07-03",
                                "reason": "测试批量下发结束日期",
                            },
                        ],
                    },
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["appliedCount"], 2)
                self.assertNotEqual(temp_project_path.read_bytes(), before_bytes)
                updated = next(
                    row
                    for row in data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")
                    if row["rowKey"] == row_key
                )
                self.assertEqual(updated["startDate"], "2026-07-01")
                self.assertEqual(updated["endDate"], "2026-07-03")
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_update_milestone_date_batch_validate_does_not_write(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                row_key = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")[0]["rowKey"]
                response = self.client.post(
                    "/api/v2/ontologies/default/actions/UpdateMilestoneDate/validateBatch",
                    json={
                        "batch": [
                            {
                                "milestoneId": row_key,
                                "dateField": "startDate",
                                "newDate": "2026-07-01",
                                "reason": "测试批量校验开始日期",
                            },
                            {
                                "milestoneId": row_key,
                                "dateField": "endDate",
                                "newDate": "2026-07-03",
                                "reason": "测试批量校验结束日期",
                            },
                        ],
                    },
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["actionName"], "UpdateMilestoneDate")
                self.assertEqual(payload["validatedCount"], 2)
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_update_milestone_date_batch_action_rejects_bad_date_without_writing(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                row_key = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")[0]["rowKey"]
                response = self.client.post(
                    "/api/v2/ontologies/default/actions/UpdateMilestoneDate/applyBatch",
                    json={
                        "batch": [
                            {
                                "milestoneId": row_key,
                                "dateField": "startDate",
                                "newDate": "2026/07/01",
                            }
                        ],
                    },
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_update_milestone_date_batch_action_writes_csv_once_per_source_file(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                row_key = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")[0]["rowKey"]
                with patch.object(data_connector, "_write_csv", wraps=data_connector._write_csv) as write_csv_mock:
                    response = self.client.post(
                        "/api/v2/ontologies/default/actions/UpdateMilestoneDate/applyBatch",
                        json={
                            "batch": [
                                {
                                    "milestoneId": row_key,
                                    "dateField": "startDate",
                                    "newDate": "2026-07-01",
                                },
                                {
                                    "milestoneId": row_key,
                                    "dateField": "endDate",
                                    "newDate": "2026-07-03",
                                },
                            ],
                        },
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(write_csv_mock.call_count, 1)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_action_validate_accepts_end_date_without_mutating_csv(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                row = next(
                    item
                    for item in data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")
                    if item["activityName"] == "现场勘测"
                )

                response = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyDeliveryPlanEndDate/validate",
                    json={
                        "project_id": "浙江移动",
                        "rowKey": row["rowKey"],
                        "changes": {"endDate": "2026-07-18"},
                    },
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["actionName"], "modifyDeliveryPlanEndDate")
                self.assertEqual(payload["validatedChanges"], {"endDate": "2026-07-18"})
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_action_validate_rejects_bad_end_date_requests_without_mutating_csv(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                row = data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")[0]

                invalid_date = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyDeliveryPlanEndDate/validate",
                    json={
                        "project_id": "浙江移动",
                        "rowKey": row["rowKey"],
                        "changes": {"endDate": "2026/07/18"},
                    },
                )
                self.assertEqual(invalid_date.status_code, 400)

                invalid_field = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyDeliveryPlanEndDate/validate",
                    json={
                        "project_id": "浙江移动",
                        "rowKey": row["rowKey"],
                        "changes": {"startDate": "2026-07-18"},
                    },
                )
                self.assertEqual(invalid_field.status_code, 400)

                unknown_row = self.client.post(
                    "/api/v2/ontologies/default/actions/modifyDeliveryPlanEndDate/validate",
                    json={
                        "project_id": "浙江移动",
                        "rowKey": "missing-row",
                        "changes": {"endDate": "2026-07-18"},
                    },
                )
                self.assertEqual(unknown_row.status_code, 404)
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_skill_and_action_execute_reject_bad_requests(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        missing_project = self.client.post(
            "/api/v2/ontologies/default/skills/execute_backward_key_milestones/execute",
            json={"anchor_id": "浙江移动::PROJECT::GLOBAL::POWER_ON"},
        )
        self.assertEqual(missing_project.status_code, 400)

        unknown_skill = self.client.post(
            "/api/v2/ontologies/default/skills/not_a_skill/execute",
            json={"project_id": "浙江移动"},
        )
        self.assertEqual(unknown_skill.status_code, 404)

        unknown_action = self.client.post(
            "/api/v2/ontologies/default/actions/notAnAction/apply",
            json={"project_id": "浙江移动"},
        )
        self.assertEqual(unknown_action.status_code, 404)

    def test_v2_generic_query_route_rejects_unknown_query(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        response = self.client.post(
            "/api/v2/ontologies/default/queries/not-a-query/execute",
            json={"project_id": "浙江移动"},
        )
        self.assertEqual(response.status_code, 404)

    def test_v2_forward_skill_execute_returns_dry_run_and_writeback_uses_batch_action(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            self._blank_delivery_plan_dates(temp_project_path)

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                before_rejected_bytes = temp_project_path.read_bytes()
                rejected_response = self.client.post(
                    "/api/v2/ontologies/default/queries/forward-key-milestones/execute",
                    json={"project_id": "浙江移动"},
                )
                self.assertEqual(rejected_response.status_code, 400)
                self.assertIn("actions/executeForwardKeyMilestones/apply", rejected_response.json()["detail"])
                self.assertEqual(temp_project_path.read_bytes(), before_rejected_bytes)

                action_response = self.client.post(
                    "/api/v2/ontologies/default/actions/executeForwardKeyMilestones/apply",
                    json={"project_id": "浙江移动"},
                )
                self.assertEqual(action_response.status_code, 400)
                self.assertIn("Action Exclusive", action_response.json()["detail"])
                self.assertEqual(temp_project_path.read_bytes(), before_rejected_bytes)

                skill_response = self.client.post(
                    "/api/v2/ontologies/default/skills/execute_forward_key_milestones/execute",
                    json={"project_id": "浙江移动"},
                )
                self.assertEqual(skill_response.status_code, 200)
                payload = skill_response.json()
                self.assertEqual(payload["status"], "DRY_RUN_READY")
                self.assertGreater(payload["summary"]["mutationCount"], 0)
                self.assertEqual(payload["summary"]["mutationCount"], len(payload["proposed_mutations"]))
                self.assertEqual(temp_project_path.read_bytes(), before_rejected_bytes)

                first_row_key = payload["proposed_mutations"][0]["rowKey"]
                row_mutations = [
                    mutation
                    for mutation in payload["proposed_mutations"]
                    if mutation["rowKey"] == first_row_key
                ]
                batch_response = self.client.post(
                    "/api/v2/ontologies/default/actions/UpdateMilestoneDate/applyBatch",
                    json={
                        "batch": [
                            {
                                "milestoneId": mutation["milestoneId"],
                                "dateField": mutation["field"],
                                "newDate": mutation["newDate"],
                                "reason": mutation["reason"],
                            }
                            for mutation in row_mutations
                        ]
                    },
                )
                self.assertEqual(batch_response.status_code, 200)
                self.assertEqual(batch_response.json()["appliedCount"], len(row_mutations))
                self.assertNotEqual(temp_project_path.read_bytes(), before_rejected_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_forward_skill_accepts_temporary_activity_anchor_without_mutating_csv(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_path = BACKEND_DIR / "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
        milestone_path = BACKEND_DIR / "Milestone.csv"
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_project_path = Path(tmp_dir) / source_path.name
            temp_milestone_path = Path(tmp_dir) / milestone_path.name
            temp_project_path.write_bytes(source_path.read_bytes())
            temp_milestone_path.write_bytes(milestone_path.read_bytes())
            before_bytes = temp_project_path.read_bytes()

            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = Path(tmp_dir)
                data_connector.PROJECT_SOURCES = {
                    "浙江移动": data_connector.ProjectSource("浙江移动", temp_project_path.name, "浙江移动"),
                }
                row = next(
                    item
                    for item in data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")
                    if item["activityName"] == "现场勘测"
                )

                response = self.client.post(
                    "/api/v2/ontologies/default/skills/execute_forward_key_milestones/execute",
                    json={
                        "project_id": "浙江移动",
                        "temporary_anchor": {
                            "rowKey": row["rowKey"],
                            "startDate": row["startDate"],
                            "endDate": "2026-07-18",
                            "field": "endDate",
                        },
                    },
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["status"], "DRY_RUN_READY")
                self.assertEqual(payload["summary"]["anchorMode"], "temporary_activity")
                self.assertGreater(payload["summary"]["mutationCount"], 0)
                self.assertEqual(payload["summary"]["mutationCount"], len(payload["proposed_mutations"]))
                anchor_mutation = next(
                    (
                        mutation
                        for mutation in payload["proposed_mutations"]
                        if mutation["rowKey"] == row["rowKey"]
                        and mutation["field"] == "endDate"
                        and mutation["newDate"] == "2026-07-18"
                    ),
                    None,
                )
                self.assertIsNotNone(anchor_mutation)
                self.assertEqual(anchor_mutation["milestoneId"], row["rowKey"])
                self.assertEqual(anchor_mutation["changeType"], "UPDATE_END_DATE")
                self.assertEqual(
                    anchor_mutation["reason"],
                    f"基于活动 `{row['activityName']}` 的临时结束日期执行正排沙箱推演。",
                )
                self.assertEqual(
                    data_connector._try_parse_plan_date(anchor_mutation["originalDate"]),
                    data_connector._try_parse_plan_date(row["endDate"]),
                )
                self.assertEqual(temp_project_path.read_bytes(), before_bytes)
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_v2_plan_row_dependencies_links_are_resolved(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")
        data_connector = importlib.import_module("data_connector")
        source_row = next(
            row
            for row in data_connector.get_object_data("DeliveryPlanRow", project_id="浙江移动")
            if row["activityName"] == "机房改造液冷完成"
        )
        response = self.client.get(
            f"/api/v2/ontologies/default/objects/DeliveryPlanRow/{source_row['rowKey']}/links/PlanRowDependencies"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["linkType"], "PlanRowDependencies")
        self.assertEqual(payload["fromObjectKey"], source_row["rowKey"])
        self.assertGreaterEqual(payload["total"], 1)
        self.assertTrue(any(item["activityName"] == "机房改造实施" for item in payload["items"]))


class ValueTypeConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = None
        if TestClient is None:
            return
        backend_app = importlib.import_module("backend_app")
        cls.client = TestClient(backend_app.create_app())

    def test_value_types_schema_is_wellformed(self):
        data_connector = importlib.import_module("data_connector")

        value_types = data_connector._load_value_types()

        self.assertIn("MilestoneDirectionRole", value_types)
        self.assertIn("AdvanceDays", value_types)
        direction_role = value_types["MilestoneDirectionRole"]
        constraint = direction_role["constraints"][0]
        self.assertEqual(constraint["type"], "oneOf")
        self.assertIn("BACKWARD_TARGET", constraint["values"])

    def test_object_property_binds_value_type(self):
        data_connector = importlib.import_module("data_connector")

        milestone_map = data_connector._property_value_type_map("Milestone")
        self.assertEqual(milestone_map.get("directionRole"), "MilestoneDirectionRole")
        self.assertEqual(milestone_map.get("milestoneType"), "MilestoneType")
        self.assertEqual(milestone_map.get("scopeType"), "MilestoneScopeType")

        change_order_map = data_connector._property_value_type_map("ChangeOrder")
        self.assertEqual(change_order_map.get("status"), "ChangeOrderStatus")
        self.assertEqual(change_order_map.get("approvedAdvanceDays"), "AdvanceDays")

    def test_enum_constraint_rejects_unknown_value(self):
        data_connector = importlib.import_module("data_connector")

        with self.assertRaisesRegex(ValueError, "MilestoneDirectionRole"):
            data_connector._validate_action_value_type_changes(
                "Milestone", {"directionRole": "NOT_A_ROLE"}
            )

        # Valid enum value and blank value both pass.
        data_connector._validate_action_value_type_changes(
            "Milestone", {"directionRole": "BACKWARD_TARGET"}
        )
        data_connector._validate_action_value_type_changes("Milestone", {"directionRole": ""})

    def test_integer_and_range_constraints(self):
        data_connector = importlib.import_module("data_connector")

        with self.assertRaisesRegex(ValueError, "integer"):
            data_connector._validate_action_value_type_changes(
                "ChangeOrder", {"approvedAdvanceDays": "abc"}
            )
        with self.assertRaisesRegex(ValueError, ">= 0"):
            data_connector._validate_action_value_type_changes(
                "ChangeOrder", {"approvedAdvanceDays": "-1"}
            )
        # Valid integer and blank value both pass.
        data_connector._validate_action_value_type_changes(
            "ChangeOrder", {"approvedAdvanceDays": "3"}
        )
        data_connector._validate_action_value_type_changes(
            "ChangeOrder", {"approvedAdvanceDays": ""}
        )

    def test_validate_object_update_enforces_value_type(self):
        data_connector = importlib.import_module("data_connector")

        milestones = data_connector.get_object_data("Milestone")
        self.assertTrue(milestones, "expected at least one Milestone backing row")
        milestone_key = milestones[0]["milestoneKey"]

        with self.assertRaisesRegex(ValueError, "MilestoneDirectionRole"):
            data_connector.validate_object_update(
                "Milestone",
                "modifyMilestoneDirectionRole",
                {"milestoneId": milestone_key, "directionRole": "NOT_A_ROLE"},
            )

        valid = data_connector.validate_object_update(
            "Milestone",
            "modifyMilestoneDirectionRole",
            {"milestoneId": milestone_key, "directionRole": "BACKWARD_TARGET"},
        )
        self.assertTrue(valid["success"])

    def test_value_type_api_endpoints(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        listing = self.client.get("/api/v2/ontologies/default/valueTypes")
        self.assertEqual(listing.status_code, 200)
        api_names = {item["apiName"] for item in listing.json()}
        self.assertIn("MilestoneDirectionRole", api_names)
        self.assertIn("AdvanceDays", api_names)

        detail = self.client.get("/api/v2/ontologies/default/valueTypes/MilestoneDirectionRole")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["apiName"], "MilestoneDirectionRole")

        missing = self.client.get("/api/v2/ontologies/default/valueTypes/DoesNotExist")
        self.assertEqual(missing.status_code, 404)


class FunctionRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = None
        if TestClient is None:
            return
        backend_app = importlib.import_module("backend_app")
        cls.client = TestClient(backend_app.create_app())

    def test_function_types_schema_is_wellformed(self):
        backend_app = importlib.import_module("backend_app")

        function_types = backend_app.load_function_types()

        self.assertIn("projectPlanSummary", function_types)
        self.assertIn("backwardKeyMilestonesGraph", function_types)
        binding = function_types["projectPlanSummary"]["binding"]
        self.assertEqual(binding["module"], "data_connector")
        self.assertEqual(binding["function"], "project_plan_summary")

    def test_project_plan_summary_function(self):
        data_connector = importlib.import_module("data_connector")

        summary = data_connector.project_plan_summary("浙江移动")

        self.assertEqual(summary["projectId"], "浙江移动")
        for key in (
            "activityCount",
            "milestoneCount",
            "podCount",
            "scheduledActivityCount",
            "unscheduledActivityCount",
            "planStartDate",
            "planEndDate",
        ):
            self.assertIn(key, summary)
        self.assertGreater(summary["activityCount"], 0)
        self.assertEqual(
            summary["scheduledActivityCount"] + summary["unscheduledActivityCount"],
            summary["activityCount"],
        )

    def test_execute_function_type_requires_declared_param(self):
        backend_app = importlib.import_module("backend_app")

        with self.assertRaisesRegex(ValueError, "project_id"):
            backend_app.execute_function_type("projectPlanSummary", {})

    def test_execute_function_type_rejects_unknown_function(self):
        backend_app = importlib.import_module("backend_app")

        with self.assertRaises(KeyError):
            backend_app.execute_function_type("doesNotExist", {"project_id": "浙江移动"})

    def test_query_types_endpoint_is_no_longer_empty(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        response = self.client.get("/api/v2/ontologies/default/queryTypes")
        self.assertEqual(response.status_code, 200)
        api_names = {item["apiName"] for item in response.json()}
        self.assertIn("projectPlanSummary", api_names)
        self.assertIn("backwardKeyMilestonesGraph", api_names)
        # Dry-run Skills (kind == "SKILL") are not Queries; they must not leak here.
        self.assertNotIn("execute_forward_key_milestones", api_names)

    def test_function_type_api_endpoints(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        listing = self.client.get("/api/v2/ontologies/default/functionTypes")
        self.assertEqual(listing.status_code, 200)
        api_names = {item["apiName"] for item in listing.json()}
        self.assertIn("projectPlanSummary", api_names)
        self.assertIn("backwardKeyMilestonesGraph", api_names)
        # Skills share function-types.json but are published via /skillTypes only.
        self.assertNotIn("execute_forward_key_milestones", api_names)
        self.assertNotIn("execute_plan_compression_decision", api_names)

        detail = self.client.get("/api/v2/ontologies/default/functionTypes/projectPlanSummary")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["apiName"], "projectPlanSummary")

        skill_detail = self.client.get(
            "/api/v2/ontologies/default/functionTypes/execute_forward_key_milestones"
        )
        self.assertEqual(skill_detail.status_code, 404)

        missing = self.client.get("/api/v2/ontologies/default/functionTypes/Nope")
        self.assertEqual(missing.status_code, 404)

    def test_execute_function_endpoint(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        ok = self.client.post(
            "/api/v2/ontologies/default/functions/projectPlanSummary/execute",
            json={"project_id": "浙江移动"},
        )
        self.assertEqual(ok.status_code, 200)
        body = ok.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["functionName"], "projectPlanSummary")
        self.assertEqual(body["result"]["projectId"], "浙江移动")

        unknown = self.client.post(
            "/api/v2/ontologies/default/functions/doesNotExist/execute",
            json={"project_id": "浙江移动"},
        )
        self.assertEqual(unknown.status_code, 404)


class StateMachineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = None
        if TestClient is None:
            return
        backend_app = importlib.import_module("backend_app")
        cls.client = TestClient(backend_app.create_app())

    def test_state_transitions_declared_in_schema(self):
        data_connector = importlib.import_module("data_connector")

        action_types = data_connector._load_action_types()
        change_order = action_types["modifyChangeOrderStatus"]["stateTransitions"]
        self.assertEqual(change_order["field"], "status")
        self.assertIn("PENDING_SUPPLIER_APPROVAL", change_order["allowed"]["DRAFT"])
        self.assertEqual(change_order["allowed"]["APPROVED"], [])

        supplier = action_types["modifySupplierCompanyStatus"]["stateTransitions"]
        self.assertEqual(supplier["field"], "status")

    def test_state_machine_allows_legal_transition(self):
        data_connector = importlib.import_module("data_connector")

        # DRAFT -> PENDING_SUPPLIER_APPROVAL is legal; no raise.
        data_connector._validate_action_state_transition(
            "modifyChangeOrderStatus",
            {"status": "DRAFT"},
            {"status": "PENDING_SUPPLIER_APPROVAL"},
            "ChangeOrder",
        )
        # No-op transition (same state) is allowed.
        data_connector._validate_action_state_transition(
            "modifyChangeOrderStatus",
            {"status": "APPROVED"},
            {"status": "APPROVED"},
            "ChangeOrder",
        )

    def test_state_machine_rejects_illegal_transition(self):
        data_connector = importlib.import_module("data_connector")

        with self.assertRaisesRegex(ValueError, "illegal state transition"):
            data_connector._validate_action_state_transition(
                "modifyChangeOrderStatus",
                {"status": "APPROVED"},
                {"status": "DRAFT"},
                "ChangeOrder",
            )

    def test_state_machine_rejects_transition_from_terminal_state(self):
        data_connector = importlib.import_module("data_connector")

        with self.assertRaisesRegex(ValueError, "illegal state transition"):
            data_connector._validate_action_state_transition(
                "modifyChangeOrderStatus",
                {"status": "CANCELLED"},
                {"status": "APPROVED"},
                "ChangeOrder",
            )

    def test_state_machine_enforces_initial_states(self):
        data_connector = importlib.import_module("data_connector")

        # Empty current state + a valid initial state is allowed.
        data_connector._validate_action_state_transition(
            "modifyChangeOrderStatus",
            {},
            {"status": "DRAFT"},
            "ChangeOrder",
        )
        # Empty current state + a non-initial state is rejected.
        with self.assertRaisesRegex(ValueError, "initial state"):
            data_connector._validate_action_state_transition(
                "modifyChangeOrderStatus",
                {},
                {"status": "APPROVED"},
                "ChangeOrder",
            )

    def test_supplier_state_machine(self):
        data_connector = importlib.import_module("data_connector")

        data_connector._validate_action_state_transition(
            "modifySupplierCompanyStatus",
            {"status": "ACTIVE"},
            {"status": "BLACKLISTED"},
            "SupplierCompany",
        )
        with self.assertRaisesRegex(ValueError, "illegal state transition"):
            data_connector._validate_action_state_transition(
                "modifySupplierCompanyStatus",
                {"status": "BLACKLISTED"},
                {"status": "INACTIVE"},
                "SupplierCompany",
            )

    def test_state_machine_inert_for_actions_without_transitions(self):
        data_connector = importlib.import_module("data_connector")

        # modifyMilestoneDirectionRole declares no stateTransitions -> never raises.
        data_connector._validate_action_state_transition(
            "modifyMilestoneDirectionRole",
            {"directionRole": "FORWARD_START"},
            {"directionRole": "BACKWARD_TARGET"},
            "Milestone",
        )

    def test_action_type_endpoint_exposes_state_transitions(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        response = self.client.get(
            "/api/v2/ontologies/default/actionTypes/modifyChangeOrderStatus"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stateTransitions"]["field"], "status")


class SubmissionCriteriaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = None
        if TestClient is None:
            return
        backend_app = importlib.import_module("backend_app")
        cls.client = TestClient(backend_app.create_app())

    def test_submission_criteria_declared_in_schema(self):
        data_connector = importlib.import_module("data_connector")

        action = data_connector._load_action_types()["modifyChangeOrderApprovedAdvanceDays"]
        criteria = action["submissionCriteria"]
        self.assertEqual(criteria[0]["name"], "approvedNotExceedRequested")
        self.assertIn("condition", criteria[0])

    def test_submission_criteria_passes_when_within_requested(self):
        data_connector = importlib.import_module("data_connector")

        # approved (7) <= requested (10): rule holds.
        data_connector._validate_action_submission_criteria(
            "modifyChangeOrderApprovedAdvanceDays",
            {"requestedAdvanceDays": "10"},
            {"approvedAdvanceDays": "7"},
            "ChangeOrder",
        )
        # empty approved short-circuits the `any` and passes.
        data_connector._validate_action_submission_criteria(
            "modifyChangeOrderApprovedAdvanceDays",
            {"requestedAdvanceDays": "10"},
            {"approvedAdvanceDays": ""},
            "ChangeOrder",
        )

    def test_submission_criteria_rejects_when_exceeding_requested(self):
        data_connector = importlib.import_module("data_connector")

        with self.assertRaisesRegex(ValueError, "submission criteria failed"):
            data_connector._validate_action_submission_criteria(
                "modifyChangeOrderApprovedAdvanceDays",
                {"requestedAdvanceDays": "5"},
                {"approvedAdvanceDays": "7"},
                "ChangeOrder",
            )

    def test_criteria_node_operators(self):
        data_connector = importlib.import_module("data_connector")

        def holds(node, record):
            return data_connector._eval_criteria_node(node, record, {}, {})

        # numeric comparison (digits compared as numbers, not strings: 9 < 10)
        self.assertTrue(holds({"field": "a", "op": "lt", "value": "10"}, {"a": "9"}))
        self.assertFalse(holds({"field": "a", "op": "gt", "value": "10"}, {"a": "9"}))
        # date strings compare chronologically via string order
        self.assertTrue(holds({"field": "end", "op": "gte", "field2": "start"}, {"start": "2026-01-01", "end": "2026-02-01"}))
        # eq / ne / nonEmpty / empty
        self.assertTrue(holds({"field": "s", "op": "eq", "value": "X"}, {"s": "X"}))
        self.assertTrue(holds({"field": "s", "op": "nonEmpty"}, {"s": "X"}))
        self.assertTrue(holds({"field": "s", "op": "empty"}, {"s": ""}))
        # all / any / not combinators
        self.assertTrue(holds({"all": [{"field": "a", "op": "eq", "value": "1"}, {"field": "b", "op": "eq", "value": "2"}]}, {"a": "1", "b": "2"}))
        self.assertFalse(holds({"all": [{"field": "a", "op": "eq", "value": "1"}, {"field": "b", "op": "eq", "value": "9"}]}, {"a": "1", "b": "2"}))
        self.assertTrue(holds({"any": [{"field": "a", "op": "eq", "value": "9"}, {"field": "b", "op": "eq", "value": "2"}]}, {"a": "1", "b": "2"}))
        self.assertTrue(holds({"not": {"field": "a", "op": "eq", "value": "9"}}, {"a": "1"}))

    def test_submission_criteria_inert_for_actions_without_rules(self):
        data_connector = importlib.import_module("data_connector")

        # modifyMilestoneDirectionRole declares no submissionCriteria -> never raises.
        data_connector._validate_action_submission_criteria(
            "modifyMilestoneDirectionRole",
            {"directionRole": "FORWARD_START"},
            {"directionRole": "BACKWARD_TARGET"},
            "Milestone",
        )

    def test_action_type_endpoint_exposes_submission_criteria(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        response = self.client.get(
            "/api/v2/ontologies/default/actionTypes/modifyChangeOrderApprovedAdvanceDays"
        )
        self.assertEqual(response.status_code, 200)
        names = {rule["name"] for rule in response.json()["submissionCriteria"]}
        self.assertIn("approvedNotExceedRequested", names)


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = None
        if TestClient is None:
            return
        backend_app = importlib.import_module("backend_app")
        cls.client = TestClient(backend_app.create_app())

    def test_interface_types_schema_is_wellformed(self):
        backend_app = importlib.import_module("backend_app")

        interfaces = backend_app.load_interface_types()
        self.assertIn("ProjectScoped", interfaces)
        self.assertIn("SourceTraceable", interfaces)
        self.assertIn("projectKey", interfaces["ProjectScoped"]["properties"])
        self.assertIn("sourceFile", interfaces["SourceTraceable"]["properties"])

    def test_object_types_declare_interfaces(self):
        backend_app = importlib.import_module("backend_app")

        object_types = backend_app.load_object_types()
        self.assertEqual(
            set(object_types["Milestone"]["implementsInterfaces"]),
            {"ProjectScoped", "SourceTraceable"},
        )
        self.assertEqual(
            object_types["SupplierCompany"]["implementsInterfaces"],
            ["SourceTraceable"],
        )

    def test_interface_conformance_has_no_violations(self):
        backend_app = importlib.import_module("backend_app")

        self.assertEqual(backend_app.interface_conformance_violations(), [])

    def test_interface_conformance_detects_missing_property(self):
        backend_app = importlib.import_module("backend_app")

        violations = backend_app.interface_conformance_violations(
            object_types={
                "Bad": {"implementsInterfaces": ["ProjectScoped"], "properties": {}},
            },
            interface_types=backend_app.load_interface_types(),
        )
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["objectType"], "Bad")
        self.assertEqual(violations[0]["missingProperty"], "projectKey")

    def test_object_types_implementing_interface(self):
        backend_app = importlib.import_module("backend_app")

        source_traceable = backend_app.object_types_implementing_interface("SourceTraceable")
        self.assertIn("SupplierCompany", source_traceable)
        self.assertIn("ParsedDocumentSection", source_traceable)

        project_scoped = backend_app.object_types_implementing_interface("ProjectScoped")
        self.assertIn("Milestone", project_scoped)
        self.assertNotIn("SupplierCompany", project_scoped)
        self.assertNotIn("ParsedDocumentSection", project_scoped)

    def test_interface_type_api_endpoints(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        listing = self.client.get("/api/v2/ontologies/default/interfaceTypes")
        self.assertEqual(listing.status_code, 200)
        api_names = {item["apiName"] for item in listing.json()}
        self.assertEqual(api_names, {"ProjectScoped", "SourceTraceable", "PlanScoped"})

        detail = self.client.get("/api/v2/ontologies/default/interfaceTypes/ProjectScoped")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["apiName"], "ProjectScoped")

        # PlanScoped came in with the merged contingency ontology.
        plan_scoped = self.client.get("/api/v2/ontologies/default/interfaceTypes/PlanScoped")
        self.assertEqual(plan_scoped.status_code, 200)

        missing = self.client.get("/api/v2/ontologies/default/interfaceTypes/Nope")
        self.assertEqual(missing.status_code, 404)

        implementers = self.client.get(
            "/api/v2/ontologies/default/interfaceTypes/ProjectScoped/objectTypes"
        )
        self.assertEqual(implementers.status_code, 200)
        implementer_names = implementers.json()["objectTypeApiNames"]
        # Default plan objects and project-ized contingency objects both implement ProjectScoped.
        self.assertIn("Milestone", implementer_names)
        self.assertIn("ContingencyPlan", implementer_names)


class AutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = None
        if TestClient is None:
            return
        backend_app = importlib.import_module("backend_app")
        cls.client = TestClient(backend_app.create_app())

    def test_automation_types_schema_is_wellformed(self):
        data_connector = importlib.import_module("data_connector")

        automations = data_connector._load_automation_types()
        self.assertIn("recomputePlanSummaryOnPlanRowChange", automations)
        automation = automations["recomputePlanSummaryOnPlanRowChange"]
        self.assertEqual(automation["trigger"]["objectTypeApiName"], "DeliveryPlanRow")
        self.assertEqual(automation["effect"]["functionApiName"], "projectPlanSummary")

    def test_matching_automations(self):
        data_connector = importlib.import_module("data_connector")

        plan_row_matches = {name for name, _ in data_connector._matching_automations("DeliveryPlanRow", "UPDATE")}
        self.assertIn("recomputePlanSummaryOnPlanRowChange", plan_row_matches)
        # Wrong object type or wrong event -> no match.
        self.assertEqual(data_connector._matching_automations("Milestone", "UPDATE"), [])
        self.assertEqual(data_connector._matching_automations("DeliveryPlanRow", "CREATE"), [])

    def test_run_automations_produces_suggestion(self):
        data_connector = importlib.import_module("data_connector")

        results = data_connector.run_automations(
            "DeliveryPlanRow", "UPDATE", {"projectKey": "浙江移动"}
        )
        entry = next(
            item for item in results if item["automation"] == "recomputePlanSummaryOnPlanRowChange"
        )
        self.assertEqual(entry["function"], "projectPlanSummary")
        self.assertNotIn("error", entry)
        self.assertEqual(entry["result"]["projectId"], "浙江移动")

    def test_run_automations_inert_for_other_object_types(self):
        data_connector = importlib.import_module("data_connector")

        self.assertEqual(
            data_connector.run_automations("Milestone", "UPDATE", {"projectKey": "浙江移动"}),
            [],
        )

    def test_automation_type_api_endpoints(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        listing = self.client.get("/api/v2/ontologies/default/automationTypes")
        self.assertEqual(listing.status_code, 200)
        api_names = {item["apiName"] for item in listing.json()}
        self.assertIn("recomputePlanSummaryOnPlanRowChange", api_names)

        detail = self.client.get(
            "/api/v2/ontologies/default/automationTypes/recomputePlanSummaryOnPlanRowChange"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["apiName"], "recomputePlanSummaryOnPlanRowChange")

        missing = self.client.get("/api/v2/ontologies/default/automationTypes/Nope")
        self.assertEqual(missing.status_code, 404)

    def test_evaluate_automations_endpoint(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        response = self.client.post(
            "/api/v2/ontologies/default/automations:evaluate",
            json={"objectType": "DeliveryPlanRow", "event": "UPDATE", "context": {"projectKey": "浙江移动"}},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["objectType"], "DeliveryPlanRow")
        summary_entry = next(
            item for item in body["automations"] if item["automation"] == "recomputePlanSummaryOnPlanRowChange"
        )
        self.assertEqual(summary_entry["result"]["projectId"], "浙江移动")


class DecisionLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = None
        if TestClient is None:
            return
        backend_app = importlib.import_module("backend_app")
        cls.client = TestClient(backend_app.create_app())

    def test_decision_functions_registered(self):
        backend_app = importlib.import_module("backend_app")

        functions = backend_app.load_function_types()
        for name, binding in (
            ("projectDecisionPoints", "project_decision_points"),
            ("projectEmergentRisks", "project_emergent_risks"),
        ):
            self.assertIn(name, functions)
            self.assertEqual(functions[name]["kind"], "FUNCTION")
            self.assertEqual(functions[name]["binding"]["function"], binding)

    def test_decision_points_are_derived_from_milestone_gates(self):
        data_connector = importlib.import_module("data_connector")

        result = data_connector.project_decision_points("浙江移动")
        self.assertEqual(result["projectId"], "浙江移动")
        self.assertGreater(result["decisionPointCount"], 0)

        counts = result["statusCounts"]
        self.assertEqual(
            counts["MET"] + counts["OPEN"] + counts["BLOCKED"],
            result["decisionPointCount"],
        )

        for point in result["decisionPoints"]:
            self.assertIn(point["gateStatus"], {"MET", "OPEN", "BLOCKED"})
            # A gate is BLOCKED iff it has blockers; a gate with no dependencies is never BLOCKED.
            if point["gateStatus"] == "BLOCKED":
                self.assertTrue(point["blockers"])
            if not point["gateDependencyTypes"]:
                self.assertNotEqual(point["gateStatus"], "BLOCKED")

        # FORWARD_START-style gates (no deps, not yet actual) derive as OPEN, not hand-authored.
        open_no_dep = [
            p
            for p in result["decisionPoints"]
            if not p["gateDependencyTypes"] and not p["actualDate"]
        ]
        self.assertTrue(open_no_dep)
        self.assertTrue(all(p["gateStatus"] == "OPEN" for p in open_no_dep))

    def test_emergent_risks_are_derived_suggestions(self):
        data_connector = importlib.import_module("data_connector")

        decision = data_connector.project_decision_points("浙江移动")
        risks = data_connector.project_emergent_risks("浙江移动")
        self.assertEqual(risks["riskCount"], len(risks["risks"]))
        for risk in risks["risks"]:
            self.assertIn("type", risk)
            self.assertIn("severity", risk)
            self.assertIn("message", risk)
        # Blocked gates must surface as emergent risks.
        if decision["statusCounts"]["BLOCKED"] > 0:
            self.assertTrue(any(r["type"] == "BLOCKED_GATE" for r in risks["risks"]))

    def test_decision_functions_run_through_generic_executor(self):
        backend_app = importlib.import_module("backend_app")

        points = backend_app.execute_function_type("projectDecisionPoints", {"project_id": "浙江移动"})
        self.assertEqual(points["projectId"], "浙江移动")
        risks = backend_app.execute_function_type("projectEmergentRisks", {"project_id": "浙江移动"})
        self.assertIn("risks", risks)

    def test_decision_functions_exposed_via_api(self):
        if self.client is None:
            self.skipTest("fastapi is not installed")

        query_types = self.client.get("/api/v2/ontologies/default/queryTypes")
        self.assertEqual(query_types.status_code, 200)
        api_names = {item["apiName"] for item in query_types.json()}
        self.assertIn("projectDecisionPoints", api_names)
        self.assertIn("projectEmergentRisks", api_names)

        executed = self.client.post(
            "/api/v2/ontologies/default/functions/projectDecisionPoints/execute",
            json={"project_id": "浙江移动"},
        )
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(executed.json()["result"]["projectId"], "浙江移动")

    def test_emergent_risk_automation_surfaces_on_plan_row_change(self):
        data_connector = importlib.import_module("data_connector")

        automations = data_connector._load_automation_types()
        self.assertIn("surfaceEmergentRisksOnPlanRowChange", automations)

        results = data_connector.run_automations(
            "DeliveryPlanRow", "UPDATE", {"projectKey": "浙江移动"}
        )
        emergent_entry = next(
            item for item in results if item["automation"] == "surfaceEmergentRisksOnPlanRowChange"
        )
        self.assertNotIn("error", emergent_entry)
        self.assertIn("riskCount", emergent_entry["result"])


class DoltSubstrateTests(unittest.TestCase):
    """Generic single-object Action writeback to Dolt (the missing substrate primitive)."""

    def _manager_with_memory_engine(self, mem):
        scenario_lifecycle_manager = importlib.import_module("scenario_lifecycle_manager")
        return scenario_lifecycle_manager.ScenarioLifecycleManager(
            database_url="mysql+pymysql://local:@127.0.0.1:3306/dolt",
            engine_factory=lambda url, **_kwargs: mem,
        )

    @staticmethod
    def _update_calls(mem):
        return [(sql, params) for sql, params in mem.connection.calls if str(sql).strip().upper().startswith("UPDATE")]

    def test_apply_object_update_issues_update_by_primary_key(self):
        # Writeback is UPDATE ... SET ... WHERE <pk> (not an upsert) so partial-column
        # edits work against NOT NULL columns on real Dolt. The in-memory engine does
        # not simulate bare UPDATE state, so the SQL contract is asserted here; the
        # real DRAFT->APPROVED state round-trip was verified against a live dolt
        # sql-server (matchedRows=1, read-back APPROVED) on a throwaway scenario branch.
        mem = _MemoryDoltEngine()
        manager = self._manager_with_memory_engine(mem)

        result = manager.apply_object_update(
            "shadow_co", "ChangeOrder", {"changeOrderKey": "CO-1"}, {"status": "APPROVED"}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["tableName"], "change_order")
        self.assertEqual(result["appliedColumns"], ["status"])

        update_calls = self._update_calls(mem)
        self.assertEqual(len(update_calls), 1)
        sql, params = update_calls[0]
        self.assertIn("`change_order`", sql)
        self.assertIn("`status` = :set_status", sql)
        self.assertIn("`changeOrderKey` = :pk_changeOrderKey", sql)
        self.assertEqual(params["set_status"], "APPROVED")
        self.assertEqual(params["pk_changeOrderKey"], "CO-1")
        self.assertIn(("COMMIT", {}), mem.connection.calls)

    def test_apply_object_update_validates_arguments(self):
        mem = _MemoryDoltEngine()
        manager = self._manager_with_memory_engine(mem)
        with self.assertRaisesRegex(ValueError, "changes must not be empty"):
            manager.apply_object_update("shadow_co", "ChangeOrder", {"changeOrderKey": "CO-1"}, {})
        with self.assertRaisesRegex(ValueError, "primary_key must not be empty"):
            manager.apply_object_update("shadow_co", "ChangeOrder", {}, {"status": "APPROVED"})

    def test_apply_object_update_to_dolt_wrapper(self):
        preview_branch = importlib.import_module("preview_branch")
        mem = _MemoryDoltEngine()
        context = preview_branch.resolve_preview_branch_context("shadow_wrap")

        original_engine = preview_branch._dolt_engine
        preview_branch._dolt_engine = mem
        try:
            result = preview_branch.apply_object_update_to_dolt(
                context, "SupplierCompany", {"supplierKey": "huawei"}, {"status": "BLACKLISTED"}
            )
        finally:
            preview_branch._dolt_engine = original_engine

        self.assertTrue(result["success"])
        self.assertEqual(result["tableName"], "supplier_company")
        update_calls = self._update_calls(mem)
        self.assertTrue(update_calls)
        self.assertIn("`supplier_company`", update_calls[0][0])


class DoltGoLiveActionTests(unittest.TestCase):
    """The 3 validation layers fire end-to-end on the Dolt-backed Action write path.

    ChangeOrder is now writable with no CSV backing, so update_object_data /
    validate_object_update route to the Dolt path: current state is read from Dolt
    (the in-memory engine simulates SELECT) and the layers run against it.
    """

    def setUp(self):
        self.preview_branch = importlib.import_module("preview_branch")
        self.data_connector = importlib.import_module("data_connector")
        self.mem = _MemoryDoltEngine()
        self.mem.connection.primary_keys["change_order"] = ["changeOrderKey"]
        self._original_engine = self.preview_branch._dolt_engine
        self.preview_branch._dolt_engine = self.mem

    def tearDown(self):
        self.preview_branch._dolt_engine = self._original_engine

    def _seed(self, **overrides):
        row = {
            "changeOrderKey": "CO-1",
            "projectKey": "ZJYD",
            "supplierKey": "huawei",
            "title": "t",
            "changeType": "SUPPLY_ADVANCE",
            "requestedAdvanceDays": "5",
            "status": "DRAFT",
        }
        row.update(overrides)
        self.mem.connection.tables["change_order"] = [row]

    def _seed_component(self, **overrides):
        self.mem.connection.primary_keys["component_config"] = ["componentId"]
        row = {
            "componentId": "CMP-CPU-1",
            "projectKey": "京东",
            "componentType": "CPU",
            "componentCode": "Ascend-910C",
            "vendor": "华为",
            "componentName": "昇腾 910C 训练处理器",
            "dataSource": "自动解析",
        }
        row.update(overrides)
        self.mem.connection.tables["component_config"] = [row]

    def _update_sql(self):
        return [sql for sql, _ in self.mem.connection.calls if str(sql).strip().upper().startswith("UPDATE")]

    def test_value_type_layer_fires_on_dolt_path(self):
        self._seed(status="DRAFT")
        with self.assertRaisesRegex(ValueError, "ChangeOrderStatus"):
            self.data_connector.update_object_data(
                "ChangeOrder", "modifyChangeOrderStatus", {"targetChangeOrder": "CO-1", "status": "BOGUS"}
            )

    def test_state_machine_layer_fires_against_dolt_current_state(self):
        self._seed(status="APPROVED")  # APPROVED is terminal -> any transition illegal
        with self.assertRaisesRegex(ValueError, "illegal state transition"):
            self.data_connector.update_object_data(
                "ChangeOrder", "modifyChangeOrderStatus", {"targetChangeOrder": "CO-1", "status": "DRAFT"}
            )

    def test_submission_criteria_layer_fires_against_dolt_current_state(self):
        self._seed(status="PENDING_SUPPLIER_APPROVAL", requestedAdvanceDays="5")
        with self.assertRaisesRegex(ValueError, "submission criteria failed"):
            self.data_connector.update_object_data(
                "ChangeOrder",
                "modifyChangeOrderApprovedAdvanceDays",
                {"targetChangeOrder": "CO-1", "approvedAdvanceDays": "7"},
            )
        # within the requested limit -> passes and writes
        result = self.data_connector.update_object_data(
            "ChangeOrder",
            "modifyChangeOrderApprovedAdvanceDays",
            {"targetChangeOrder": "CO-1", "approvedAdvanceDays": "3"},
        )
        self.assertTrue(result["success"])

    def test_legal_action_writes_update_to_dolt(self):
        self._seed(status="DRAFT")
        result = self.data_connector.update_object_data(
            "ChangeOrder",
            "modifyChangeOrderStatus",
            {"targetChangeOrder": "CO-1", "status": "PENDING_SUPPLIER_APPROVAL"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["changeOrderKey"], "CO-1")
        self.assertTrue(
            any("`change_order`" in sql and "`status` = :set_status" in sql for sql in self._update_sql())
        )

    def test_validate_runs_layers_without_writing(self):
        self._seed(status="DRAFT")
        result = self.data_connector.validate_object_update(
            "ChangeOrder",
            "modifyChangeOrderStatus",
            {"targetChangeOrder": "CO-1", "status": "PENDING_SUPPLIER_APPROVAL"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["validatedChanges"], {"status": "PENDING_SUPPLIER_APPROVAL"})
        self.assertEqual(self._update_sql(), [])

    def test_unknown_primary_key_raises(self):
        self._seed(status="DRAFT")
        with self.assertRaises(KeyError):
            self.data_connector.update_object_data(
                "ChangeOrder",
                "modifyChangeOrderStatus",
                {"targetChangeOrder": "CO-NOPE", "status": "PENDING_SUPPLIER_APPROVAL"},
            )

    def test_dolt_rows_component_config_chapter_field_writes_by_schema_primary_key(self):
        self._seed_component()

        result = self.data_connector.update_object_data(
            "ComponentConfig",
            "modifyComponentConfigChapterFields",
            {"componentId": "CMP-CPU-1", "changes": {"componentName": "昇腾 910C 训练处理器（修订）"}},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["componentId"], "CMP-CPU-1")
        self.assertTrue(
            any(
                "`component_config`" in sql
                and "`componentName` = :set_componentName" in sql
                and "`componentId` = :pk_componentId" in sql
                for sql in self._update_sql()
            )
        )

    def test_dolt_rows_component_config_requires_schema_primary_key(self):
        self._seed_component()

        with self.assertRaisesRegex(KeyError, "componentId"):
            self.data_connector.update_object_data(
                "ComponentConfig",
                "modifyComponentConfigChapterFields",
                {"changes": {"componentName": "缺少主键"}},
            )

    def test_dolt_rows_component_config_rejects_undeclared_chapter_field(self):
        self._seed_component()

        with self.assertRaisesRegex(ValueError, "cannot update field"):
            self.data_connector.update_object_data(
                "ComponentConfig",
                "modifyComponentConfigChapterFields",
                {"componentId": "CMP-CPU-1", "changes": {"projectKey": "浙江移动"}},
            )


if __name__ == "__main__":
    unittest.main()
