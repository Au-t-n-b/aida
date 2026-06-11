"""
data_append · 数据条目追加

意图: survey_work 专属

流程:
  1. HITL ChoiceCard 询问用户是否追加数据类条目（追加全部 / 跳过）
  2. 若追加：加载底表 → 按 generation_cooling 过滤分类=数据 → append_data_items()
  3. 返回追加数量 metrics
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip

_APPEND_OPTIONS = [
    {
        "label": "追加全部数据条目",
        "value": "append_all",
        "description": "将底表中所有数据类（布线仿真/设备上架评估等）条目追加到勘测表",
    },
    {
        "label": "跳过，不追加",
        "value": "skip",
        "description": "保持当前勘测表内容不变，直接进入下一步",
    },
]

_HITL_INPUT = {
    "id": "data_append_choice",
    "label": "是否追加数据类勘测条目？",
    "options": _APPEND_OPTIONS,
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


def _already_appended(ctx: SkillContext) -> bool:
    """幂等标记：本 run 是否已追加过数据条目（防 full_restart 重放重复追加）。"""
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            return bool(json.loads(info_path.read_text(encoding="utf-8")).get("data_append_done"))
        except Exception:
            pass
    return False


def _mark_appended(ctx: SkillContext, count: int) -> None:
    info_path = ctx.runtime_dir / "project_info.json"
    try:
        existing = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    except Exception:
        existing = {}
    existing["data_append_done"] = True
    existing["data_append_count"] = count
    ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
    info_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


class DataAppendStep(BaseStep):
    key = "data_append"
    name = "数据条目追加"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        # 已经做过追加决策（HITL 完成后 apply_resume_payload 写入）
        if ctx.project.get("data_append_choice"):
            return {"ok": True, "missing": []}

        # 触发 ChoiceCard HITL
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [_HITL_INPUT],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        choice = ctx.project.get("data_append_choice", "skip")

        if choice == "skip":
            emit("[data_append] 跳过数据条目追加")
            return {"metrics": {"data_append_skipped": True, "data_append_count": 0}}

        # 幂等：full_restart 重放本步时若已追加过则跳过，否则数据行会累积翻倍
        if _already_appended(ctx):
            emit("[data_append] ✓ 数据条目已追加过（幂等跳过，避免重复行）")
            return {"metrics": {"data_append_idempotent_skip": True}}

        # choice == "append_all"
        survey_table_path = _get_survey_table(ctx)
        if not survey_table_path:
            emit("[data_append] ⚠ 全量勘测结果表不存在，跳过追加")
            return {"metrics": {"data_append_skipped": True, "data_append_count": 0}}

        gen_cooling = _get_generation_cooling(ctx)
        if not gen_cooling:
            emit("[data_append] ⚠ generation_cooling 未知，跳过追加")
            return {"metrics": {"data_append_skipped": True, "data_append_count": 0}}

        from ..services.table_filter import (
            load_base_table,
            get_available_data_keywords,
            filter_items,
        )
        from ..services.survey_table_builder import append_data_items
        from ..path_config import get_base_table_path

        base_table_path = get_base_table_path()
        if not os.path.exists(base_table_path):
            emit("[data_append] ⚠ 底表文件不存在，跳过追加")
            return {"metrics": {"data_append_skipped": True, "data_append_count": 0}}

        emit(f"[data_append] 加载底表: {os.path.basename(base_table_path)}")
        items = load_base_table(base_table_path)

        keywords = get_available_data_keywords(items, gen_cooling)
        if not keywords:
            emit(f"[data_append] {gen_cooling} 下无数据类条目，跳过")
            return {"metrics": {"data_append_count": 0}}

        emit(f"[data_append] 数据类关键词: {keywords}")

        try:
            data_items = filter_items(
                items,
                generation_cooling=gen_cooling,
                category="数据",
                data_keywords=keywords,
            )
        except Exception as e:
            emit(f"[data_append] ⚠ 过滤失败: {e}，跳过")
            return {"metrics": {"data_append_skipped": True, "data_append_count": 0}}

        total_rows = append_data_items(survey_table_path, data_items)
        count = len(data_items)
        _mark_appended(ctx, count)
        emit(f"[data_append] ✓ 追加 {count} 条数据类条目（表格总行数: {total_rows}）")

        return {
            "metrics": {
                "data_append_count": count,
                "total_rows_after_append": total_rows,
            }
        }
