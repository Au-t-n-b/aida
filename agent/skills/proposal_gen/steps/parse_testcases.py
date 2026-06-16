"""proposal_gen · parse_testcases"""
from __future__ import annotations

import json

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths


class ParseTestcasesStep(BaseStep):
    key = "parse_testcases"
    name = "测试用例结构化"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"ok": False, "missing": ["project_id"], "found": []}
        io.proposal_testcases_in.mkdir(parents=True, exist_ok=True)
        for pattern in ("*.docx", "*.xlsx"):
            hits = sorted(io.proposal_testcases_in.glob(pattern))
            if hits:
                return {"ok": True, "missing": [], "found": [io.rel(p) for p in hits]}
        return {
            "ok": False,
            "missing": ["早期介入/交付预案/输入文件/测试用例/*"],
            "found": [],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"error": "缺少 project_id"}

        io.proposal_testcase_parse.mkdir(parents=True, exist_ok=True)
        candidates = sorted(io.proposal_testcases_in.glob("*.docx")) + sorted(
            io.proposal_testcases_in.glob("*.xlsx")
        )
        if not candidates:
            return {
                "hitl": {
                    "step": self.key,
                    "reason": "请上传测试用例 docx/xlsx",
                    "need_files": ["早期介入/交付预案/输入文件/测试用例/*"],
                },
            }

        from agent.services.officecli_parse import parse_testcases_via_officecli

        src = candidates[0]
        emit(f"解析 {src.name} …")
        cases = parse_testcases_via_officecli(src)
        out_json = io.proposal_testcase_parse / f"{src.stem}-测试用例.json"
        out_json.write_text(
            json.dumps({"cases": cases}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rel = io.rel(out_json)
        emit(f"产出 {rel}（{len(cases)} 条用例）")
        return {
            "artifacts": [rel],
            "files": {"testcase_parse_json": rel},
            "metrics": {"testcase_count": len(cases)},
        }
