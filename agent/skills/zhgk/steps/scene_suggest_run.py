"""
scene_suggest_run · 场景建议生成

意图: scene_suggest 专属

根据代际-制冷给出勘测场景推荐：
  1. 从 project 或 project_info.json 取 generation_cooling
  2. get_sub_scenes_for_cooling → 细分场景列表
  3. 加载底表统计各场景条目数（需底表存在；若无底表则仅返回场景名）
  4. LLM 生成中文场景推荐摘要
  5. 返回 metrics 及推荐文本
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip


def _get_generation_cooling(ctx: SkillContext) -> str:
    gc = ctx.project.get("generation_cooling", "")
    if gc:
        return gc
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            return json.loads(info_path.read_text(encoding="utf-8")).get("generation_cooling", "")
        except Exception:
            pass
    return ""


class SceneSuggestRunStep(BaseStep):
    key = "scene_suggest_run"
    name = "场景建议生成"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        # generation_cooling 由 determine_gen 提供
        if not _get_generation_cooling(ctx):
            return {
                "ok": False,
                "missing": [],
                "note": "需先完成代际制冷识别（determine_gen）",
            }
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        from ..services.table_filter import get_sub_scenes_for_cooling

        gen_cooling = _get_generation_cooling(ctx)
        if not gen_cooling:
            raise RuntimeError("scene_suggest_run: generation_cooling 未知")

        sub_scenes = get_sub_scenes_for_cooling(gen_cooling)
        emit(f"[scene_suggest_run] 代际制冷: {gen_cooling}")
        emit(f"[scene_suggest_run] 推荐细分场景: {sub_scenes}")

        # 尝试从底表统计各场景条目数
        scene_counts: dict[str, int] = {}
        from ..path_config import get_base_table_path
        base_table_path = get_base_table_path()
        if os.path.exists(base_table_path):
            try:
                from ..services.table_filter import load_base_table, filter_items
                items = load_base_table(base_table_path)
                filtered = filter_items(items, generation_cooling=gen_cooling, category="标准")
                for item in filtered:
                    scene = item.get("细分场景", "其他")
                    scene_counts[scene] = scene_counts.get(scene, 0) + 1
                for scene, count in scene_counts.items():
                    emit(f"[scene_suggest_run]   {scene}: {count} 条标准勘测项")
            except Exception as e:
                emit(f"[scene_suggest_run] ⚠ 底表统计失败（{e}），仅返回场景名")

        # LLM 生成推荐摘要
        proj = ctx.project
        try:
            scene_detail = "\n".join(
                f"  - {s}（{scene_counts.get(s, '?')} 条勘测项）" for s in sub_scenes
            )
            prompt = (
                f"你是 AIDA 智慧工勘 AI。用户咨询项目「{proj.get('project_name', '未知')}」"
                f"机房「{proj.get('room_name', '未知')}」的勘测场景推荐。\n\n"
                f"代际-制冷: {gen_cooling}\n"
                f"推荐细分场景:\n{scene_detail}\n\n"
                f"请用 2-3 句话介绍这几个勘测场景的核心关注点和推荐顺序，"
                f"语言精炼，适合工程师阅读。不加标号，不客套。"
            )
            resp = ctx.invoke_llm(
                [
                    ("system", "你是华为智算 ICT 交付工勘 AI，回答精炼。"),
                    ("human", prompt),
                ],
                step_key=self.key,
            )
            summary = resp.content if isinstance(resp.content, str) else str(resp.content)
            for line in summary.splitlines():
                emit(f"[scene_suggest_run] 🤖 {line}")
        except Exception as e:
            emit(f"[scene_suggest_run] ⚠ LLM 摘要跳过（{e}）")
            summary = f"推荐场景: {', '.join(sub_scenes)}"

        return {
            "metrics": {
                "generation_cooling": gen_cooling,
                "sub_scenes": sub_scenes,
                "scene_counts": scene_counts,
                "scene_summary": summary,
            }
        }
