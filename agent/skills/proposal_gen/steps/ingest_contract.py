"""proposal_gen · ingest_contract"""
from __future__ import annotations

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths


class IngestContractStep(BaseStep):
    key = "ingest_contract"
    name = "读取合同 BOQ 解析结果"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"ok": False, "missing": ["project_id"], "found": []}
        files = sorted(io.contract_boq_parse.glob("*.normalized.json"))
        if not files:
            return {
                "ok": False,
                "missing": ["早期介入/合同/解析结果/BOQ设备解析原始结果/*.normalized.json"],
                "found": [],
                "note": "请先运行 contract_boq Skill 或手工落盘 BOQ 解析结果",
            }
        return {"ok": True, "missing": [], "found": [io.rel(p) for p in files]}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"error": "缺少 project_id"}
        files = sorted(io.contract_boq_parse.glob("*.normalized.json"))
        rels = [io.rel(p) for p in files]
        emit(f"已接入 {len(rels)} 份合同 normalized.json（只读）")
        return {
            "artifacts": rels,
            "files": {"contract_normalized_json": rels},
            "metrics": {"normalized_count": len(rels)},
        }
