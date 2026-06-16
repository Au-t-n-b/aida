"""proposal_gen · assemble_service_maint"""
from __future__ import annotations

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths, resolve_project_id


class AssembleServiceMaintStep(BaseStep):
    key = "assemble_service_maint"
    name = "服务/维保组装（第8章）"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"ok": False, "missing": ["project_id"], "found": []}
        service = sorted(io.contract_service_boq_parse.glob("*.normalized.json"))
        if service:
            return {"ok": True, "missing": [], "found": [io.rel(p) for p in service]}
        return {
            "ok": True,
            "missing": [],
            "found": [],
            "note": "无服务 BOQ 解析结果，跳过",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        pid = resolve_project_id(ctx.project)
        if not pid:
            return {"error": "缺少 project_id"}

        from agent.proposal.assemblers.service_boq_assembler import assemble_service_content

        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"error": "路径解析失败"}

        if not list(io.contract_service_boq_parse.glob("*.normalized.json")):
            emit("无服务 BOQ，跳过第8章组装")
            return {"metrics": {"service_skipped": True}}

        emit("组装服务配置 …")
        rows = assemble_service_content(pid)
        emit(f"服务配置 {len(rows)} 行")
        return {
            "metrics": {"service_rows": len(rows), "service_skipped": False},
        }
