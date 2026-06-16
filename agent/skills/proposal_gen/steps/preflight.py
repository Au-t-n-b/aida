"""proposal_gen · preflight"""
from __future__ import annotations

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths


class PreflightStep(BaseStep):
    key = "preflight"
    name = "环境预检"
    internal = True

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": [], "found": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        io = resolve_early_io_paths(ctx.project)
        lines: list[str] = []
        n = 0
        if io is None:
            lines.append("⚠ 未解析 project_id")
        else:
            n = len(list(io.contract_boq_parse.glob("*.normalized.json")))
            lines.append(f"合同 BOQ 解析产物: {n} 份 normalized.json")
            lines.append(f"交付预案输出目录: {io.proposal_device_table_out.parent}")
        emit("\n".join(lines))
        return {"logs": lines, "metrics": {"contract_ready": n > 0 if io else False}}
