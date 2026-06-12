"""Step 5 · CloudOps 手工补充登记。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._sd_ops import _chain, op_cloudops_supplement, slot_missing
from ._hitl import confirm_gate


class CloudopsSupplementStep(BaseStep):
    key = "cloudops_supplement"
    name = "CloudOps 补充"
    artifacts_pattern = ["ProjectData/plan/Output/CloudOps配置_手工补充.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        missing: list[str] = []
        if not _chain(ctx.work_root).get("step4_cloudops_init_at"):
            missing.append("ProjectData/plan/Output/CloudOps初始配置.xlsx（需先 cloudops_init）")
        missing.extend(slot_missing(ctx.work_root, "cloudops_manual"))
        if missing:
            return {"ok": False, "missing": missing, "found": [], "note": "需 CloudOps 手工补充表"}
        return confirm_gate(
            ctx.project,
            self.key,
            "确认登记 CloudOps 补充",
            note="手工补充表已就绪，请确认登记步骤 5。",
            description="将记录手工补充表路径，并探测是否已有设备安装完工清单。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 登记 CloudOps 手工补充…")
        result = op_cloudops_supplement(ctx.work_root)
        if not result.get("ok"):
            return {"error": result.get("error") or "补充登记失败"}
        emit(f"[{self.key}] 手工表：{result.get('manual_path', '')}")
        return {
            "metrics": {
                "checklist_present": bool(result.get("checklist_present")),
                "manual_path": result.get("manual_path", ""),
            }
        }
