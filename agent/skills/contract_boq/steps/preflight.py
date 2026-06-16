"""contract_boq · preflight"""
from __future__ import annotations

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import clone_boq_skill_root, resolve_early_io_paths


class PreflightStep(BaseStep):
    key = "preflight"
    name = "环境预检"
    internal = True

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": [], "found": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        io = resolve_early_io_paths(ctx.project)
        lines: list[str] = []
        if io is None:
            lines.append("⚠ 未解析 project_id")
        else:
            lines.append(f"项目根: {io.project_root}")
            io.contract_boq_upload.mkdir(parents=True, exist_ok=True)
            io.contract_boq_parse.mkdir(parents=True, exist_ok=True)
            lines.append(f"BOQ 输入目录: {io.contract_boq_upload}")
            lines.append(f"解析落盘: {io.contract_boq_parse}")
        uniex = clone_boq_skill_root()
        lines.append(f"uniEx clone-boq: {'可用 ' + str(uniex) if uniex else '未配置 UNIEX_BENCH_ROOT'}")
        emit("\n".join(lines))
        return {
            "logs": lines,
            "metrics": {"preflight_ok": io is not None, "uniex_available": uniex is not None},
        }
