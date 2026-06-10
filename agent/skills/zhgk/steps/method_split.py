"""
method_split · 勘测方法分流

意图: survey_work 专属

将全量勘测结果表按「勘测方法」列分组，统计各方法条目数，
结果写入 RunTime/project_info.json["method_groups"]。

无 HITL，纯统计分析。
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip


def _get_survey_table(ctx: SkillContext) -> str | None:
    """找到全量勘测结果表：优先 project_info.json，退而 glob"""
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


class MethodSplitStep(BaseStep):
    key = "method_split"
    name = "勘测方法分流"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if _get_survey_table(ctx) is None:
            return {"ok": False, "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"]}
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        from ..services.survey_table_builder import read_survey_table

        survey_table_path = _get_survey_table(ctx)
        if not survey_table_path:
            raise RuntimeError("method_split: 全量勘测结果表不存在")

        emit(f"[method_split] 读取: {os.path.basename(survey_table_path)}")
        rows = read_survey_table(survey_table_path)

        groups: dict[str, int] = defaultdict(int)
        for row in rows:
            method = row.get("勘测方法") or "未知"
            groups[method] += 1

        total = len(rows)
        emit(f"[method_split] 总条目: {total}")
        for method, count in sorted(groups.items()):
            emit(f"[method_split]   {method}: {count} 条")

        # 写统计到 project_info.json
        info_path = ctx.runtime_dir / "project_info.json"
        try:
            existing = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
        except Exception:
            existing = {}
        existing["method_groups"] = dict(groups)
        existing["total_items"] = total
        ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
        info_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

        emit(f"[method_split] ✓ 分流完成，{len(groups)} 种勘测方法")

        return {
            "metrics": {
                "total_items": total,
                "method_groups": dict(groups),
            }
        }
