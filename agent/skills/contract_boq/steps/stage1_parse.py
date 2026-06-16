"""contract_boq · stage1_parse"""
from __future__ import annotations

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths
from ..bridge import UniExBoqError, run_stage1


class Stage1ParseStep(BaseStep):
    key = "stage1_parse"
    name = "BOQ Stage1 解析"
    artifacts_pattern = ["早期介入/合同/解析结果/BOQ设备解析原始结果/*.normalized.json"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"ok": False, "missing": ["project_id"], "found": []}
        existing = sorted(io.contract_boq_parse.glob("*.normalized.json"))
        if existing:
            return {"ok": True, "missing": [], "found": [io.rel(p) for p in existing]}
        boq = sorted(io.contract_boq_upload.glob("*.xlsx"))
        if not boq:
            return {"ok": False, "missing": ["BOQ xlsx"], "found": []}
        return {"ok": True, "missing": [], "found": [io.rel(p) for p in boq]}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"error": "缺少 project_id"}

        existing = sorted(io.contract_boq_parse.glob("*.normalized.json"))
        if existing:
            rels = [io.rel(p) for p in existing]
            emit(f"跳过 Stage1：已有 {len(rels)} 份 normalized.json")
            return {
                "artifacts": rels,
                "files": {"normalized_json": rels},
                "metrics": {"normalized_count": len(rels), "stage1_skipped": True},
            }

        try:
            emit("调用 uniEx clone-boq Stage1 …")
            run_dir = run_stage1(io.contract_boq_upload, io.contract_boq_parse, project_id=io.project_id)
        except UniExBoqError as exc:
            return {"error": str(exc)}

        produced = sorted(io.contract_boq_parse.glob("*.normalized.json"))
        rels = [io.rel(p) for p in produced]
        emit(f"Stage1 完成：{len(rels)} 份 normalized.json")
        return {
            "artifacts": rels,
            "files": {"normalized_json": rels, "clone_boq_run_dir": str(run_dir)},
            "metrics": {"normalized_count": len(rels), "stage1_skipped": False},
        }
