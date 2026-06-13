"""Offline tests for the contingency chapter-assembly feature (本体派生骨架 + LangGraph 裁剪).

Hermetic: the LLM is a stub (no network), the run-record overlay is redirected to a temp dir, and the
underlying deriveContingencyRisks is stubbed with a canned chapter set, so the full tailoring loop runs
without Dolt or a live model. The ontology-derived directory tests read the real schema files (no Dolt).
Run from this directory:

    cd ontology/tests
    ../.venv/Scripts/python -m unittest -v test_contingency_assembly
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_ONTOLOGY_DIR = Path(__file__).resolve().parents[1]
if str(_ONTOLOGY_DIR) not in sys.path:
    sys.path.insert(0, str(_ONTOLOGY_DIR))

import data_connector as dc  # noqa: E402
from contingency_assembly import llm as asm_llm  # noqa: E402
from contingency_assembly import store as asm_store  # noqa: E402

# The fake LLM keeps a real chapter (doc-device), drops an empty one (doc-service), and emits a
# hallucinated id (doc-FAKE) + a note for it — the select node must validate it all away.
_SELECT_OUT = {
    "include": ["doc-device", "doc-FAKE"],
    "order": ["doc-device"],
    "notes": {"doc-device": "本项目设备清单已就绪。", "doc-FAKE": "应被丢弃"},
    "rationale": "保留有事实的章节，裁掉本项目为空的章节。",
}

# Canned deriveContingencyRisks output: meta + risks are mandatory (no objectType / consolidates),
# doc-device is mandatory (has rows + risk), doc-service is droppable (objectType but empty).
_CANNED_DERIVED = {
    "planId": "P",
    "projectKey": "京东",
    "assessmentId": "A",
    "riskCount": 1,
    "risks": [{"riskId": "R1"}],
    "chapters": [
        {"id": "doc-ch-meta", "no": "元数据", "title": "元数据信息"},
        {
            "id": "doc-device",
            "no": "2",
            "title": "设备配置信息",
            "objectType": "EquipmentConfig",
            "decisionLabel": "设备配置的可交付性",
            "rows": [{"型号": "X"}],
            "riskIds": ["R1"],
        },
        {
            "id": "doc-service",
            "no": "3",
            "title": "部件配置信息",
            "objectType": "ComponentConfig",
            "decisionLabel": "设备配置的可交付性",
            "rows": [],
            "riskIds": [],
        },
        {"id": "doc-risks", "no": "13", "title": "风险&假设信息", "consolidatesRisks": True, "riskIds": ["R1"]},
    ],
    "decisionPoints": [],
}


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content
        self.response_metadata = {"model_name": "stub-model"}


class _FakeSelectModel:
    """Returns the canned select JSON; counts invocations to assert only_empty short-circuits."""

    model_name = "stub-model"

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return _FakeResponse(json.dumps(self._payload, ensure_ascii=False))


class ContingencyAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._orig_path = dc._contingency_runrecord_path
        dc._contingency_runrecord_path = lambda ot: tmp / f"{ot}.json"  # redirect overlay
        self.model = _FakeSelectModel(_SELECT_OUT)
        self._patch_model = mock.patch.object(asm_llm, "get_model", return_value=self.model)
        self._patch_model.start()
        self._patch_derive = mock.patch.object(
            dc, "derive_contingency_risks_for_plan", return_value=_CANNED_DERIVED
        )
        self._patch_derive.start()

    def tearDown(self) -> None:
        self._patch_model.stop()
        self._patch_derive.stop()
        dc._contingency_runrecord_path = self._orig_path
        self._tmp.cleanup()

    def test_select_drops_hallucination_and_empty_keeps_mandatory(self) -> None:
        out = dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        self.assertFalse(out["degraded"])
        include = out["outline"]["include"]
        # mandatory (global meta / has facts / consolidates) always kept
        for cid in ("doc-ch-meta", "doc-device", "doc-risks"):
            self.assertIn(cid, include, f"mandatory chapter {cid} dropped")
        # hallucinated id never survives schema validation
        self.assertNotIn("doc-FAKE", include)
        self.assertNotIn("doc-FAKE", out["outline"]["notes"])
        # empty, droppable, LLM-omitted chapter is tailored out
        self.assertNotIn("doc-service", include)
        # the validated note rides along
        self.assertEqual(out["outline"]["notes"].get("doc-device"), "本项目设备清单已就绪。")

    def test_human_pin_include_survives_regenerate(self) -> None:
        dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        pinned = dc.pin_contingency_chapter("京东", "doc-service", "include")
        self.assertIn("doc-service", pinned["pinnedInclude"])
        out = dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        self.assertIn("doc-service", out["outline"]["include"], "human-pinned chapter must survive re-tailor")

    def test_human_pin_exclude_overrides_mandatory(self) -> None:
        dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        dc.pin_contingency_chapter("京东", "doc-device", "exclude")
        out = dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        self.assertNotIn("doc-device", out["outline"]["include"], "human exclude must beat mandatory")
        self.assertEqual(out["outline"]["status"], "human_pinned")

    def test_only_empty_does_not_regenerate(self) -> None:
        dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        calls = self.model.calls
        dc.assemble_contingency_chapters(project_key="京东", mode="only_empty")
        self.assertEqual(self.model.calls, calls, "only_empty must not re-invoke the LLM once tailored")

    def test_apply_outline_filters_and_reorders(self) -> None:
        chapters = [{"id": "doc-a", "desc": "A"}, {"id": "doc-b"}, {"id": "doc-c"}]
        outline = {"include": ["doc-c", "doc-a"], "order": ["doc-c", "doc-a"], "notes": {"doc-c": "note c"}}
        res = asm_store.apply_outline(chapters, outline)
        self.assertEqual([c["id"] for c in res], ["doc-c", "doc-a"])  # filtered + reordered
        self.assertEqual(res[0].get("assemblyNote"), "note c")  # note attached non-destructively
        self.assertEqual(res[1].get("desc"), "A")  # skeleton preserved
        # empty selection / no overlay -> full directory unchanged (graceful default)
        self.assertEqual(len(asm_store.apply_outline(chapters, {"include": []})), 3)
        self.assertEqual(len(asm_store.apply_outline(chapters, None)), 3)

    def test_pin_exclude_then_restore_brings_chapter_back(self) -> None:
        dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        base = asm_store.read_outline("京东")["include"]
        target = next((c for c in base if c not in ("doc-ch-meta", "doc-risks")), base[-1])
        excl = dc.pin_contingency_chapter("京东", target, "exclude")
        self.assertNotIn(target, excl["include"])  # excluded -> dropped from visible set
        self.assertIn(target, excl["pinnedExclude"])
        rest = dc.pin_contingency_chapter("京东", target, "auto")
        self.assertNotIn(target, rest["pinnedExclude"])  # pin cleared
        self.assertIn(target, rest["include"])  # and the chapter is restored to the visible set

    def test_set_include_preserves_drag_order_and_clears_pins(self) -> None:
        # a prior assemble + pin leaves pins behind
        dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        dc.pin_contingency_chapter("京东", "doc-service", "exclude")
        # an explicit drag selection sets include/order verbatim (NOT sorted) and supersedes pins
        order = ["doc-risks", "doc-device", "doc-ch-meta"]
        res = asm_store.set_include("京东", order)
        self.assertEqual(res["include"], order)  # exact drag order, no re-sort by no
        self.assertEqual(res["order"], order)
        self.assertEqual(res["pinnedInclude"], [])
        self.assertEqual(res["pinnedExclude"], [])  # pins cleared — explicit selection is the truth
        self.assertEqual(res["status"], "manual")
        # dedupes
        self.assertEqual(asm_store.set_include("京东", ["doc-a", "doc-a", "doc-b"])["include"], ["doc-a", "doc-b"])

    def test_set_contingency_chapters_validates_and_drops_unselected(self) -> None:
        # uses the REAL directory (not the canned derive): unknown ids dropped, unselected data chapters not forced
        res = dc.set_contingency_chapters("京东", ["doc-device", "doc-BOGUS"])
        self.assertEqual(res["include"][0], "doc-device")  # drag order preserved
        self.assertNotIn("doc-BOGUS", res["include"])  # hallucinated/unknown id dropped
        # 计划章已绑定 DeliveryPlanRow（普通数据章），不再 structural —— 未显式选入则不在 include
        self.assertNotIn("doc-ch-12", res["include"])

    def test_list_contingency_chapters_returns_full_elements_and_include(self) -> None:
        out = dc.list_contingency_chapters("京东")
        ids = [e["id"] for e in out["elements"]]
        self.assertEqual(set(ids), {"doc-ch-meta", "doc-device", "doc-service", "doc-risks"})
        self.assertEqual(set(out["include"]), set(ids))  # no overlay yet -> all included by default
        dev = next(e for e in out["elements"] if e["id"] == "doc-device")
        self.assertEqual(dev["objectType"], "EquipmentConfig")
        self.assertEqual((dev["rowCount"], dev["riskCount"]), (1, 1))  # from canned rows/riskIds
        self.assertFalse(dev["structural"])
        self.assertTrue(next(e for e in out["elements"] if e["id"] == "doc-ch-meta")["structural"])

    def test_assemble_persist_false_returns_suggestion_without_writing(self) -> None:
        out = dc.assemble_contingency_chapters(project_key="京东", mode="regenerate", persist=False)
        self.assertTrue(out["outline"]["include"])  # a suggestion is returned
        self.assertIsNone(asm_store.read_outline("京东"))  # but nothing was persisted
        # a normal (persist=True) assemble does write
        dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        self.assertIsNotNone(asm_store.read_outline("京东"))

    def test_reset_clears_overlay_to_default(self) -> None:
        dc.set_contingency_chapters("京东", ["doc-device"])
        self.assertIsNotNone(asm_store.read_outline("京东"))  # a manual selection exists
        dc.reset_contingency_chapters("京东")
        self.assertIsNone(asm_store.read_outline("京东"))  # overlay cleared -> derive returns the full directory


class ContingencyDerivedDirectoryTests(unittest.TestCase):
    """The chapter directory is derived from the ontology (no Dolt) — fields from schema, marker chapters."""

    def test_fields_derived_from_schema(self) -> None:
        directory = dc._load_contingency_chapter_directory()
        device = next(c for c in directory if c["id"] == "doc-device")
        names = [f["name"] for f in device["fields"]]
        keys = [f["key"] for f in device["fields"]]
        # labels are the ontology displayNames, keys are the property apiNames — not hand-authored
        self.assertIn("型号", names)
        self.assertIn("总空间", names)
        self.assertIn("model", keys)
        self.assertIn("totalSpace", keys)

    def test_chapter_can_live_in_the_ontology_marker(self) -> None:
        marker_ids = [m["id"] for m in dc._contingency_chapter_markers()]
        self.assertIn("doc-testcase", marker_ids, "TestCase should declare a contingencyChapter marker")
        # every ObjectType-bound chapter is ontology-resident now (the placement table only keeps
        # the no-ObjectType 计划 placeholder)
        for cid in (
            "doc-ch-1", "doc-device", "doc-service", "doc-ch-4", "doc-ch-5",
            "doc-ch-10", "doc-ch-6", "doc-network", "doc-ch-8", "doc-acceptance",
        ):
            self.assertIn(cid, marker_ids, f"{cid} should be declared as a contingencyChapter marker")
        directory = dc._load_contingency_chapter_directory()
        testcase = next(c for c in directory if c["id"] == "doc-testcase")
        self.assertEqual(testcase["objectType"], "TestCase")
        # fields still derive from the bound ObjectType schema (apiName order from the marker fieldOrder)
        self.assertEqual(
            [f["key"] for f in testcase["fields"]],
            ["level3Category", "testCaseName", "caseCode", "testPurpose"],
        )
        # marker-carried decisionId / lane ride through the loader untouched (Decision_Chapters FK)
        device = next(c for c in directory if c["id"] == "doc-device")
        self.assertEqual(device["decisionId"], "DP-SUB-DEVICE")
        self.assertEqual(device["lane"], "device")

    def test_project_scoped_fetch_keeps_global_chapter_rows(self) -> None:
        """Global reusable libraries without projectKey should still project into project reports."""
        directory = [{"id": "doc-testcase", "objectType": "TestCase"}]
        global_rows = [{"testCaseId": "test_case-0001", "projectKey": "", "caseCode": "TC-OPT-001"}]

        def fake_get_object_data(object_type: str, project_id: str | None = None):
            self.assertEqual(object_type, "TestCase")
            return [] if project_id == "京东" else global_rows

        with mock.patch.object(dc, "_load_contingency_chapter_directory", return_value=directory), \
             mock.patch.object(dc, "get_object_data", side_effect=fake_get_object_data):
            rows_by_type = dc._fetch_chapter_object_rows("京东", {})

        self.assertEqual(rows_by_type["TestCase"], global_rows)

    def test_directory_preserves_stable_ids_and_order(self) -> None:
        directory = dc._load_contingency_chapter_directory()
        ids = [c["id"] for c in directory]
        self.assertEqual(ids[0], "doc-ch-1")  # 元数据章已删，纯数字 no 升序 → 项目背景首位
        self.assertEqual(len(ids), len(set(ids)))  # no dup ids
        for cid in ("doc-device", "doc-network", "doc-acceptance", "doc-ch-12", "doc-testcase"):
            self.assertIn(cid, ids)
        # the deleted 元数据 / 风险&假设 chapters never come back
        self.assertNotIn("doc-ch-meta", ids)
        self.assertNotIn("doc-risks", ids)


class AdhocChapterTests(unittest.TestCase):
    """doc-ot-* 临时章：本体类型库候选 → set 放行 → derive 读时 materialize → assemble 强保 → reset 即清。

    Real directory + real derive (no canned patch — materialization is the behavior under test);
    the overlay is redirected to a temp dir so the project's real ContingencyOutline is untouched.
    Row counts are never asserted (Dolt may be offline; rows degrade to [] gracefully).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._orig_path = dc._contingency_runrecord_path
        dc._contingency_runrecord_path = lambda ot: tmp / f"{ot}.json"  # redirect overlay

    def tearDown(self) -> None:
        dc._contingency_runrecord_path = self._orig_path
        self._tmp.cleanup()

    def test_candidates_expose_unbound_business_types_only(self) -> None:
        out = dc.list_contingency_chapters("京东")
        cands = out["candidates"]
        self.assertTrue(cands, "本体类型库 must not be empty")
        types = {c["objectType"] for c in cands}
        self.assertIn("ServiceConfig", types)  # known business type with no chapter
        for banned in ("DecisionPoint", "RiskRule", "RiskItem", "ContingencyOutline", "PlanVersionLog"):
            self.assertNotIn(banned, types, f"runtime/mechanism type {banned} must not be a candidate")
        self.assertNotIn("EquipmentConfig", types)  # already bound to doc-device
        svc = next(c for c in cands if c["objectType"] == "ServiceConfig")
        self.assertEqual(svc["id"], "doc-ot-ServiceConfig")
        self.assertTrue(svc["fields"], "schema-derived field projection rides along")
        self.assertFalse(svc["structural"])
        self.assertTrue(svc["candidate"])
        counts = [int(c.get("rowCount") or 0) for c in cands]
        self.assertEqual(counts, sorted(counts, reverse=True))  # 行数降序

    def test_set_accepts_eligible_adhoc_and_drops_ineligible(self) -> None:
        res = dc.set_contingency_chapters(
            "京东",
            ["doc-ch-1", "doc-ot-ServiceConfig", "doc-device", "doc-ot-DecisionPoint", "doc-ot-Nope"],
        )
        self.assertEqual(res["include"][:3], ["doc-ch-1", "doc-ot-ServiceConfig", "doc-device"])
        self.assertNotIn("doc-ot-DecisionPoint", res["include"])  # denylist
        self.assertNotIn("doc-ot-Nope", res["include"])  # unknown type
        self.assertNotIn("doc-ch-12", res["include"])  # 计划章现为普通数据章（绑定 DeliveryPlanRow），未拖入则不强制纳入

    def test_derive_materializes_adhoc_chapter_in_outline_order(self) -> None:
        dc.set_contingency_chapters("京东", ["doc-ch-1", "doc-ot-ServiceConfig", "doc-device"])
        derived = dc.derive_contingency_risks_for_plan(project_key="京东")
        ids = [c["id"] for c in derived["chapters"]]
        self.assertEqual(ids.index("doc-ot-ServiceConfig"), 1)  # 拖动位置即章节顺序
        chapter = derived["chapters"][1]
        self.assertEqual(chapter["objectType"], "ServiceConfig")
        self.assertTrue(chapter.get("adhoc"))
        self.assertTrue(chapter.get("fields"))  # 字段来自 ObjectType schema
        self.assertTrue(all(f.get("key") for f in chapter["fields"]))
        # materialized adhoc chapter is an element (composer can render it) and leaves the candidates
        out = dc.list_contingency_chapters("京东")
        self.assertIn("doc-ot-ServiceConfig", [e["id"] for e in out["elements"]])
        self.assertNotIn("doc-ot-ServiceConfig", [c["id"] for c in out["candidates"]])

    def test_assemble_preserves_manual_adhoc(self) -> None:
        dc.set_contingency_chapters("京东", ["doc-device", "doc-ot-ServiceConfig"])
        model = _FakeSelectModel(
            {"include": ["doc-device"], "order": ["doc-device"], "notes": {}, "rationale": "裁剪"}
        )
        with mock.patch.object(asm_llm, "get_model", return_value=model):
            out = dc.assemble_contingency_chapters(project_key="京东", mode="regenerate")
        self.assertIn(
            "doc-ot-ServiceConfig", out["outline"]["include"], "AI 重排不得静默丢手动拖入的临时章"
        )

    def test_reset_clears_adhoc_chapters(self) -> None:
        dc.set_contingency_chapters("京东", ["doc-device", "doc-ot-ServiceConfig"])
        dc.reset_contingency_chapters("京东")
        derived = dc.derive_contingency_risks_for_plan(project_key="京东")
        self.assertNotIn("doc-ot-ServiceConfig", [c["id"] for c in derived["chapters"]])


class ContingencyGroupTests(unittest.TestCase):
    """章节融合（groups）：apply_outline 折叠成组章 + set/list/reset 落库 + 临时章成员 materialize。

    Real directory + real derive (no canned patch); overlay redirected to a temp dir so the project's
    real ContingencyOutline is untouched. Row counts are never asserted (Dolt may be offline).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._orig_path = dc._contingency_runrecord_path
        dc._contingency_runrecord_path = lambda ot: tmp / f"{ot}.json"  # redirect overlay

    def tearDown(self) -> None:
        dc._contingency_runrecord_path = self._orig_path
        self._tmp.cleanup()

    # --- pure folding (no overlay needed) ---
    def test_apply_outline_folds_group_into_composite(self) -> None:
        chapters = [
            {"id": "doc-ch-1", "title": "项目背景"},
            {"id": "doc-device", "title": "设备配置", "decisionPoint": "device",
             "decisionLabel": "设备配置可交付性", "riskIds": ["R1", "R2"],
             "rows": [{"a": 1}], "columns": [{"key": "a"}]},
            {"id": "doc-ot-ComponentConfig", "title": "部件配置", "decisionPoint": "global",
             "riskIds": ["R2", "R3"], "rows": [{"b": 2}]},
            {"id": "doc-acceptance", "title": "验收策略", "riskIds": []},
        ]
        outline = {
            "include": ["doc-ch-1", "doc-grp-1", "doc-acceptance"],
            "order": ["doc-ch-1", "doc-grp-1", "doc-acceptance"],
            "groups": {"doc-grp-1": {"title": "设备与部件配置",
                                     "members": ["doc-device", "doc-ot-ComponentConfig"],
                                     "decisionPoint": "device"}},
        }
        out = asm_store.apply_outline(chapters, outline)
        # members fold into the group → never render standalone
        self.assertEqual([c["id"] for c in out], ["doc-ch-1", "doc-grp-1", "doc-acceptance"])
        grp = next(c for c in out if c["id"] == "doc-grp-1")
        self.assertTrue(grp["isGroup"])
        self.assertEqual(grp["title"], "设备与部件配置")
        self.assertEqual(grp["memberIds"], ["doc-device", "doc-ot-ComponentConfig"])
        self.assertEqual(grp["riskIds"], ["R1", "R2", "R3"])  # union, deduped, order preserved
        self.assertEqual(grp["state"], "gap")
        self.assertEqual(grp["decisionLabel"], "设备配置可交付性")
        # 复合章：组章自身无顶层表，但 nest 完整成员章（各自保留原始数据表）
        self.assertNotIn("rows", grp)
        self.assertNotIn("columns", grp)
        self.assertIn("members", grp)
        self.assertEqual([m["id"] for m in grp["members"]], ["doc-device", "doc-ot-ComponentConfig"])
        dev = grp["members"][0]
        self.assertEqual(dev["rows"], [{"a": 1}])  # 成员原始数据表被保留
        self.assertEqual(dev["title"], "设备配置")

    def test_apply_outline_drops_group_with_no_resolvable_member(self) -> None:
        chapters = [{"id": "doc-a"}]
        outline = {"include": ["doc-grp-1"], "order": ["doc-grp-1"],
                   "groups": {"doc-grp-1": {"title": "G", "members": ["doc-missing"]}}}
        self.assertEqual(asm_store.apply_outline(chapters, outline), [])

    # --- set / list / reset round-trip (real directory) ---
    def test_set_stores_valid_group_and_hides_members(self) -> None:
        groups = {"doc-grp-1": {"title": "设备与部件配置",
                                "members": ["doc-device", "doc-service"], "decisionPoint": "device"}}
        res = dc.set_contingency_chapters("京东", ["doc-ch-1", "doc-grp-1", "doc-device", "doc-service"], groups)
        self.assertIn("doc-grp-1", res["include"])
        self.assertNotIn("doc-device", res["include"])  # member -> not standalone
        self.assertNotIn("doc-service", res["include"])
        self.assertEqual(res["groups"]["doc-grp-1"]["members"], ["doc-device", "doc-service"])
        self.assertEqual(res["groups"]["doc-grp-1"]["title"], "设备与部件配置")

    def test_set_degrades_single_member_group(self) -> None:
        groups = {"doc-grp-1": {"title": "G", "members": ["doc-device", "doc-BOGUS"]}}
        res = dc.set_contingency_chapters("京东", ["doc-grp-1", "doc-network"], groups)
        self.assertNotIn("doc-grp-1", res["include"])  # only 1 valid member -> degraded
        self.assertEqual(res.get("groups", {}), {})
        self.assertIn("doc-device", res["include"])  # lone member becomes standalone

    def test_set_preserves_human_title_by(self) -> None:
        # 人工改名标记 titleBy='human' 透传落库；缺省不写 human（保持 auto，允许 AI 融合命名）。
        res = dc.set_contingency_chapters(
            "京东", ["doc-grp-1"],
            {"doc-grp-1": {"title": "我的章名", "members": ["doc-device", "doc-service"], "titleBy": "human"}},
        )
        self.assertEqual(res["groups"]["doc-grp-1"].get("titleBy"), "human")
        res2 = dc.set_contingency_chapters(
            "京东", ["doc-grp-1"],
            {"doc-grp-1": {"title": "x", "members": ["doc-device", "doc-service"]}},
        )
        self.assertNotEqual(res2["groups"]["doc-grp-1"].get("titleBy"), "human")

    def test_set_group_title_writeback_respects_human(self) -> None:
        # set_group_title：auto 组可被 AI 标题覆盖；human 组不被覆盖。
        dc.set_contingency_chapters(
            "京东", ["doc-grp-1"],
            {"doc-grp-1": {"title": "默认拼接名", "members": ["doc-device", "doc-service"]}},
        )
        self.assertTrue(asm_store.set_group_title("京东", "doc-grp-1", "设备与部件配置", source="ai"))
        title, by = asm_store.group_title("京东", "doc-grp-1")
        self.assertEqual((title, by), ("设备与部件配置", "ai"))
        # 人工改名后，AI 写回被拒
        dc.set_contingency_chapters(
            "京东", ["doc-grp-1"],
            {"doc-grp-1": {"title": "我的章名", "members": ["doc-device", "doc-service"], "titleBy": "human"}},
        )
        self.assertFalse(asm_store.set_group_title("京东", "doc-grp-1", "又一个AI名", source="ai"))
        self.assertEqual(asm_store.group_title("京东", "doc-grp-1"), ("我的章名", "human"))

    def test_set_dedupes_member_across_groups(self) -> None:
        groups = {
            "doc-grp-1": {"title": "G1", "members": ["doc-device", "doc-service"]},
            "doc-grp-2": {"title": "G2", "members": ["doc-service", "doc-network", "doc-acceptance"]},
        }
        res = dc.set_contingency_chapters("京东", ["doc-grp-1", "doc-grp-2"], groups)
        self.assertEqual(res["groups"]["doc-grp-1"]["members"], ["doc-device", "doc-service"])
        self.assertEqual(res["groups"]["doc-grp-2"]["members"], ["doc-network", "doc-acceptance"])  # service deduped

    def test_list_returns_groups(self) -> None:
        dc.set_contingency_chapters("京东", ["doc-grp-1"],
                                    {"doc-grp-1": {"title": "G", "members": ["doc-device", "doc-service"]}})
        out = dc.list_contingency_chapters("京东")
        self.assertIn("doc-grp-1", out.get("groups", {}))
        self.assertEqual(out["groups"]["doc-grp-1"]["members"], ["doc-device", "doc-service"])

    def test_reset_clears_groups(self) -> None:
        dc.set_contingency_chapters("京东", ["doc-grp-1"],
                                    {"doc-grp-1": {"title": "G", "members": ["doc-device", "doc-service"]}})
        self.assertTrue(asm_store.read_outline("京东").get("groups"))
        dc.reset_contingency_chapters("京东")
        self.assertIsNone(asm_store.read_outline("京东"))

    def test_derive_materializes_adhoc_group_member(self) -> None:
        # 关键接线点：仅作为融合组成员（不在 include 顶层）的 doc-ot-* 也必须被 materialize，
        # 否则 apply_outline 折叠组时取不到该成员。
        dc.set_contingency_chapters(
            "京东",
            ["doc-ch-1", "doc-grp-1", "doc-device"],
            {"doc-grp-1": {"title": "服务与组网", "members": ["doc-ot-ServiceConfig", "doc-network"],
                           "decisionPoint": "network"}},
        )
        derived = dc.derive_contingency_risks_for_plan(project_key="京东")
        ids = [c["id"] for c in derived["chapters"]]
        self.assertIn("doc-grp-1", ids)
        self.assertNotIn("doc-ot-ServiceConfig", ids)  # adhoc member folded into group, not standalone
        self.assertNotIn("doc-network", ids)
        grp = next(c for c in derived["chapters"] if c["id"] == "doc-grp-1")
        self.assertTrue(grp.get("isGroup"))
        self.assertEqual(list(grp.get("memberIds")), ["doc-ot-ServiceConfig", "doc-network"])
        self.assertNotIn("rows", grp)  # 单段融合正文、无独立数据表


if __name__ == "__main__":
    unittest.main()
