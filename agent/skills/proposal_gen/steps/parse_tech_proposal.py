"""proposal_gen · parse_tech_proposal"""
from __future__ import annotations

import json
from pathlib import Path

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths


class ParseTechProposalStep(BaseStep):
    key = "parse_tech_proposal"
    name = "技术建议书 → 验收策略"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"ok": False, "missing": ["project_id"], "found": []}
        io.proposal_tech_proposal_in.mkdir(parents=True, exist_ok=True)
        docx = sorted(io.proposal_tech_proposal_in.glob("*.docx"))
        if docx:
            return {"ok": True, "missing": [], "found": [io.rel(p) for p in docx]}
        return {
            "ok": False,
            "missing": ["早期介入/交付预案/输入文件/技术建议书/*.docx"],
            "found": [],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"error": "缺少 project_id"}

        io.proposal_tech_proposal_parse.mkdir(parents=True, exist_ok=True)
        docx_files = sorted(io.proposal_tech_proposal_in.glob("*.docx"))
        if not docx_files:
            return {
                "hitl": {
                    "step": self.key,
                    "reason": "请上传技术建议书 docx",
                    "need_files": ["早期介入/交付预案/输入文件/技术建议书/*.docx"],
                },
            }

        from agent.services.officecli_parse import parse_acceptance_via_officecli

        src = docx_files[0]
        emit(f"解析 {src.name} …")
        rows = parse_acceptance_via_officecli(src)
        out_json = io.proposal_tech_proposal_parse / f"{src.stem}-验收表.json"
        out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        rel = io.rel(out_json)
        emit(f"产出 {rel}（{len(rows)} 条验收项）")
        return {
            "artifacts": [rel],
            "files": {"acceptance_parse_json": rel},
            "metrics": {"acceptance_rows": len(rows)},
        }
