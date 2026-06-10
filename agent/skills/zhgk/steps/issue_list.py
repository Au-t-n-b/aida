"""
issue_list · 问题清单生成

意图: survey_work / report_gen

流程:
  1. 找全量勘测结果表（需已完成 assess）
  2. build_issue_list() — 筛「不满足」「无法识别」，LLM 生成问题描述 + 整改建议
  3. 写入 Output/{activity_id}_{project_name}_{room_name}_问题清单表.xlsx
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


class IssueListStep(BaseStep):
    key = "issue_list"
    name = "问题清单生成"
    artifacts_pattern = ["ProjectData/Output/*问题清单表*.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if _get_survey_table(ctx) is None:
            return {"ok": False, "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"]}
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        from ..services.issue_list_builder import build_issue_list
        from ..services._llm_adapter import make_llm_adapter

        survey_table = _get_survey_table(ctx)
        if not survey_table:
            raise RuntimeError("issue_list: 全量勘测结果表不存在")

        proj = ctx.project
        emit(f"[issue_list] 生成问题清单: {os.path.basename(survey_table)}")
        llm = make_llm_adapter(ctx, step_key=self.key)

        issue_list_path, issue_rows = build_issue_list(
            survey_table_path=survey_table,
            output_dir=str(ctx.output_dir),
            activity_id=proj.get("activity_id", ""),
            project_name=proj.get("project_name", ""),
            room_name=proj.get("room_name", ""),
            llm_call=llm,
        )

        emit(f"[issue_list] ✓ 问题清单: {os.path.basename(issue_list_path)}（{len(issue_rows)} 条）")

        return {
            "metrics": {
                "issue_list_path": issue_list_path,
                "issue_count": len(issue_rows),
                # 仅前 10 条进 metrics（SDUI 问题清单 Table 预览）
                "issue_rows": issue_rows[:10],
            },
            "artifacts": [ctx.rel(issue_list_path)],
        }
