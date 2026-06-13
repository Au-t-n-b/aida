"""End-to-end validation for the Foundry-style Dolt-native writeback overlay.

These tests exercise the real merge semantics (ingest branch + dolt_merge --ours),
which cannot be faked, so they require a running Dolt SQL server. They are skipped
unless both env vars are set:

    DOLT_DATABASE_URL=mysql+pymysql://user:@host:3306/<db>
    RUN_DOLT_INTEGRATION=1

Run (PowerShell):
    $env:DOLT_DATABASE_URL="mysql+pymysql://root:@127.0.0.1:3306/delivery"
    $env:RUN_DOLT_INTEGRATION="1"
    python backend\tests\test_writeback_overlay_integration.py -v
"""

import os
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_DOLT_AVAILABLE = bool(os.getenv("DOLT_DATABASE_URL")) and os.getenv("RUN_DOLT_INTEGRATION") == "1"


@unittest.skipUnless(_DOLT_AVAILABLE, "requires a running Dolt server (set DOLT_DATABASE_URL + RUN_DOLT_INTEGRATION=1)")
class WritebackOverlayIntegrationTests(unittest.TestCase):
    PROJECT_ID = "浙江移动"

    def setUp(self):
        os.environ["DOLT_WRITEBACK_OVERLAY"] = "1"

    def test_user_edit_survives_pipeline_reingest(self):
        import backend_app
        import data_connector
        import dolt_mirror

        # 1. Baseline: pipeline ingest materializes CSV onto main via the ingest branch.
        dolt_mirror.sync_main_mirror(object_types=["DeliveryPlanRow"])
        rows = data_connector.get_object_data("DeliveryPlanRow", project_id=self.PROJECT_ID)
        self.assertTrue(rows, "expected DeliveryPlanRow rows after baseline ingest")
        target = rows[0]
        row_key = str(target["rowKey"])
        edited_date = "2099-01-01"
        self.assertNotEqual(str(target.get("startDate")), edited_date)

        # 2. User Action edit on main (writeback layer).
        backend_app.apply_update_milestone_date_batch(
            {
                "batch": [
                    {
                        "rowKey": row_key,
                        "dateField": "startDate",
                        "newDate": edited_date,
                        "project_id": self.PROJECT_ID,
                    }
                ]
            }
        )
        after_edit = {
            str(r["rowKey"]): r for r in data_connector.get_object_data("DeliveryPlanRow", project_id=self.PROJECT_ID)
        }
        self.assertEqual(str(after_edit[row_key]["startDate"]), edited_date, "edit should be visible on main")

        # 3. Pipeline re-runs (re-ingest). With --ours, the user edit must survive.
        dolt_mirror.sync_main_mirror(object_types=["DeliveryPlanRow"])
        after_reingest = {
            str(r["rowKey"]): r for r in data_connector.get_object_data("DeliveryPlanRow", project_id=self.PROJECT_ID)
        }
        self.assertEqual(
            str(after_reingest[row_key]["startDate"]),
            edited_date,
            "pipeline re-ingest must NOT clobber the user edit (dolt_conflicts_resolve --ours)",
        )

    def test_pipeline_validate_targets_ingest_branch(self):
        import dolt_mirror

        dolt_mirror.sync_main_mirror(object_types=["DeliveryProject"])
        summary = dolt_mirror.validate_main_mirror(object_types=["DeliveryProject"])
        # The ingest branch holds pure pipeline truth, so it must match CSV exactly.
        self.assertEqual(summary["status"], "ok", summary)


if __name__ == "__main__":
    unittest.main()
