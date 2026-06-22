"""proposal_gen · assemble_device_table"""
from __future__ import annotations

import json

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths, resolve_project_id


class AssembleDeviceTableStep(BaseStep):
    key = "assemble_device_table"
    name = "组装设备信息表（第2章）"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"ok": False, "missing": ["project_id"], "found": []}
        if sorted(io.contract_boq_parse.glob("*.normalized.json")):
            return {"ok": True, "missing": [], "found": []}
        return {
            "ok": False,
            "missing": ["合同 BOQ normalized.json"],
            "found": [],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        pid = resolve_project_id(ctx.project)
        if not pid:
            return {"error": "缺少 project_id"}

        from agent.proposal.assemblers.device_boq_assembler import assemble_device_info

        emit("调用 device_boq_assembler …")
        rows = assemble_device_info(pid)
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"error": "路径解析失败"}

        draft_path = io.proposal_draft_json("2.设备配置信息.json")
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        rel = io.rel(draft_path)
        emit(f"设备信息表草稿 {rel}（{len(rows)} 行）")
        return {
            "artifacts": [rel],
            "files": {"device_table_draft": rel},
            "metrics": {"device_rows": len(rows)},
        }
