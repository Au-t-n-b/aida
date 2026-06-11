"""
filter_build · 底表过滤 + 全量勘测结果表构建

意图: survey_work 专属

流程：
  1. 从 project_info.json 或 ctx.project 取 generation_cooling
  2. load_base_table(入场评估标准表.xlsx)
  3. get_sub_scenes_for_cooling(generation_cooling) 取细分场景列表
  4. filter_items(items, generation_cooling, category="标准", sub_scenes) 过滤
  5. build_survey_table(filtered, output_dir, activity_id, project_name, room_name) 生成
  6. 将 survey_table_path 写入 project_info.json["survey_table_path"]
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip


def _get_generation_cooling(ctx: SkillContext, state: SkillState) -> str:
    """按优先级获取 generation_cooling: project → project_info.json → state metrics"""
    gc = ctx.project.get("generation_cooling", "")
    if gc:
        return gc
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            gc = json.loads(info_path.read_text(encoding="utf-8")).get(
                "generation_cooling", ""
            )
            if gc:
                return gc
        except Exception:
            pass
    metrics = (state or {}).get("metrics") or {}
    return metrics.get("generation_cooling", "")


def _update_project_info(runtime_dir, key: str, value) -> None:
    """追加/更新 project_info.json 的单个字段。"""
    info_path = runtime_dir / "project_info.json"
    try:
        existing = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    except Exception:
        existing = {}
    existing[key] = value
    runtime_dir.mkdir(parents=True, exist_ok=True)
    info_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


class FilterBuildStep(BaseStep):
    key = "filter_build"
    name = "底表过滤建表"
    artifacts_pattern = ["ProjectData/Output/*全量勘测结果表*.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        missing = []

        # 1. 入场评估标准表
        from ..path_config import get_base_table_path
        base_table = get_base_table_path()
        if not os.path.exists(base_table):
            missing.append("ProjectData/Template/入场评估标准表.xlsx")

        # 2. generation_cooling
        gc = ctx.project.get("generation_cooling", "")
        if not gc:
            info_path = ctx.runtime_dir / "project_info.json"
            if info_path.exists():
                try:
                    gc = json.loads(info_path.read_text(encoding="utf-8")).get(
                        "generation_cooling", ""
                    )
                except Exception:
                    pass
        if not gc:
            return {
                "ok": False,
                "missing": missing,
                "note": "需先完成代际制冷识别（determine_gen 步骤尚未产出代际-制冷标签）",
            }

        return {"ok": not missing, "missing": missing}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        from ..services.table_filter import load_base_table, filter_items, get_sub_scenes_for_cooling
        from ..services.survey_table_builder import build_survey_table, survey_table_path_for
        from ..path_config import get_base_table_path

        gen_cooling = _get_generation_cooling(ctx, state)
        if not gen_cooling:
            raise RuntimeError(
                "filter_build: generation_cooling 未知，请先完成 determine_gen 步骤"
            )

        proj = ctx.project
        project_name = proj.get("project_name", "未知项目")
        activity_id  = proj.get("activity_id", "")
        room_name    = proj.get("room_name", "")

        base_table_path = get_base_table_path()
        emit(f"[filter_build] 加载底表: {os.path.basename(base_table_path)}")

        items = load_base_table(base_table_path)
        emit(f"[filter_build] 底表总条目: {len(items)}")

        sub_scenes = get_sub_scenes_for_cooling(gen_cooling)
        emit(f"[filter_build] 细分场景（{gen_cooling}）: {sub_scenes}")

        filtered = filter_items(
            items,
            generation_cooling=gen_cooling,
            category="标准",
            sub_scenes=sub_scenes,
        )
        emit(f"[filter_build] 过滤后条目: {len(filtered)} 条（标准类，{gen_cooling}）")

        output_dir = str(ctx.output_dir)
        # 幂等：resume 走 full_restart 会重放本步。若结果表已存在则复用、不重建，
        # 否则会覆盖 wait_survey 已合并的「最新检查结果 / 第N轮」列 → assess 评空表全判「未勘测」。
        expected_path = survey_table_path_for(output_dir, activity_id, project_name, room_name)
        if os.path.exists(expected_path):
            survey_table_path = expected_path
            emit(f"[filter_build] ✓ 复用已存在的结果表（幂等，保住已合并勘测结果）: {os.path.basename(expected_path)}")
        else:
            survey_table_path = build_survey_table(
                filtered_items=filtered,
                output_dir=output_dir,
                activity_id=activity_id,
                project_name=project_name,
                room_name=room_name,
            )
            emit(f"[filter_build] ✓ 全量勘测结果表: {os.path.basename(survey_table_path)}")

        # 写路径到 project_info.json
        _update_project_info(ctx.runtime_dir, "survey_table_path", survey_table_path)

        # 前 10 条进 metrics（SDUI 条目预览 Table）
        preview_rows = [
            {
                "细分场景": str(it.get("细分场景", "") or ""),
                "勘测要素": str(it.get("勘测要素", "") or ""),
                "项目":     str(it.get("项目", "") or ""),
                "勘测方法": str(it.get("勘测方法", "") or ""),
            }
            for it in filtered[:10]
        ]

        return {
            "metrics": {
                "generation_cooling":  gen_cooling,
                "sub_scenes":          sub_scenes,
                "filtered_count":      len(filtered),
                "survey_table_path":   survey_table_path,
                "preview_rows":        preview_rows,
            },
            "artifacts": [ctx.rel(survey_table_path)],
        }
