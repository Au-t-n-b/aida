from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class EodsPresalesRiskTests(unittest.TestCase):
    def test_eods_node_helpers_format_filter_flatten_and_parse(self):
        eods = importlib.import_module("eods_presales_risk")

        table = eods.format_cell_table(
            {
                "headers": [{"name": "riskRuleId"}, {"name": "riskPoint"}],
                "cell_values": [["RR-1", "EOS风险"], ["RR-2", "ESS风险"]],
            }
        )
        self.assertEqual(
            table,
            [
                {"riskRuleId": "RR-1", "riskPoint": "EOS风险"},
                {"riskRuleId": "RR-2", "riskPoint": "ESS风险"},
            ],
        )

        voted = eods.filter_repeated_risks(
            [
                [{"rule_id": "RR-A", "risk_point": "A"}, {"rule_id": "RR-B", "risk_point": "B"}],
                [{"rule_id": "RR-A", "risk_point": "A"}],
                [{"rule_id": "RR-A", "risk_point": "A"}],
            ]
        )
        self.assertEqual(voted, [{"rule_id": "RR-A", "risk_point": "A"}])

        self.assertEqual(eods.flatten_risk_arrays([[{"a": 1}], [], [{"b": 2}]]), [{"a": 1}, {"b": 2}])

        parsed = eods.parse_llm_risk_output(
            'prefix</think>[{"risk_sub_type":"SVC","risk_point":"服务漏配","countermeasure":"补齐服务"}]',
            opportunity_code="OPP-1",
            bidding_code="BID-1",
            create_time="2026-06-12 10:00:00",
        )
        self.assertEqual(parsed[0]["risk_code"], "OPP-1_SVC_服务漏配")
        self.assertEqual(parsed[0]["risk_generation_mode"], "AI工作流")
        self.assertEqual(parsed[0]["risk_response_measure"], "补齐服务")
        self.assertNotIn("risk_sub_type", parsed[0])

    def test_derive_eods_presales_risks_for_plan_reads_through_ontology_sdk(self):
        dc = importlib.import_module("data_connector")
        ref = "2026-06-12"
        fake_rows = {
            "RiskRule": [
                {
                    "riskRuleId": "RR-EOS-01",
                    "riskPoint": "EOS风险",
                    "ruleName": "产品EOS早于交付窗口",
                    "riskCategory": "生命周期风险",
                    "riskSubCategory": "EOS",
                    "riskLevel": "高",
                    "owner": "交付PM",
                    "responseMeasure": "更换在维产品",
                    "impact": "SLA无法保障",
                }
            ],
            "MaintenancePolicy": [],
            "EquipmentConfig": [
                {
                    "equipmentId": "EQ-JD-1",
                    "projectKey": "京东",
                    "equipmentName": "Atlas 900 A3",
                    "eosDate": "2026-01-01",
                },
                {
                    "equipmentId": "EQ-ZJ-1",
                    "projectKey": "浙江移动",
                    "equipmentName": "CE6865",
                    "eosDate": "2026-01-01",
                },
            ],
            "ComponentConfig": [],
        }

        calls: list[tuple[str, str | None]] = []

        def fake_get_object_data(object_type, project_id=None):
            calls.append((object_type, project_id))
            return fake_rows.get(object_type, [])

        with patch.object(dc, "get_object_data", side_effect=fake_get_object_data), patch.object(
            dc, "contingency_object_data", return_value=[]
        ):
            result = dc.derive_eods_presales_risks_for_plan(
                plan_id="PLAN-JD",
                project_key="京东",
                reference_date=ref,
                apply_outline=False,
            )

        self.assertEqual(result["engine"], "eods_presales_risk")
        self.assertEqual(result["projectKey"], "京东")
        self.assertEqual(result["riskCount"], 1)
        risk = result["risks"][0]
        self.assertEqual(risk["riskPoint"], "EOS风险")
        self.assertEqual(risk["subjects"], ["Atlas 900 A3"])
        self.assertEqual(risk["provenance"]["engine"], "deriveContingencyRisks")
        self.assertIn(("RiskRule", None), calls)
        self.assertIn(("EquipmentConfig", None), calls)

    def test_derive_eods_presales_risks_is_registered_as_ontology_function(self):
        backend_app = importlib.import_module("backend_app")
        function_types = backend_app.load_function_types()
        self.assertIn("deriveEodsPresalesRisks", function_types)
        binding = function_types["deriveEodsPresalesRisks"]["binding"]
        self.assertEqual(binding, {"module": "data_connector", "function": "derive_eods_presales_risks_for_plan"})


if __name__ == "__main__":
    unittest.main()
