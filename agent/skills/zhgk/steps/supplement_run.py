"""
supplement_run · 补充勘测处理

意图: supplement 专属

向已有的全量勘测结果表追加数据类条目：
  1. 检查已有勘测结果表
  2. HITL ChoiceCard：追加全部数据条目 / 跳过
  3. 执行 append_data_items() 追加
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip

_SUPPLEMENT_OPTIONS = [
    {
        "label": "追加全部数据条目",
        "value": "append_all",
        "description": "将底表中所有数据类条目追加到已有勘测表",
    },
    {
        "label": "跳过，不追加",
        "value": "skip",
        "description": "保持当前勘测表内容不变",
    },
]

_HITL_INPUT = {
    "id": "supplement_choice",
    "label": "是否向勘测表追加数据类条目？",
    "options": _SUPPLEMENT_OPTIONS,
}


def _get_survey_table(ctx: SkillContext) -> str | None:
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            path = json.loads(info_path.read_text(encoding="utf-8")).get("survey_table_path", "")
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
    tables = sorted(ctx.output_dir.glob("*全量勘测结果表*.xlsx")) if ctx.output_dir.exists() else []
    return str(tables[0]) if tables else None


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


class SupplementRunStep(BaseStep):
    key = "supplement_run"
    name = "补充勘测处理"
    artifacts_pattern = ["ProjectData/Output/*全量勘测结果表*.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        # 已有决策
        if ctx.project.get("supplement_choice"):
            return {"ok": True, "missing": []}

        # 需要勘测表已存在
        if _get_survey_table(ctx) is None:
            return {
                "ok": False,
                "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"],
                "note": "补充勘测需要已有全量勘测结果表（先完成 survey_work 生成表格）",
            }

        # 触发追加选择 HITL
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [_HITL_INPUT],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        choice = ctx.project.get("supplement_choice", "skip")
        survey_table_path = _get_survey_table(ctx)

        if choice == "skip":
            emit("[supplement_run] 跳过数据条目追加")
            return {"metrics": {"supplement_skipped": True, "supplement_count": 0}}

        if not survey_table_path:
            emit("[supplement_run] ⚠ 全量勘测结果表不存在，跳过")
            return {"metrics": {"supplement_skipped": True, "supplement_count": 0}}

        gen_cooling = _get_generation_cooling(ctx)
        if not gen_cooling:
            emit("[supplement_run] ⚠ generation_cooling 未知，跳过")
            return {"metrics": {"supplement_skipped": True, "supplement_count": 0}}

        from ..services.table_filter import load_base_table, get_available_data_keywords, filter_items
        from ..services.survey_table_builder import append_data_items
        from ..path_config import get_base_table_path

        base_table_path = get_base_table_path()
        if not os.path.exists(base_table_path):
            emit("[supplement_run] ⚠ 底表文件不存在，跳过")
            return {"metrics": {"supplement_skipped": True, "supplement_count": 0}}

        emit(f"[supplement_run] 加载底表: {os.path.basename(base_table_path)}")
        items = load_base_table(base_table_path)
        keywords = get_available_data_keywords(items, gen_cooling)

        if not keywords:
            emit(f"[supplement_run] {gen_cooling} 下无数据类条目，跳过")
            return {"metrics": {"supplement_count": 0}}

        emit(f"[supplement_run] 数据类关键词: {keywords}")

        try:
            data_items = filter_items(
                items,
                generation_cooling=gen_cooling,
                category="数据",
                data_keywords=keywords,
            )
        except Exception as e:
            emit(f"[supplement_run] ⚠ 过滤失败: {e}，跳过")
            return {"metrics": {"supplement_skipped": True, "supplement_count": 0}}

        total_rows = append_data_items(survey_table_path, data_items)
        count = len(data_items)
        emit(f"[supplement_run] ✓ 追加 {count} 条数据类条目（表格总行数: {total_rows}）")

        return {
            "metrics": {
                "supplement_count": count,
                "total_rows_after_supplement": total_rows,
            },
            "artifacts": [ctx.rel(survey_table_path)],
        }
