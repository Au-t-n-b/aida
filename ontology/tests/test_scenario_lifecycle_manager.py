import csv
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class _ManagerResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def first(self):
        if self._scalar is not None:
            return (self._scalar,)
        return self._rows[0] if self._rows else None

    def mappings(self):
        return SimpleNamespace(all=lambda: list(self._rows))


class _ManagerConnection:
    def __init__(self, *, fail_on_insert_batch=None):
        self.calls = []
        self.fail_on_insert_batch = fail_on_insert_batch
        self.insert_batches = 0
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params))
        if "HASHOF('HEAD')" in sql:
            return _ManagerResult(scalar="hash-before-ingest")
        if "FROM dolt_branches" in sql:
            return _ManagerResult()
        if "KEY_COLUMN_USAGE" in sql:
            return _ManagerResult([{"COLUMN_NAME": "rowKey"}])
        if sql.startswith("INSERT INTO"):
            self.insert_batches += 1
            if self.fail_on_insert_batch == self.insert_batches:
                raise RuntimeError("simulated chunk failure")
        return _ManagerResult()

    def commit(self):
        self.calls.append(("COMMIT", None))

    def rollback(self):
        self.calls.append(("ROLLBACK", None))


class _ManagerEngine:
    def __init__(self, url, *, fail_on_insert_batch=None):
        self.url = url
        self.disposed = False
        self.connection = _ManagerConnection(fail_on_insert_batch=fail_on_insert_batch)

    def connect(self):
        return self.connection

    def dispose(self):
        self.disposed = True


class _IngestConnection(_ManagerConnection):
    """Like _ManagerConnection but reports that any queried branch already exists."""

    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM dolt_branches" in sql:
            self.calls.append((sql, params))
            return _ManagerResult([{"ok": 1}])
        return super().execute(statement, params)


class _IngestEngine(_ManagerEngine):
    def __init__(self, url, **kwargs):
        super().__init__(url, **kwargs)
        self.connection = _IngestConnection()


class ScenarioLifecycleManagerTests(unittest.TestCase):
    def test_branch_engines_are_cached_by_branch_and_disposed(self):
        from scenario_lifecycle_manager import ScenarioLifecycleManager

        created = []

        def engine_factory(url, **_kwargs):
            engine = _ManagerEngine(url)
            created.append(engine)
            return engine

        manager = ScenarioLifecycleManager(
            database_url="mysql+pymysql://admin:@127.0.0.1:3306/dolt",
            engine_factory=engine_factory,
        )

        first = manager.get_scenario_engine("sim_20260603_a")
        second = manager.get_scenario_engine("sim_20260603_a")
        other = manager.get_scenario_engine("sim_20260603_b")

        self.assertIs(first, second)
        self.assertIsNot(first, other)
        self.assertEqual(first.url, "mysql+pymysql://admin:@127.0.0.1:3306/dolt/sim_20260603_a")
        self.assertEqual(other.url, "mysql+pymysql://admin:@127.0.0.1:3306/dolt/sim_20260603_b")

        manager.dispose_scenario_engine("sim_20260603_a")

        self.assertTrue(first.disposed)
        replacement = manager.get_scenario_engine("sim_20260603_a")
        self.assertIsNot(replacement, first)
        self.assertEqual(len(created), 3)

    def test_preview_branch_write_uses_branch_bound_engine_without_checkout(self):
        from scenario_lifecycle_manager import ScenarioLifecycleManager

        engines = {}

        def engine_factory(url, **_kwargs):
            return engines.setdefault(url, _ManagerEngine(url))

        manager = ScenarioLifecycleManager(
            database_url="mysql+pymysql://admin:@127.0.0.1:3306/dolt",
            engine_factory=engine_factory,
        )

        result = manager.apply_update_milestone_date_batch(
            "shadow_sim_789",
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

        branch_engine = engines["mysql+pymysql://admin:@127.0.0.1:3306/dolt/shadow_sim_789"]
        sql_calls = [sql for sql, _params in branch_engine.connection.calls]
        self.assertTrue(result["success"])
        self.assertFalse(any("dolt_checkout" in sql for sql in sql_calls))
        self.assertTrue(any("UPDATE `delivery_plan_row`" in sql for sql in sql_calls))
        self.assertTrue(any("CALL dolt_commit" in sql for sql in sql_calls))

    def test_csv_ingest_resets_to_pre_ingest_hash_when_a_chunk_fails(self):
        from scenario_lifecycle_manager import ScenarioLifecycleManager

        engines = {}

        def engine_factory(url, **_kwargs):
            fail_batch = 3 if url.endswith("/shadow_sim_789") else None
            return engines.setdefault(url, _ManagerEngine(url, fail_on_insert_batch=fail_batch))

        manager = ScenarioLifecycleManager(
            database_url="mysql+pymysql://admin:@127.0.0.1:3306/dolt",
            engine_factory=engine_factory,
            ingest_chunk_size=2,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "rows.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["rowKey", "startDate"])
                writer.writeheader()
                for index in range(5):
                    writer.writerow({"rowKey": f"row-{index}", "startDate": "2026-07-01"})

            with self.assertRaises(RuntimeError):
                manager.ingest_simulation_csv("shadow_sim_789", str(csv_path), "delivery_plan_row")

        branch_engine = engines["mysql+pymysql://admin:@127.0.0.1:3306/dolt/shadow_sim_789"]
        sql_calls = [sql for sql, _params in branch_engine.connection.calls]
        self.assertIn("ROLLBACK", sql_calls)
        self.assertTrue(any("CALL dolt_reset('--hard', :target_hash)" in sql for sql in sql_calls))
        self.assertTrue(
            any(params == {"target_hash": "hash-before-ingest"} for _sql, params in branch_engine.connection.calls)
        )

    def test_environment_simulation_publish_is_rejected_and_engine_is_disposed(self):
        from scenario_lifecycle_manager import ScenarioLifecycleManager, ScenarioMergeRejectedError

        engines = {}

        def engine_factory(url, **_kwargs):
            return engines.setdefault(url, _ManagerEngine(url))

        manager = ScenarioLifecycleManager(
            database_url="mysql+pymysql://admin:@127.0.0.1:3306/dolt",
            engine_factory=engine_factory,
        )
        engine = manager.get_scenario_engine("shadow_sim_789")

        with self.assertRaises(ScenarioMergeRejectedError):
            manager.resolve_scenario("shadow_sim_789", accept=True, is_env_simulation=True)

        self.assertTrue(engine.disposed)

    def test_dataset_commit_on_preview_branch_delegates_csv_ingest_to_scenario_manager(self):
        dataset_service = importlib.import_module("dataset_service")
        preview_branch = importlib.import_module("preview_branch")

        class FakeScenarioManager:
            def __init__(self):
                self.ingests = []

            def ingest_simulation_csv(self, branch_name, csv_file_path, target_table):
                self.ingests.append((branch_name, csv_file_path, target_table))
                return {"rowsWritten": 2}

        fake_manager = FakeScenarioManager()
        object_types = {
            "DeliveryPlanRow": {
                "apiName": "DeliveryPlanRow",
                "primaryKeyPropertyApiNames": ["rowKey"],
                "properties": {
                    "rowKey": {"apiName": "rowKey", "dataType": {"type": "string"}, "required": True},
                    "startDate": {"apiName": "startDate", "dataType": {"type": "string"}},
                },
            }
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            service = dataset_service.LocalDatasetService(
                registry_path=Path(tmp_dir) / "registry.json",
                staging_root=Path(tmp_dir) / "staging",
                engine=_ManagerEngine("memory://main"),
                scenario_manager=fake_manager,
            )
            dataset = service.create_dataset(
                name="DeliveryPlanRow",
                object_type="DeliveryPlanRow",
                object_types=object_types,
            )
            transaction = service.create_transaction(dataset["datasetRid"], "UPDATE")
            service.upload_file(
                dataset["datasetRid"],
                transaction["transactionRid"],
                b"rowKey,startDate\nrow-1,2026-07-01\nrow-2,2026-07-02\n",
                file_name="rows.csv",
            )
            context = preview_branch.resolve_preview_branch_context("shadow_sim_789")
            with preview_branch.use_preview_branch(context):
                result = service.commit_transaction(dataset["datasetRid"], transaction["transactionRid"])

        self.assertEqual(result["rowsWritten"], 2)
        self.assertEqual(len(fake_manager.ingests), 1)
        branch_name, staged_path, target_table = fake_manager.ingests[0]
        self.assertEqual(branch_name, "shadow_sim_789")
        self.assertTrue(staged_path.endswith("rows.csv"))
        self.assertEqual(target_table, "delivery_plan_row")

    def test_dataset_branch_routes_use_official_foundry_shape(self):
        try:
            from fastapi.testclient import TestClient
        except ModuleNotFoundError:
            self.skipTest("fastapi is not installed")

        backend_app = importlib.import_module("backend_app")
        client = TestClient(backend_app.create_app())
        expected = {"data": [{"branchId": "shadow_sim_789", "rid": "ri.foundry.main.branch.shadow_sim_789"}]}

        with patch.object(backend_app, "list_dataset_branches", return_value=expected) as list_branches:
            response = client.get("/api/v1/datasets/ri.foundry.main.dataset.demo/branches")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        list_branches.assert_called_once_with("ri.foundry.main.dataset.demo")


    def test_ingest_and_merge_overlays_pipeline_onto_main_with_ours(self):
        from scenario_lifecycle_manager import ScenarioLifecycleManager

        engines = {}

        def engine_factory(url, **_kwargs):
            return engines.setdefault(url, _IngestEngine(url))

        manager = ScenarioLifecycleManager(
            database_url="mysql+pymysql://admin:@127.0.0.1:3306/dolt",
            engine_factory=engine_factory,
        )

        result = manager.ingest_and_merge(
            "delivery_plan_row",
            [
                {"rowKey": "k1", "startDate": "2026-07-01"},
                {"rowKey": "k2", "startDate": "2026-07-02"},
            ],
            columns=["rowKey", "startDate"],
            primary_keys=["rowKey"],
        )

        self.assertEqual(result["status"], "MERGED")
        self.assertEqual(result["ingestBranch"], "ingest")
        self.assertEqual(result["rowsWritten"], 2)

        ingest_sql = [sql for sql, _p in engines["mysql+pymysql://admin:@127.0.0.1:3306/dolt/ingest"].connection.calls]
        main_sql = [sql for sql, _p in engines["mysql+pymysql://admin:@127.0.0.1:3306/dolt/main"].connection.calls]
        self.assertTrue(
            any("INSERT INTO `delivery_plan_row`" in sql and "ON DUPLICATE KEY UPDATE" in sql for sql in ingest_sql)
        )
        self.assertTrue(any("CALL dolt_merge" in sql for sql in main_sql))
        self.assertTrue(any("dolt_conflicts_resolve('--ours'" in sql for sql in main_sql))
        self.assertFalse(any("dolt_checkout" in sql for sql in ingest_sql + main_sql))

    def test_reserved_ingest_branch_cannot_be_used_as_scenario(self):
        from scenario_lifecycle_manager import ScenarioLifecycleManager

        manager = ScenarioLifecycleManager(
            database_url="mysql+pymysql://admin:@127.0.0.1:3306/dolt",
            engine_factory=lambda url, **_kwargs: _ManagerEngine(url),
        )

        with self.assertRaises(ValueError):
            manager.create_scenario("ingest")


class _RecordingConnection:
    """Connection fake that records SQL/params and returns canned mapping rows."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        self.calls.append((str(statement), dict(params or {})))
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: list(self.rows)))

    def commit(self):
        return None


class _RecordingEngine:
    def __init__(self, rows):
        self.connection = _RecordingConnection(rows)

    def connect(self):
        return self.connection


class ObjectHistoryReadTests(unittest.TestCase):
    """A/B/C/D: object history, time-travel, diff and commit author attribution."""

    def _manager(self, rows):
        from scenario_lifecycle_manager import ScenarioLifecycleManager

        engine = _RecordingEngine(rows)
        manager = ScenarioLifecycleManager(
            database_url="mysql+pymysql://admin:@127.0.0.1:3306/dolt",
            engine_factory=lambda *_a, **_k: engine,
        )
        return manager, engine

    def test_read_object_history_queries_dolt_history_table(self):
        rows = [
            {
                "rowKey": "R1",
                "startDate": "2026-07-01",
                "commit_hash": "abc",
                "committer": "Alice <a@x>",
                "commit_date": "2026-06-01",
                "commit_message": "edit",
            }
        ]
        manager, engine = self._manager(rows)
        out = manager.read_object_history(
            "shadow_a", "DeliveryPlanRow", {"rowKey": "R1"}, project_key="浙江移动", limit=50
        )
        self.assertEqual(out, rows)
        sql, params = engine.connection.calls[0]
        norm = " ".join(sql.split())
        self.assertIn("FROM `dolt_history_delivery_plan_row` AS h", norm)
        self.assertIn("LEFT JOIN dolt_log AS l ON l.commit_hash = h.commit_hash", norm)
        self.assertIn("h.`rowKey` = :pk_rowKey", norm)
        self.assertIn("h.`projectKey` = :pk___project_key", norm)
        self.assertIn("ORDER BY h.commit_date DESC", norm)
        self.assertIn("LIMIT :history_limit", norm)
        self.assertEqual(params["pk_rowKey"], "R1")
        self.assertEqual(params["pk___project_key"], "浙江移动")
        self.assertEqual(params["history_limit"], 50)

    def test_read_table_as_of_inlines_validated_ref(self):
        manager, engine = self._manager([{"rowKey": "R1"}])
        manager.read_table_as_of(
            "shadow_a", "DeliveryPlanRow", "2026-06-01T00:00:00Z", primary_key={"rowKey": "R1"}
        )
        sql, params = engine.connection.calls[0]
        norm = " ".join(sql.split())
        self.assertIn("FROM `delivery_plan_row` AS OF '2026-06-01T00:00:00Z'", norm)
        self.assertIn("`rowKey` = :pk_rowKey", norm)
        self.assertEqual(params["pk_rowKey"], "R1")

    def test_read_table_as_of_rejects_unsafe_ref(self):
        manager, _engine = self._manager([])
        with self.assertRaises(ValueError):
            manager.read_table_as_of("shadow_a", "DeliveryPlanRow", "abc'; DROP TABLE x; --")

    def test_read_object_diff_uses_commit_diff_table(self):
        manager, engine = self._manager([{"diff_type": "modified"}])
        manager.read_object_diff("shadow_a", "DeliveryPlanRow", "h1", "h2", {"rowKey": "R1"})
        sql, params = engine.connection.calls[0]
        norm = " ".join(sql.split())
        self.assertIn("FROM `dolt_commit_diff_delivery_plan_row`", norm)
        self.assertIn("from_commit = :from_ref", norm)
        self.assertIn("to_commit = :to_ref", norm)
        self.assertIn("COALESCE(`to_rowKey`, `from_rowKey`) = :pk_rowKey", norm)
        self.assertEqual(params["from_ref"], "h1")
        self.assertEqual(params["to_ref"], "h2")
        self.assertEqual(params["pk_rowKey"], "R1")

    def test_apply_object_update_records_author_on_commit(self):
        manager, engine = self._manager([])
        manager.apply_object_update(
            "shadow_a",
            "DeliveryPlanRow",
            {"rowKey": "R1"},
            {"startDate": "2026-07-01"},
            author="Alice <alice@ontology.local>",
            message="Apply EditPlanRow on DeliveryPlanRow R1 (startDate)",
        )
        commit_calls = [(sql, params) for sql, params in engine.connection.calls if "dolt_commit" in sql]
        self.assertTrue(commit_calls)
        sql, params = commit_calls[0]
        self.assertIn("--author", sql)
        self.assertEqual(params.get("author"), "Alice <alice@ontology.local>")
        self.assertEqual(params.get("message"), "Apply EditPlanRow on DeliveryPlanRow R1 (startDate)")

    def test_apply_object_update_without_author_keeps_plain_commit(self):
        manager, engine = self._manager([])
        manager.apply_object_update("shadow_a", "DeliveryPlanRow", {"rowKey": "R1"}, {"startDate": "2026-07-01"})
        commit_calls = [sql for sql, _ in engine.connection.calls if "dolt_commit" in sql]
        self.assertTrue(commit_calls)
        self.assertNotIn("--author", commit_calls[0])


class ObjectHistoryGatingTests(unittest.TestCase):
    """data_connector gates history reads to the Dolt path (CSV has no history)."""

    def test_history_requires_dolt_path_for_csv_object_on_main(self):
        import data_connector
        from preview_branch import PreviewBranchUnavailableError

        with patch.object(data_connector, "writeback_overlay_enabled", return_value=False):
            with self.assertRaises(PreviewBranchUnavailableError):
                data_connector.get_object_history("DeliveryPlanRow", {"rowKey": "R1"})

    def test_history_allows_backing_object_on_preview_branch(self):
        import data_connector
        from preview_branch import resolve_preview_branch_context, use_preview_branch

        captured = {}

        def fake_reader(context, object_type, primary_key, *, project_key=None, limit=None):
            captured["branch"] = context.dolt_branch
            captured["object_type"] = object_type
            return [{"rowKey": "R1"}]

        with use_preview_branch(resolve_preview_branch_context("shadow_sim_xyz")):
            with patch.object(data_connector, "get_object_history_for_branch", side_effect=fake_reader):
                out = data_connector.get_object_history("DeliveryPlanRow", {"rowKey": "R1"})

        self.assertEqual(out, [{"rowKey": "R1"}])
        self.assertEqual(captured["branch"], "shadow_sim_xyz")
        self.assertEqual(captured["object_type"], "DeliveryPlanRow")


if __name__ == "__main__":
    unittest.main()
