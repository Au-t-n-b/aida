"""Offline tests for the contingency chapter-narrative feature (LangGraph + run-record overlay).

Hermetic: the LLM is a stub (no network) and the run-record overlay is redirected to a temp dir, so
the full loop runs without Dolt or a live model. Run from this directory:

    cd ontology/tests
    ../.venv/Scripts/python -m unittest -v test_contingency_narrative
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_ONTOLOGY_DIR = Path(__file__).resolve().parents[1]
if str(_ONTOLOGY_DIR) not in sys.path:
    sys.path.insert(0, str(_ONTOLOGY_DIR))

import data_connector as dc  # noqa: E402
from contingency_narrative import llm as narr_llm  # noqa: E402

_MERGE_TEXT = "智能融合稿：保留人工改动并融入最新事实。"


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content
        self.response_metadata = {"model_name": "stub-model"}


class _FakeModel:
    """Returns canned prose; distinguishes generate vs merge by the system prompt."""

    model_name = "stub-model"

    def __init__(self) -> None:
        self.gen_calls = 0
        self.merge_calls = 0
        self.generated_systems: list[str] = []

    def invoke(self, messages):
        system = messages[0]["content"] if messages else ""
        if "协同编辑助手" in system:  # MERGE_SYSTEM
            self.merge_calls += 1
            return _FakeResponse(_MERGE_TEXT)
        self.generated_systems.append(system)
        self.gen_calls += 1
        return _FakeResponse(f"AI生成的章节正文片段{self.gen_calls}（基于给定事实）。")


class ContingencyNarrativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._orig_path = dc._contingency_runrecord_path
        dc._contingency_runrecord_path = lambda ot: tmp / f"{ot}.json"  # redirect overlay
        self.model = _FakeModel()
        self._patch_model = mock.patch.object(narr_llm, "get_model", return_value=self.model)
        self._patch_model.start()

    def tearDown(self) -> None:
        self._patch_model.stop()
        dc._contingency_runrecord_path = self._orig_path
        self._tmp.cleanup()

    def test_generate_only_empty_writes_ai_drafts(self) -> None:
        out = dc.generate_contingency_narratives(project_key="京东", scope="all", mode="only_empty")
        self.assertFalse(out["degraded"])
        self.assertTrue(out["narratives"], "expected at least one chapter narrative")
        sample = out["narratives"][0]
        self.assertEqual(sample["status"], "ai_draft")
        self.assertTrue(sample["displayText"])
        self.assertGreater(self.model.gen_calls, 0)

    def test_project_background_uses_one_sentence_overview_prompt(self) -> None:
        dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-ch-1", mode="only_empty"
        )
        self.assertTrue(self.model.generated_systems, "expected the project background chapter to generate")
        prompt = self.model.generated_systems[-1]
        self.assertIn("一句", prompt)
        self.assertIn("总览", prompt)
        self.assertNotIn("2–4 个自然段", prompt)
        self.assertNotIn("150–350 字", prompt)

    # 生成机制类测试一律打在 doc-ch-1（项目背景）上：它是 NARRATIVE_CHAPTERS 白名单里唯一的章，
    # 非白名单章（如 doc-device）即使 scope=chapter 也会被 gather() 过滤、不产正文（产品行为）。
    def test_only_empty_skips_chapters_that_already_have_text(self) -> None:
        dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-ch-1", mode="only_empty"
        )
        calls = self.model.gen_calls
        self.assertGreater(calls, 0, "whitelisted chapter should generate")
        dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-ch-1", mode="only_empty"
        )
        self.assertEqual(self.model.gen_calls, calls, "only_empty should not regenerate existing")

    def test_human_edit_survives_regenerate_then_smart_merge_then_accept(self) -> None:
        dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-ch-1", mode="only_empty"
        )
        edited = dc.edit_chapter_narrative("京东", "doc-ch-1", "人工修订的背景章正文", edited_by="张三")
        self.assertEqual(edited["status"], "human_edited")
        self.assertEqual(edited["displayText"], "人工修订的背景章正文")

        # regenerate: new draft parked in pendingGenerated, edited text untouched
        regen = dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-ch-1", mode="regenerate"
        )
        row = next(n for n in regen["narratives"] if n["chapterId"] == "doc-ch-1")
        self.assertEqual(row["status"], "regen_pending")
        self.assertTrue(row["pendingGenerated"])
        self.assertEqual(row["editedText"], "人工修订的背景章正文")
        self.assertEqual(row["displayText"], "人工修订的背景章正文")

        # smart merge: candidate produced, edited text still untouched
        merged = dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-ch-1", mode="smart_merge"
        )
        row = next(n for n in merged["narratives"] if n["chapterId"] == "doc-ch-1")
        self.assertEqual(row["mergeCandidate"], _MERGE_TEXT)
        self.assertEqual(row["editedText"], "人工修订的背景章正文")
        self.assertGreater(self.model.merge_calls, 0)

        # accept the fused candidate -> becomes the text, candidates cleared
        accepted = dc.accept_chapter_merge("京东", "doc-ch-1", "candidate", edited_by="张三")
        self.assertEqual(accepted["status"], "merged")
        self.assertEqual(accepted["displayText"], _MERGE_TEXT)
        self.assertEqual(accepted["pendingGenerated"], "")
        self.assertEqual(accepted["mergeCandidate"], "")

    def test_accept_keep_mine_discards_pending(self) -> None:
        dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-ch-1", mode="only_empty"
        )
        dc.edit_chapter_narrative("京东", "doc-ch-1", "我的稿", edited_by="张三")
        dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-ch-1", mode="regenerate"
        )
        kept = dc.accept_chapter_merge("京东", "doc-ch-1", "mine", edited_by="张三")
        self.assertEqual(kept["displayText"], "我的稿")
        self.assertEqual(kept["pendingGenerated"], "")

    def test_version_milestone_and_restore(self) -> None:
        dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-ch-1", mode="only_empty"
        )
        dc.edit_chapter_narrative("京东", "doc-ch-1", "第一版人工稿", edited_by="张三")
        v1 = dc.save_contingency_plan_version("京东", "V1.0", created_by="张三")
        self.assertTrue(any(x["planVersion"] == "V1.0" for x in v1["versions"]))

        dc.edit_chapter_narrative("京东", "doc-ch-1", "第二版人工稿", edited_by="张三")
        v2 = dc.save_contingency_plan_version("京东", "V2.0", created_by="张三")
        self.assertTrue(v2["changeSummary"].startswith("V2.0"))
        self.assertIn("项目背景", v2["changeSummary"])  # changed chapter listed by title

        restored = dc.restore_chapter_narrative_version(
            "京东", "doc-ch-1", version_label="V1.0", edited_by="张三"
        )
        self.assertEqual(restored["displayText"], "第一版人工稿")
        self.assertEqual(restored["status"], "human_edited")

    def test_narrative_injected_into_derive_chapters(self) -> None:
        dc.edit_chapter_narrative("京东", "doc-device", "注入测试正文", edited_by="李四")
        result = dc.derive_contingency_risks_for_plan(project_key="京东")
        chapter = next((c for c in result["chapters"] if c.get("id") == "doc-device"), None)
        self.assertIsNotNone(chapter, "doc-device chapter missing from derive output")
        self.assertEqual(chapter.get("narrative"), "注入测试正文")
        self.assertEqual(chapter.get("narrativeStatus"), "human_edited")
        # static skeleton desc is preserved (caption), not overwritten by the prose
        self.assertTrue(chapter.get("desc"))
        self.assertNotEqual(chapter.get("desc"), "注入测试正文")

    def test_group_chapter_fuses_members_with_group_prompt(self) -> None:
        # 建融合组（设备+部件）后为组章生成正文：应走 GROUP_FUSION_SYSTEM、把成员事实融合成单段，
        # 并以组 id 落一条 ChapterNarrative。
        dc.set_contingency_chapters(
            "京东",
            ["doc-ch-1", "doc-grp-1", "doc-device"],
            {"doc-grp-1": {"title": "设备与部件配置",
                           "members": ["doc-device", "doc-service"], "decisionPoint": "device"}},
        )
        out = dc.generate_contingency_narratives(
            project_key="京东", scope="chapter", chapter_id="doc-grp-1", mode="only_empty"
        )
        self.assertFalse(out["degraded"])
        # the group fusion prompt drove generation (a title-only fallback call may follow it when the
        # stub doesn't emit JSON, so assert membership rather than the last system prompt)
        systems = self.model.generated_systems
        self.assertTrue(systems, "expected the group chapter to generate")
        self.assertTrue(
            any("融合章节" in s and "members" in s for s in systems),
            "group fusion prompt should drive generation",
        )
        # narrative persisted under the group id
        narr = next((n for n in out["narratives"] if n["chapterId"] == "doc-grp-1"), None)
        self.assertIsNotNone(narr, "group chapter narrative not written")
        self.assertTrue(narr["displayText"])
        self.assertEqual(narr["status"], "ai_draft")

    def test_group_narrative_injected_into_derive(self) -> None:
        # 组章正文经 derive 注入到组章 chapter dict（前端据此渲染单段融合正文）。
        dc.set_contingency_chapters(
            "京东",
            ["doc-ch-1", "doc-grp-1", "doc-device"],
            {"doc-grp-1": {"title": "设备与部件配置",
                           "members": ["doc-device", "doc-service"], "decisionPoint": "device"}},
        )
        dc.edit_chapter_narrative("京东", "doc-grp-1", "融合章人工正文", edited_by="李四")
        result = dc.derive_contingency_risks_for_plan(project_key="京东")
        grp = next((c for c in result["chapters"] if c.get("id") == "doc-grp-1"), None)
        self.assertIsNotNone(grp, "group chapter missing from derive output")
        self.assertTrue(grp.get("isGroup"))
        self.assertEqual(grp.get("narrative"), "融合章人工正文")
        self.assertNotIn("rows", grp)  # 组章自身无顶层数据表
        self.assertTrue(grp.get("members"))  # 但 nest 完整成员（报告渲染各自原始表单）

    def test_group_title_fused_and_human_rename_wins(self) -> None:
        from contingency_assembly import store as asm_store

        class _GroupJsonModel:
            model_name = "stub-group"

            def invoke(self, messages):
                system = messages[0]["content"] if messages else ""
                if "融合章节" in system:  # GROUP_FUSION_SYSTEM → 返回 {title,intro}
                    return _FakeResponse('{"title": "设备与部件配置", "intro": "本章整合设备与部件配置的关键事实。"}')
                return _FakeResponse("普通章正文。")

        with mock.patch.object(narr_llm, "get_model", return_value=_GroupJsonModel()):
            # auto 组：AI 融合标题写回 overlay + 进 narrative.chapterTitle；intro 落正文
            dc.set_contingency_chapters(
                "京东", ["doc-ch-1", "doc-grp-1", "doc-device"],
                {"doc-grp-1": {"title": "设备配置信息 + 部件配置信息",
                               "members": ["doc-device", "doc-service"], "decisionPoint": "device"}},
            )
            out = dc.generate_contingency_narratives(
                project_key="京东", scope="chapter", chapter_id="doc-grp-1", mode="only_empty"
            )
            narr = next(n for n in out["narratives"] if n["chapterId"] == "doc-grp-1")
            self.assertEqual(narr["chapterTitle"], "设备与部件配置")  # 有效标题=AI 融合名
            self.assertIn("整合", narr["displayText"])  # intro 落正文
            self.assertEqual(asm_store.group_title("京东", "doc-grp-1"), ("设备与部件配置", "ai"))

            # 人工改名（titleBy='human'）后重生成：AI 标题不覆盖
            dc.set_contingency_chapters(
                "京东", ["doc-ch-1", "doc-grp-1", "doc-device"],
                {"doc-grp-1": {"title": "我的自定义章名", "members": ["doc-device", "doc-service"],
                               "decisionPoint": "device", "titleBy": "human"}},
            )
            out2 = dc.generate_contingency_narratives(
                project_key="京东", scope="chapter", chapter_id="doc-grp-1", mode="regenerate"
            )
            narr2 = next(n for n in out2["narratives"] if n["chapterId"] == "doc-grp-1")
            self.assertEqual(narr2["chapterTitle"], "我的自定义章名")  # 人工优先
            self.assertEqual(asm_store.group_title("京东", "doc-grp-1"), ("我的自定义章名", "human"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
