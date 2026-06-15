"""Unit tests for the contingency run-record Action loop (create + modify halves).

Covers the 预案必备 action set end-to-end at the engine level:

    CreateContingencyPlan (DRAFT)
        -> CreateDeliverabilityAssessment (follow-on lifecycle edit: plan DRAFT -> ASSESSING)
        -> RecordContingencyDecision -> AdoptDerivedRisk / DismissDerivedRisk
        -> UpdateRiskStatus -> CreateGapItem
        -> GenerateRemediationTask (with gapId: gap OPEN -> IN_PROGRESS)
        -> ModifyInfrastructureConfig -> CompleteRemediationTask -> CloseGapItem
        -> ApproveContingencyPlan (DRAFT/ASSESSING -> APPROVED, terminal)

These run fully offline: Dolt reads degrade to [] and the run-record overlay is redirected
into a temp dir, so no external substrate is required (unlike the Dolt integration tests).

Run (PowerShell, repo root):
    ontology\.venv\Scripts\python.exe ontology\tests\test_contingency_action_loop.py -v
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import backend_app
import data_connector

PLAN_ID = "PLAN-T1"
PROJECT_KEY = "PJ-T"
ASSESSMENT_ID = "ASSESS-T1"


class ContingencyActionLoopTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tmp_root = Path(tmp.name)
        patcher = mock.patch.object(
            data_connector,
            "_contingency_runrecord_path",
            new=lambda object_type: tmp_root / f"{object_type}.json",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _apply(action: str, payload: dict):
        return backend_app.apply_action_type(action, payload)

    @staticmethod
    def _validate(action: str, payload: dict):
        return backend_app.validate_action_type(action, payload)

    @staticmethod
    def _rows(object_type: str):
        return data_connector.get_object_data(object_type)

    def _create_plan(self, plan_id: str = PLAN_ID):
        return self._apply(
            "CreateContingencyPlan",
            {
                "planId": plan_id,
                "projectKey": PROJECT_KEY,
                "planName": "京东A3三期交付预案",
                "planVersion": "V1.0",
                "updatedBy": "tester",
                "sourceSummary": "deriveContingencyRisks 派生批次固化（单测）",
            },
        )

    def test_create_plan_then_approve_walks_the_status_state_machine(self):
        created = self._create_plan()
        self.assertTrue(created["success"])
        self.assertEqual(created["data"]["status"], "DRAFT")

        approved = self._apply(
            "ApproveContingencyPlan",
            {"targetPlan": PLAN_ID, "approvedBy": "王总", "approvalComment": "评审通过"},
        )
        self.assertEqual(approved["data"]["status"], "APPROVED")
        self.assertEqual(approved["data"]["approvedBy"], "王总")

        rows = {str(r.get("planId")): r for r in self._rows("ContingencyPlan")}
        self.assertEqual(rows[PLAN_ID]["status"], "APPROVED")

    def test_approve_unknown_plan_is_a_key_error(self):
        with self.assertRaises(KeyError):
            self._apply("ApproveContingencyPlan", {"targetPlan": "NO-SUCH-PLAN", "approvedBy": "王总"})

    def test_record_decision_defaults_pk_and_validates_conclusion(self):
        recorded = self._apply(
            "RecordContingencyDecision",
            {
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "decisionId": "DP-CORE",
                "decisionName": "方案可交付性",
                "decisionLevel": "core",
                "derivedConclusion": "存在风险",
                "conclusion": "存在风险",
                "deliverabilityIndex": 64,
                "decidedBy": "李架构",
                "decisionComment": "EOS 超期风险未消除，维持派生结论。",
            },
        )
        self.assertEqual(recorded["decisionRecordId"], f"{PLAN_ID}_DP-CORE")
        self.assertEqual(recorded["data"]["status"], "CONFIRMED")

        rows = self._rows("DecisionRecord")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["conclusion"], "存在风险")

        with self.assertRaises(ValueError):
            self._apply(
                "RecordContingencyDecision",
                {
                    "planId": PLAN_ID,
                    "projectKey": PROJECT_KEY,
                    "decisionId": "DP-DEVICE",
                    "conclusion": "大概率没问题",
                    "decidedBy": "李架构",
                },
            )

    def test_adopt_then_update_risk_status_reaches_the_overlay_row(self):
        self._apply(
            "AdoptDerivedRisk",
            {
                "riskId": "RISK-T1",
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "assessmentId": ASSESSMENT_ID,
                "riskName": "EOS超期风险",
                "riskPoint": "EOS风险",
                "severity": "高",
                "state": "处理中",
            },
        )
        updated = self._apply(
            "UpdateRiskStatus",
            {"targetRisk": "RISK-T1", "status": "已关闭", "owner": "李工", "mitigationPlan": "升级维保合同"},
        )
        self.assertEqual(updated["data"]["status"], "已关闭")
        self.assertEqual(updated["data"]["owner"], "李工")
        # The adopted row's untouched fields survive the modify merge.
        self.assertEqual(updated["data"]["riskName"], "EOS超期风险")

        with self.assertRaises(KeyError):
            self._apply("UpdateRiskStatus", {"targetRisk": "NO-SUCH-RISK", "status": "已关闭"})

    def test_dismiss_derived_risk_leaves_an_auditable_trace(self):
        dismissed = self._apply(
            "DismissDerivedRisk",
            {
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "assessmentId": ASSESSMENT_ID,
                "riskName": "ESS服务窗口风险",
                "riskPoint": "ESS风险",
                "dismissReason": "服务窗口已随合同补签延长，建议失效。",
                "dismissedBy": "张交付",
            },
        )
        self.assertEqual(dismissed["riskId"], f"{PLAN_ID}_ESS风险")
        self.assertEqual(dismissed["data"]["state"], "已驳回")
        self.assertEqual(dismissed["data"]["source"], "售前风险（驳回派生建议）")

        rows = {str(r.get("riskId")): r for r in self._rows("RiskItem")}
        self.assertEqual(rows[f"{PLAN_ID}_ESS风险"]["sourceSummary"], "服务窗口已随合同补签延长，建议失效。")

    def test_task_lifecycle_generate_progress_complete_and_terminal_guard(self):
        generated = self._apply(
            "GenerateRemediationTask",
            {
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "assessmentId": ASSESSMENT_ID,
                "title": "更换 EOM 设备型号",
                "owner": "张工",
            },
        )
        task_id = generated["taskId"]
        self.assertEqual(generated["data"]["status"], "OPEN")

        progressed = self._apply(
            "ModifyInfrastructureConfig",
            {
                "targetTask": task_id,
                "targetObjectType": "EquipmentConfig",
                "targetObjectId": "EQ-001",
                "changeSummary": "替换为在售型号",
            },
        )
        self.assertEqual(progressed["data"]["status"], "IN_PROGRESS")

        completed = self._apply(
            "CompleteRemediationTask",
            {"targetTask": task_id, "completionNote": "替换完成并复测通过", "completedBy": "张工"},
        )
        self.assertEqual(completed["data"]["status"], "DONE")
        self.assertEqual(completed["data"]["completionNote"], "替换完成并复测通过")

        # DONE is terminal for the infrastructure-adjustment state machine.
        with self.assertRaises(ValueError):
            self._apply(
                "ModifyInfrastructureConfig",
                {
                    "targetTask": task_id,
                    "targetObjectType": "EquipmentConfig",
                    "targetObjectId": "EQ-001",
                    "changeSummary": "二次调整",
                },
            )

    def test_gap_create_then_close(self):
        created = self._apply(
            "CreateGapItem",
            {
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "assessmentId": ASSESSMENT_ID,
                "title": "验收到货里程碑缺失",
                "description": "AcceptanceStrategy 缺到货验收节点。",
                "severity": "高",
            },
        )
        gap_id = created["gapId"]
        self.assertEqual(created["data"]["status"], "OPEN")

        closed = self._apply(
            "CloseGapItem",
            {"targetGap": gap_id, "closureReason": "已补录里程碑", "closedBy": "陈工"},
        )
        self.assertEqual(closed["data"]["status"], "CLOSED")
        self.assertEqual(closed["data"]["closureReason"], "已补录里程碑")

    def test_assessment_create_anchors_assessment_id(self):
        self._create_plan()
        created = self._apply(
            "CreateDeliverabilityAssessment",
            {
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "decisionId": "DP-DEVICE",
                "assessmentName": "设备配置可交付性评估",
                "conclusion": "存在差异",
                "deliverabilityIndex": 70,
            },
        )
        self.assertEqual(created["assessmentId"], f"{PLAN_ID}_DP-DEVICE")
        self.assertEqual(created["data"]["status"], "ASSESSED")
        # The follow-on lifecycle edit advances the owning plan DRAFT -> ASSESSING.
        self.assertEqual(created["lifecycleEdits"][0]["data"]["status"], "ASSESSING")
        rows = {str(r.get("planId")): r for r in self._rows("ContingencyPlan")}
        self.assertEqual(rows[PLAN_ID]["status"], "ASSESSING")

    def test_assessment_without_plan_is_rejected(self):
        # The lifecycle edit makes the plan anchor real: no plan row, no assessment.
        with self.assertRaises(KeyError):
            self._apply(
                "CreateDeliverabilityAssessment",
                {
                    "planId": "NO-SUCH-PLAN",
                    "projectKey": PROJECT_KEY,
                    "decisionId": "DP-CORE",
                    "assessmentName": "悬空评估",
                },
            )

    def test_plan_walks_draft_assessing_approved_and_approved_is_terminal(self):
        self._create_plan()
        self._apply(
            "CreateDeliverabilityAssessment",
            {
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "decisionId": "DP-CORE",
                "assessmentName": "方案可交付性评估",
            },
        )
        approved = self._apply(
            "ApproveContingencyPlan", {"targetPlan": PLAN_ID, "approvedBy": "王总"}
        )
        self.assertEqual(approved["data"]["status"], "APPROVED")

        # APPROVED is terminal: a new round must re-materialize the plan first.
        with self.assertRaises(ValueError):
            self._apply(
                "CreateDeliverabilityAssessment",
                {
                    "planId": PLAN_ID,
                    "projectKey": PROJECT_KEY,
                    "decisionId": "DP-NETWORK",
                    "assessmentName": "组网配置可交付性评估",
                },
            )

    def test_gap_dispatch_moves_gap_to_in_progress(self):
        created = self._apply(
            "CreateGapItem",
            {
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "assessmentId": ASSESSMENT_ID,
                "title": "验收到货里程碑缺失",
                "description": "AcceptanceStrategy 缺到货验收节点。",
                "severity": "高",
            },
        )
        gap_id = created["gapId"]

        dispatched = self._apply(
            "GenerateRemediationTask",
            {
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "assessmentId": ASSESSMENT_ID,
                "gapId": gap_id,
                "title": "补录到货验收里程碑",
                "owner": "陈工",
            },
        )
        self.assertEqual(dispatched["data"]["status"], "OPEN")
        self.assertEqual(dispatched["lifecycleEdits"][0]["data"]["status"], "IN_PROGRESS")
        gaps = {str(r.get("gapId")): r for r in self._rows("GapItem")}
        self.assertEqual(gaps[gap_id]["status"], "IN_PROGRESS")

        # Re-dispatching against the same gap is a no-op transition (IN_PROGRESS -> IN_PROGRESS).
        self._apply(
            "GenerateRemediationTask",
            {
                "planId": PLAN_ID,
                "projectKey": PROJECT_KEY,
                "assessmentId": ASSESSMENT_ID,
                "gapId": gap_id,
                "title": "二次派发",
                "owner": "陈工",
            },
        )

        # The declared GapStatus machine still allows IN_PROGRESS -> CLOSED.
        closed = self._apply(
            "CloseGapItem", {"targetGap": gap_id, "closureReason": "已补录", "closedBy": "陈工"}
        )
        self.assertEqual(closed["data"]["status"], "CLOSED")

        # CLOSED gaps reject new dispatches; dangling gapId is rejected outright.
        with self.assertRaises(ValueError):
            self._apply(
                "GenerateRemediationTask",
                {
                    "planId": PLAN_ID,
                    "projectKey": PROJECT_KEY,
                    "assessmentId": ASSESSMENT_ID,
                    "gapId": gap_id,
                    "title": "对已关闭差异派发",
                    "owner": "陈工",
                },
            )
        with self.assertRaises(KeyError):
            self._apply(
                "GenerateRemediationTask",
                {
                    "planId": PLAN_ID,
                    "projectKey": PROJECT_KEY,
                    "assessmentId": ASSESSMENT_ID,
                    "gapId": "NO-SUCH-GAP",
                    "title": "悬空派发",
                    "owner": "陈工",
                },
            )

    def test_record_decision_validates_decision_level_vocabulary(self):
        # DecisionLevel is lowercase core/sub, aligned with the derive engine vocabulary.
        with self.assertRaises(ValueError):
            self._apply(
                "RecordContingencyDecision",
                {
                    "planId": PLAN_ID,
                    "projectKey": PROJECT_KEY,
                    "decisionId": "DP-CORE",
                    "decisionLevel": "CORE",
                    "conclusion": "可交付",
                    "decidedBy": "李架构",
                },
            )

    def test_validate_does_not_persist(self):
        validated = self._validate(
            "CreateContingencyPlan",
            {"planId": "PLAN-V1", "projectKey": PROJECT_KEY, "planName": "干跑预案"},
        )
        self.assertTrue(validated["success"])
        self.assertNotIn("PLAN-V1", {str(r.get("planId")) for r in self._rows("ContingencyPlan")})

        self._create_plan("PLAN-V2")
        dry_run = self._validate(
            "ApproveContingencyPlan", {"targetPlan": "PLAN-V2", "approvedBy": "王总"}
        )
        self.assertEqual(dry_run["validatedChanges"]["status"], "APPROVED")
        rows = {str(r.get("planId")): r for r in self._rows("ContingencyPlan")}
        self.assertEqual(rows["PLAN-V2"]["status"], "DRAFT")


if __name__ == "__main__":
    unittest.main()
