"""
assess · AI 五值评估

意图: survey_work / report_gen

流程:
  1. 找到全量勘测结果表
  2. evaluate_all() — LLM 批量评估每条勘测项（检查内容 + 最新检查结果 → 五值结论）
  3. get_assessment_statistics() — 统计各五值数量
  4. 返回 metrics（五值统计 + 评估总数）
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip


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


class AssessStep(BaseStep):
    key = "assess"
    name = "AI 五值评估"
    artifacts_pattern = ["ProjectData/Output/*全量勘测结果表*.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if _get_survey_table(ctx) is None:
            return {"ok": False, "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"]}
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        from ..services.assessment_engine import evaluate_all, get_assessment_statistics
        from ..services._llm_adapter import make_llm_adapter

        survey_table = _get_survey_table(ctx)
        if not survey_table:
            raise RuntimeError("assess: 全量勘测结果表不存在")

        emit(f"[assess] 开始 AI 五值评估: {os.path.basename(survey_table)}")
        llm = make_llm_adapter(ctx, step_key=self.key)

        results = evaluate_all(survey_table, llm)
        total = len(results)
        emit(f"[assess] 评估完成: {total} 条")

        stats = get_assessment_statistics(survey_table)
        emit(
            f"[assess] 统计: "
            f"满足={stats.get('满足', 0)} / 不满足={stats.get('不满足', 0)} / "
            f"不涉及={stats.get('不涉及', 0)} / 未勘测={stats.get('未勘测', 0)} / "
            f"无法识别={stats.get('无法识别', 0)}"
        )

        return {
            "metrics": {
                "assess_total": total,
                **{f"assess_{k}": v for k, v in stats.items()},
            },
            "artifacts": [ctx.rel(survey_table)],
        }
