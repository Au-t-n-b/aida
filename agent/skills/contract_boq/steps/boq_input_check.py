"""contract_boq · boq_input_check"""
from __future__ import annotations

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths


class BoqInputCheckStep(BaseStep):
    key = "boq_input_check"
    name = "BOQ 输入检查"
    artifacts_pattern = ["早期介入/合同/输入文件/BOQ/*.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"ok": False, "missing": ["project_id"], "found": []}
        io.contract_boq_upload.mkdir(parents=True, exist_ok=True)
        boq_files = sorted(io.contract_boq_upload.glob("*.xlsx"))
        if boq_files:
            return {
                "ok": True,
                "missing": [],
                "found": [io.rel(f) for f in boq_files],
            }
        return {
            "ok": False,
            "missing": ["早期介入/合同/输入文件/BOQ/*.xlsx"],
            "found": [],
            "note": "请上传 BOQ xlsx 到合同模块输入目录",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        check = self.check_inputs(ctx)
        if not check.get("ok"):
            return {
                "hitl": {
                    "step": self.key,
                    "reason": "缺少 BOQ 输入文件",
                    "need_files": list(check.get("missing") or []),
                },
            }
        found = check.get("found") or []
        emit(f"已检测到 {len(found)} 份 BOQ")
        return {
            "artifacts": found,
            "files": {"boq_inputs": found},
            "metrics": {"boq_count": len(found)},
        }
