from __future__ import annotations

import csv
import importlib
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date
from os import environ
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schedule_ontology import (  # noqa: E402
    FIELD_EQUIPMENT_LIST,
    FIELD_LIMIT_DURATION,
    FIELD_ONSITE_TEAM,
    FIELD_ORIGINAL_MANAGEMENT_UNIT,
    FIELD_OWNER,
    FIELD_REMOTE_TEAM,
    FIELD_RISK_BELOW_STANDARD,
    FIELD_STANDARD_DURATION,
    LocalScheduleOntology,
)
from schedule_plan_activities import (  # noqa: E402
    FIELD_ACTIVITY_ID,
    FIELD_BATCH,
    FIELD_DEPENDENCY,
    FIELD_END,
    FIELD_NAME,
    FIELD_ROW_ID,
    FIELD_SLA,
    FIELD_START,
    FIELD_UNIT,
)


DAY = "\u5929"
PREPARE = "\u51c6\u5907"
INSTALL = "\u5b89\u88c5"
ROOM_IMPLEMENTATION = "\u673a\u623f\u6539\u9020\u5b9e\u65bd"
ARRIVAL = "\u5230\u8d27"
POWER_ON = "\u4e0a\u7535"
CLUSTER_DEBUG = "\u96c6\u7fa4\u6027\u80fd\u8c03\u4f18"
NETWORK_INSTALL = "\u7f51\u7edc\u8bbe\u5907\u5b89\u88c5"

PLAN_FIELDS = [
    FIELD_ROW_ID,
    FIELD_ACTIVITY_ID,
    FIELD_UNIT,
    FIELD_NAME,
    FIELD_START,
    FIELD_END,
    FIELD_SLA,
    FIELD_DEPENDENCY,
    FIELD_BATCH,
    FIELD_STANDARD_DURATION,
    FIELD_LIMIT_DURATION,
    FIELD_EQUIPMENT_LIST,
    FIELD_REMOTE_TEAM,
    FIELD_ONSITE_TEAM,
    FIELD_OWNER,
    FIELD_ORIGINAL_MANAGEMENT_UNIT,
    FIELD_RISK_BELOW_STANDARD,
]

MILESTONE_FIELDS = [
    "milestoneKey",
    "projectKey",
    "projectName",
    "scopeType",
    "scopeKey",
    "milestoneType",
    "milestoneName",
    "plannedDate",
    "actualDate",
    "anchorDate",
    "sourceFile",
    "description",
    "directionRole",
    "dependencyMilestoneTypes",
]


def _days(value: int) -> str:
    return f"{value}{DAY}"


def _plan_row(
    serial: str,
    activity_name: str,
    *,
    activity_id: str | None = None,
    management_unit: str = "POD-A",
    start_date: str = "",
    end_date: str = "",
    sla_days: int = 10,
    dependency: str = "",
    batch: str = "B1",
    standard_days: int | None = None,
    limit_days: int | None = None,
    equipment_list: str = "",
    remote_team: str = "",
    onsite_team: str = "",
    owner: str = "",
    original_management_unit: str = "",
    risk_below_standard: str = "",
) -> dict[str, str]:
    row = {field: "" for field in PLAN_FIELDS}
    row.update(
        {
            FIELD_ROW_ID: serial,
            FIELD_ACTIVITY_ID: activity_id or serial,
            FIELD_UNIT: management_unit,
            FIELD_NAME: activity_name,
            FIELD_START: start_date,
            FIELD_END: end_date,
            FIELD_SLA: _days(sla_days),
            FIELD_DEPENDENCY: dependency,
            FIELD_BATCH: batch,
            FIELD_STANDARD_DURATION: _days(standard_days if standard_days is not None else sla_days),
            FIELD_LIMIT_DURATION: _days(limit_days if limit_days is not None else max(1, sla_days // 2)),
            FIELD_EQUIPMENT_LIST: equipment_list,
            FIELD_REMOTE_TEAM: remote_team,
            FIELD_ONSITE_TEAM: onsite_team,
            FIELD_OWNER: owner,
            FIELD_ORIGINAL_MANAGEMENT_UNIT: original_management_unit,
            FIELD_RISK_BELOW_STANDARD: risk_below_standard,
        }
    )
    return row


def _milestone(
    milestone_key: str,
    project_key: str,
    milestone_type: str,
    milestone_name: str,
    anchor_date: str,
    direction_role: str,
) -> dict[str, str]:
    row = {field: "" for field in MILESTONE_FIELDS}
    row.update(
        {
            "milestoneKey": milestone_key,
            "projectKey": project_key,
            "projectName": project_key,
            "scopeType": "PROJECT",
            "scopeKey": "GLOBAL",
            "milestoneType": milestone_type,
            "milestoneName": milestone_name,
            "anchorDate": anchor_date,
            "sourceFile": "Milestone.csv",
            "directionRole": direction_role,
        }
    )
    return row


class BusinessSemanticsCoverageTests(unittest.TestCase):
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

    @staticmethod
    def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    @contextmanager
    def _temporary_sources(
        self,
        data_connector,
        sources: list[dict[str, object]],
        *,
        milestones: list[dict[str, str]] | None = None,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            project_sources = {}
            for source in sources:
                file_name = str(source["file_name"])
                self._write_csv(tmp_path / file_name, PLAN_FIELDS, list(source["rows"]))
                project_id = str(source["project_id"])
                project_sources[project_id] = data_connector.ProjectSource(
                    project_id,
                    file_name,
                    str(source["project_key"]),
                )
            self._write_csv(tmp_path / data_connector.MILESTONE_SOURCE_FILE, MILESTONE_FIELDS, milestones or [])
            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.BASE_DIR = tmp_path
                data_connector.PROJECT_SOURCES = project_sources
                yield tmp_path
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    @contextmanager
    def _copied_default_project(self, data_connector, project_id: str, source_file: str):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            shutil.copy2(BACKEND_DIR / source_file, tmp_path / source_file)
            shutil.copy2(BACKEND_DIR / data_connector.MILESTONE_SOURCE_FILE, tmp_path / data_connector.MILESTONE_SOURCE_FILE)
            original_sources = data_connector.PROJECT_SOURCES
            original_base_dir = data_connector.BASE_DIR
            try:
                source = data_connector.PROJECT_SOURCES[project_id]
                data_connector.BASE_DIR = tmp_path
                data_connector.PROJECT_SOURCES = {
                    project_id: data_connector.ProjectSource(project_id, source_file, source.project_key)
                }
                yield tmp_path
            finally:
                data_connector.PROJECT_SOURCES = original_sources
                data_connector.BASE_DIR = original_base_dir

    def test_plan_row_preserves_station_goods_people_and_batch_inputs(self):
        data_connector = importlib.import_module("data_connector")
        rows = [
            _plan_row(
                "row-1",
                NETWORK_INSTALL,
                management_unit="104-PoD1",
                batch="batch-2026A",
                equipment_list="CE6865E x2; OSN x1",
                remote_team="remote-team-A",
                onsite_team="onsite-team-B",
                owner="owner-001",
                original_management_unit="104-PoD1/raw",
                risk_below_standard="quality gate required",
            )
        ]

        with self._temporary_sources(
            data_connector,
            [{"project_id": "Demo", "project_key": "demo", "file_name": "demo.csv", "rows": rows}],
        ):
            plan_rows = data_connector.get_object_data("DeliveryPlanRow", project_id="Demo")

        self.assertEqual(len(plan_rows), 1)
        row = plan_rows[0]
        self.assertEqual(row["managementUnit"], "104-PoD1")
        self.assertEqual(row["equipmentList"], "CE6865E x2; OSN x1")
        self.assertEqual(row["remoteTeam"], "remote-team-A")
        self.assertEqual(row["onsiteTeam"], "onsite-team-B")
        self.assertEqual(row["owner"], "owner-001")
        self.assertEqual(row["batch"], "batch-2026A")
        self.assertEqual(row["originalManagementUnit"], "104-PoD1/raw")
        self.assertEqual(row["riskBelowStandard"], "quality gate required")

    def test_plan_row_dependencies_do_not_cross_project_when_activity_names_repeat(self):
        data_connector = importlib.import_module("data_connector")
        alpha_rows = [
            _plan_row("a1", PREPARE, management_unit="POD-1", sla_days=2),
            _plan_row("a2", INSTALL, management_unit="POD-1", sla_days=3, dependency=PREPARE),
        ]
        beta_rows = [
            _plan_row("b1", PREPARE, management_unit="POD-1", sla_days=8),
            _plan_row("b2", INSTALL, management_unit="POD-1", sla_days=9, dependency=PREPARE),
        ]

        with self._temporary_sources(
            data_connector,
            [
                {"project_id": "ProjectA", "project_key": "alpha", "file_name": "alpha.csv", "rows": alpha_rows},
                {"project_id": "ProjectB", "project_key": "beta", "file_name": "beta.csv", "rows": beta_rows},
            ],
        ):
            dependencies = data_connector.get_linked_object_data(
                "DeliveryPlanRow",
                f"alpha::{INSTALL}",
                "PlanRowDependencies",
                project_id="ProjectA",
            )

        self.assertEqual([row["rowKey"] for row in dependencies], [f"alpha::{PREPARE}"])
        self.assertTrue(all(row["projectKey"] == "alpha" for row in dependencies))
        self.assertNotIn(f"beta::{PREPARE}", {row["rowKey"] for row in dependencies})

    def test_effective_sla_overrides_only_use_adopted_estimates(self):
        data_connector = importlib.import_module("data_connector")
        estimate_rows = [
            {
                "estimateKey": "est-adopted",
                "rowKey": f"demo::{INSTALL}",
                "standardSlaDays": "3",
                "limitSlaDays": "1",
                "isAdopted": "true",
            },
            {
                "estimateKey": "est-draft",
                "rowKey": f"demo::{PREPARE}",
                "standardSlaDays": "9",
                "limitSlaDays": "8",
                "isAdopted": "false",
            },
            {
                "estimateKey": "est-empty-row",
                "rowKey": "",
                "standardSlaDays": "7",
                "limitSlaDays": "6",
                "isAdopted": "true",
            },
        ]

        with (
            patch.object(
                data_connector,
                "SUPPORTED_OBJECT_TYPES",
                set(data_connector.SUPPORTED_OBJECT_TYPES) | {data_connector.ACTIVITY_SLA_ESTIMATE_OBJECT_TYPE},
            ),
            patch.object(data_connector, "get_object_data", return_value=estimate_rows),
        ):
            standard, limit = data_connector._effective_sla_overrides_for_project("Demo")

        self.assertEqual(standard, {f"demo::{INSTALL}": "3"})
        self.assertEqual(limit, {f"demo::{INSTALL}": "1"})

    def test_delivery_plan_row_without_adopted_estimate_falls_back_to_raw_sla(self):
        data_connector = importlib.import_module("data_connector")
        rows = [
            _plan_row(
                "row-1",
                INSTALL,
                sla_days=10,
                standard_days=10,
                limit_days=5,
            )
        ]

        with self._temporary_sources(
            data_connector,
            [{"project_id": "Demo", "project_key": "demo", "file_name": "demo.csv", "rows": rows}],
        ):
            with patch.object(data_connector, "_effective_sla_overrides_for_project", return_value=({}, {})):
                plan_row = data_connector.get_object_data("DeliveryPlanRow", project_id="Demo")[0]

        self.assertEqual(plan_row["sla"], _days(10))
        self.assertEqual(plan_row["standardDuration"], _days(10))
        self.assertEqual(plan_row["limitDuration"], _days(5))

    def test_backward_schedule_uses_activity_network_and_effective_sla(self):
        data_connector = importlib.import_module("data_connector")
        rows = [
            _plan_row("row-1", ROOM_IMPLEMENTATION, sla_days=10),
            _plan_row("row-2", ARRIVAL, sla_days=10, dependency=ROOM_IMPLEMENTATION),
            _plan_row("row-3", POWER_ON, sla_days=10, dependency=ARRIVAL),
        ]
        milestones = [
            _milestone(
                "demo::PROJECT::GLOBAL::POWER_ON",
                "demo",
                "POWER_ON",
                POWER_ON,
                "2026-07-20",
                "BACKWARD_TARGET",
            )
        ]
        standard = {
            f"demo::{ROOM_IMPLEMENTATION}": 2,
            f"demo::{ARRIVAL}": 3,
            f"demo::{POWER_ON}": 4,
        }
        limit = {
            f"demo::{ROOM_IMPLEMENTATION}": 1,
            f"demo::{ARRIVAL}": 2,
            f"demo::{POWER_ON}": 2,
        }

        with self._temporary_sources(
            data_connector,
            [{"project_id": "Demo", "project_key": "demo", "file_name": "demo.csv", "rows": rows}],
            milestones=milestones,
        ):
            with patch.object(data_connector, "_effective_sla_overrides_for_project", return_value=(standard, limit)):
                result = data_connector.execute_backward_key_milestones(
                    "Demo",
                    selected_anchor_id="demo::PROJECT::GLOBAL::POWER_ON",
                )

        mutations = {(item["rowKey"], item["field"]): item["newDate"] for item in result["proposed_mutations"]}
        self.assertEqual(mutations[(f"demo::{POWER_ON}", "startDate")], "2026-07-17")
        self.assertEqual(mutations[(f"demo::{POWER_ON}", "endDate")], "2026-07-20")
        self.assertEqual(mutations[(f"demo::{ARRIVAL}", "startDate")], "2026-07-14")
        self.assertEqual(mutations[(f"demo::{ARRIVAL}", "endDate")], "2026-07-16")
        self.assertEqual(mutations[(f"demo::{ROOM_IMPLEMENTATION}", "startDate")], "2026-07-12")
        self.assertEqual(mutations[(f"demo::{ROOM_IMPLEMENTATION}", "endDate")], "2026-07-13")

    def test_forward_schedule_cascades_effective_sla_from_start_anchor(self):
        data_connector = importlib.import_module("data_connector")
        rows = [
            _plan_row("row-1", ROOM_IMPLEMENTATION, sla_days=10),
            _plan_row("row-2", ARRIVAL, sla_days=10, dependency=ROOM_IMPLEMENTATION),
            _plan_row("row-3", POWER_ON, sla_days=10, dependency=ARRIVAL),
        ]
        milestones = [
            _milestone(
                "demo::PROJECT::GLOBAL::ROOM_IMPLEMENTATION_DONE",
                "demo",
                "ROOM_IMPLEMENTATION_DONE",
                ROOM_IMPLEMENTATION,
                "2026-07-01",
                "FORWARD_START",
            )
        ]
        standard = {
            f"demo::{ROOM_IMPLEMENTATION}": 2,
            f"demo::{ARRIVAL}": 3,
            f"demo::{POWER_ON}": 4,
        }
        limit = {
            f"demo::{ROOM_IMPLEMENTATION}": 1,
            f"demo::{ARRIVAL}": 2,
            f"demo::{POWER_ON}": 2,
        }

        with self._temporary_sources(
            data_connector,
            [{"project_id": "Demo", "project_key": "demo", "file_name": "demo.csv", "rows": rows}],
            milestones=milestones,
        ):
            with patch.object(data_connector, "_effective_sla_overrides_for_project", return_value=(standard, limit)):
                result = data_connector.execute_forward_key_milestones("Demo")

        mutations = {(item["rowKey"], item["field"]): item["newDate"] for item in result["proposed_mutations"]}
        self.assertEqual(mutations[(f"demo::{ROOM_IMPLEMENTATION}", "startDate")], "2026-06-30")
        self.assertEqual(mutations[(f"demo::{ROOM_IMPLEMENTATION}", "endDate")], "2026-07-01")
        self.assertEqual(mutations[(f"demo::{ARRIVAL}", "startDate")], "2026-07-02")
        self.assertEqual(mutations[(f"demo::{ARRIVAL}", "endDate")], "2026-07-04")
        self.assertEqual(mutations[(f"demo::{POWER_ON}", "startDate")], "2026-07-05")
        self.assertEqual(mutations[(f"demo::{POWER_ON}", "endDate")], "2026-07-08")

    def test_plan_compression_decision_exposes_three_business_strategies(self):
        data_connector = importlib.import_module("data_connector")

        with self._copied_default_project(data_connector, "\u6d59\u6c5f\u79fb\u52a8", data_connector.ZJYD_SOURCE_FILE):
            with patch(
                "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
                return_value=None,
            ):
                result = data_connector.execute_plan_compression_decision(
                    "\u6d59\u6c5f\u79fb\u52a8",
                    power_on_target_date="2026-08-25",
                    cluster_debug_target_date="2026-09-20",
                )

        payload = result["llm_semantic_payload"]
        strategies = {item["strategy_id"]: item for item in payload["strategies"]}
        self.assertEqual(
            set(strategies),
            {"supply_frontload", "duration_top3_slack", "duration_global_proportional"},
        )
        for strategy in strategies.values():
            self.assertIsInstance(strategy["recommendation_summary"], str)
            self.assertIsInstance(strategy["quantitative_evidence"], list)
            self.assertIsInstance(strategy["actionable_mutations"], list)
            self.assertIsInstance(strategy["cascading_risks"], list)
            self.assertIn("toolName", strategy)
            self.assertIn("toolInput", strategy)
            self.assertEqual(strategy["toolStatus"], "COMPLETED")

    def test_supply_frontload_strategy_is_station_goods_pullup_not_duration_compression(self):
        data_connector = importlib.import_module("data_connector")

        with self._copied_default_project(data_connector, "\u6d59\u6c5f\u79fb\u52a8", data_connector.ZJYD_SOURCE_FILE):
            with patch(
                "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
                return_value=None,
            ):
                result = data_connector.execute_plan_compression_decision(
                    "\u6d59\u6c5f\u79fb\u52a8",
                    power_on_target_date="2026-08-10",
                    cluster_debug_target_date="2026-09-07",
                )

        supply_strategy = next(
            item
            for item in result["llm_semantic_payload"]["strategies"]
            if item["strategy_id"] == "supply_frontload"
        )
        override = supply_strategy["parameter_overrides"]
        supply_phase = next(
            scenario
            for scenario in result["phases"][0]["scenarios"]
            if scenario["scenarioId"] == "phase1_supply_shift"
        )

        self.assertEqual(supply_strategy["toolName"], "preview_plan_supply_shift")
        self.assertEqual(supply_phase["strategy"], "SUPPLY_ADVANCE_SHIFT")
        self.assertIn("suggestedTargetArrivalDate", override)
        self.assertIn("roomImplementationDoneDate", override)
        self.assertIn("effectiveArrivalAdvanceDays", override)
        self.assertGreater(override["suggestedArrivalAdvanceDays"], 0)
        self.assertEqual(supply_strategy["strategy_id"], "supply_frontload")
        self.assertNotIn(supply_strategy["strategy_id"], {"duration_top3_slack", "duration_global_proportional"})

    def test_buffer_extension_outputs_extension_scenario_not_compression(self):
        data_connector = importlib.import_module("data_connector")

        with self._copied_default_project(data_connector, "\u6d59\u6c5f\u79fb\u52a8", data_connector.ZJYD_SOURCE_FILE):
            with patch(
                "langgraph_agent.recommenders.plan_compression.try_llm_recommend_plan_compression",
                return_value=None,
            ):
                result = data_connector.execute_plan_compression_decision(
                    "\u6d59\u6c5f\u79fb\u52a8",
                    power_on_target_date="2026-08-25",
                    cluster_debug_target_date="2026-09-20",
                )

        phase1_extension = next(
            scenario
            for scenario in result["phases"][0]["scenarios"]
            if scenario["scenarioId"] == "phase1_duration_proportional_extension"
        )
        self.assertEqual(phase1_extension["strategy"], "PROPORTIONAL_EXTENSION")
        self.assertGreater(phase1_extension["requestedExtensionDays"], 0)
        self.assertNotIn("requestedCompressionDays", phase1_extension)

    def test_unachievable_reason_and_below_standard_risk_are_separate_outputs(self):
        from llm_openrouter_milestone_compression import compute_duration_compression_schedule

        warnings: list[str] = []
        ontology = LocalScheduleOntology.from_rows(
            [
                _plan_row(
                    "row-1",
                    PREPARE,
                    start_date="2026-07-01",
                    end_date="2026-07-05",
                    sla_days=5,
                    limit_days=5,
                ),
                _plan_row(
                    "row-2",
                    INSTALL,
                    start_date="2026-07-06",
                    end_date="2026-07-10",
                    sla_days=5,
                    dependency=PREPARE,
                    limit_days=5,
                    risk_below_standard="needs approval when below standard",
                ),
            ],
            project_key="demo",
        )

        impossible = compute_duration_compression_schedule(
            ontology.activities,
            target_keys=[INSTALL],
            baseline_date=date(2026, 7, 10),
            anchor_date=date(2026, 7, 5),
            limit_duration_by_key={PREPARE: 5, INSTALL: 5},
            warnings=warnings,
        )

        self.assertLess(impossible.achieved_compression_days, impossible.requested_compression_days)
        self.assertTrue(any("\u65e0\u6cd5\u5b8c\u5168\u538b\u7f29" in item for item in warnings))

        risk_warnings: list[str] = []
        reachable = compute_duration_compression_schedule(
            ontology.activities,
            target_keys=[INSTALL],
            baseline_date=date(2026, 7, 10),
            anchor_date=date(2026, 7, 9),
            limit_duration_by_key={PREPARE: 4, INSTALL: 4},
            warnings=risk_warnings,
        )

        self.assertEqual(reachable.achieved_compression_days, reachable.requested_compression_days)
        self.assertEqual(reachable.stop_reason, "TARGET_REACHED")
        self.assertIn("needs approval when below standard", ontology.row(f"demo::{INSTALL}").to_schema_object()["riskBelowStandard"])


if __name__ == "__main__":
    unittest.main()
