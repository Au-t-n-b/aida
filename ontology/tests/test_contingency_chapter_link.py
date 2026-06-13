"""Offline tests for ContingencyChapter ObjectType + Decision_Chapters / Chapter_Narrative Links
and the chapter-narrative milestone snapshot/diff (plan A + B).

Hermetic: no Dolt, no LLM. Run from this directory:
    cd ontology/tests
    ../.venv/Scripts/python -m unittest -v test_contingency_chapter_link
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ONTOLOGY_DIR = Path(__file__).resolve().parents[1]
if str(_ONTOLOGY_DIR) not in sys.path:
    sys.path.insert(0, str(_ONTOLOGY_DIR))

import data_connector as dc  # noqa: E402
from contingency_narrative import store as narr_store  # noqa: E402

_SCHEMA = _ONTOLOGY_DIR / "schema"


def _object_types() -> dict:
    return json.loads((_SCHEMA / "object-types.json").read_text(encoding="utf-8"))


def _link_types() -> dict:
    return json.loads((_SCHEMA / "link-types.json").read_text(encoding="utf-8"))


class ContingencyChapterObjectTypeTests(unittest.TestCase):
    """A — chapter skeleton is a first-class ObjectType bound to DecisionPoint via a real Link."""

    def test_chapter_is_objecttype_and_registered(self):
        ot = _object_types()
        self.assertIn("ContingencyChapter", ot)
        self.assertEqual(ot["ContingencyChapter"]["primaryKeyPropertyApiNames"], ["id"])
        self.assertIn("ContingencyChapter", dc.SUPPORTED_OBJECT_TYPES)

    def test_chapters_load_via_objecttype_path_with_schema_derived_fields(self):
        # The placement table now holds only the 计划 chapter (doc-ch-12, bound to DeliveryPlanRow via
        # objectType/fieldOrder in the JSON); every other ObjectType-bound chapter lives in the ontology
        # as a contingencyChapter marker (decisionId / lane / layout / fieldOrder ride along on the marker).
        rows = dc.get_object_data("ContingencyChapter")
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(all("decisionId" in r for r in rows))
        self.assertIn("doc-ch-12", [r["id"] for r in rows])
        markers = {m["id"]: m for m in dc._contingency_chapter_markers()}
        self.assertGreaterEqual(len(markers), 11)
        device = markers["doc-device"]
        self.assertEqual(device["decisionId"], "DP-SUB-DEVICE")
        self.assertEqual(device["objectType"], "EquipmentConfig")  # auto-injected from the host type
        self.assertTrue(device.get("fieldOrder"))
        directory = dc._load_contingency_chapter_directory()
        device_dir = next(c for c in directory if c["id"] == "doc-device")
        derived = device_dir.get("fields") or []
        self.assertTrue(derived)
        self.assertTrue(all(f.get("key") for f in derived))  # keys are schema property apiNames
        self.assertIn("model", [f["key"] for f in derived])  # label/note sourced from the ontology

    def test_decision_chapters_link_declared_with_fk(self):
        link = _link_types()["Decision_Chapters"]
        self.assertEqual(link["linkedObjectTypeApiName"], "ContingencyChapter")
        self.assertEqual(link["foreignKey"]["sourcePropertyApiName"], "decisionId")
        self.assertEqual(link["foreignKey"]["targetPropertyApiName"], "decisionId")

    def test_decision_binding_uses_fk_not_domain_string_match(self):
        # device chapters bind to DP-SUB-DEVICE via the decisionId FK even though the
        # decision's domain ("EQUIPMENT") differs from the chapter's decisionPoint ("device") —
        # the exact case the old chapter.decisionPoint==domain string match got wrong.
        # decisionIds mirror the live Dolt decision_point PKs (DP-CORE / DP-SUB-*).
        defs = [
            {"decisionId": "DP-CORE", "decisionLevel": "core", "domain": ""},
            {"decisionId": "DP-SUB-DEVICE", "decisionLevel": "sub", "domain": "EQUIPMENT"},
            {"decisionId": "DP-SUB-NETWORK", "decisionLevel": "sub", "domain": "network"},
        ]
        orig = dc._load_contingency_decision_points
        dc._load_contingency_decision_points = lambda: defs
        try:
            chapters = dc._load_contingency_chapter_directory()
            for chapter in chapters:
                chapter.setdefault("riskIds", [])
            points = dc._build_contingency_decision_points(chapters, [])
        finally:
            dc._load_contingency_decision_points = orig
        equip = next(p for p in points if p["decisionId"] == "DP-SUB-DEVICE")
        self.assertEqual(set(equip["chapterIds"]), {"doc-device", "doc-service", "doc-ch-6"})
        core = next(p for p in points if p["decisionId"] == "DP-CORE")
        self.assertEqual(core["chapterIds"], [])  # global chapters bind to no sub-decision


class ChapterNarrativeVersionTests(unittest.TestCase):
    """B — narrative is a versioned ObjectType; milestones snapshot to Dolt; versions are diffable."""

    def test_narrative_objecttype_and_link_declared(self):
        ot = _object_types()
        link = _link_types()["Chapter_Narrative"]
        self.assertIn("ChapterNarrative", ot)
        self.assertEqual(ot["ChapterNarrative"]["primaryKeyPropertyApiNames"], ["chapterNarrativeId"])
        self.assertIn("ChapterNarrative", dc.SUPPORTED_OBJECT_TYPES)
        self.assertEqual(link["foreignKey"]["sourcePropertyApiName"], "chapterId")
        self.assertEqual(link["foreignKey"]["targetPropertyApiName"], "id")

    def test_snapshot_degrades_when_dolt_offline(self):
        # Force the offline branch deterministically (other suites may leave a live/mock Dolt engine).
        import dolt_schema_sync

        orig = dolt_schema_sync._get_dolt_engine
        dolt_schema_sync._get_dolt_engine = lambda: None
        try:
            res = narr_store._snapshot_narratives_to_dolt(
                "京东", "v1", [{"chapterId": "doc-device", "generatedText": "x"}]
            )
        finally:
            dolt_schema_sync._get_dolt_engine = orig
        self.assertEqual(res.get("written"), 0)
        self.assertIn("skipped", res)

    def test_diff_versions_pairs_by_chapter(self):
        rows = [
            {"projectKey": "京东", "chapterId": "doc-device", "versionLabel": "v1", "text": "旧", "chapterTitle": "设备"},
            {"projectKey": "京东", "chapterId": "doc-device", "versionLabel": "v2", "text": "新", "chapterTitle": "设备"},
            {"projectKey": "京东", "chapterId": "doc-acceptance", "versionLabel": "v2", "text": "新增", "chapterTitle": "验收"},
        ]
        orig = dc.get_object_data
        dc.get_object_data = lambda ot, *a, **k: rows if ot == "ChapterNarrative" else []
        try:
            out = narr_store.diff_chapter_narrative_versions("京东", "v1", "v2")
        finally:
            dc.get_object_data = orig
        self.assertEqual(out["changedCount"], 2)
        by_chapter = {d["chapterId"]: d for d in out["diffs"]}
        self.assertEqual(by_chapter["doc-device"]["change"], "modified")
        self.assertEqual(by_chapter["doc-device"]["fromText"], "旧")
        self.assertEqual(by_chapter["doc-device"]["toText"], "新")
        self.assertEqual(by_chapter["doc-acceptance"]["change"], "added")


if __name__ == "__main__":
    unittest.main()
