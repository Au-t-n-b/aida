"""contract_boq · publish_outputs"""
from __future__ import annotations

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths


class PublishOutputsStep(BaseStep):
    key = "publish_outputs"
    name = "登记合同解析产物"
    internal = True

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": [], "found": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"error": "缺少 project_id"}

        normalized = [io.rel(p) for p in sorted(io.contract_boq_parse.glob("*.normalized.json"))]
        files: dict[str, object] = {
            "contract_boq_parse_dir": io.rel(io.contract_boq_parse),
            "normalized_json": normalized,
        }
        if io.contract_simulation_md.is_file():
            files["simulation_device_md"] = io.rel(io.contract_simulation_md)

        emit(f"合同解析产物已登记：normalized={len(normalized)}")
        return {
            "files": files,
            "metrics": {"normalized_count": len(normalized)},
            "overall_progress": 100,
        }
