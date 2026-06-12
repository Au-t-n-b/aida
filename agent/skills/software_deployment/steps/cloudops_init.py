"""Step 4 · CloudOps 初配。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._sd_ops import _chain, op_cloudops_init
from ._hitl import confirm_gate


class CloudopsInitStep(BaseStep):
    key = "cloudops_init"
    name = "CloudOps 初配"
    artifacts_pattern = ["ProjectData/plan/Output/CloudOps初始配置.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if not _chain(ctx.work_root).get("step3_plan_dispatch_at"):
            return {
                "ok": False,
                "missing": ["ProjectData/plan/Output/device_base_table.json（需先 plan_dispatch）"],
                "found": [],
                "note": "",
            }
        return confirm_gate(
            ctx.project,
            self.key,
            "确认生成 CloudOps 初配",
            note="设备底表已就绪，请确认生成 CloudOps 初始配置。",
            description="将读取 LLD/设备底表并生成 CloudOps初始配置.xlsx。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 生成 CloudOps 初始配置…")
        proj_id = str((ctx.project or {}).get("project_id") or "nanobot-local")
        result = op_cloudops_init(ctx.work_root, project_id=proj_id)
        if not result.get("ok"):
            for line in result.get("logs") or []:
                emit(f"  {line}")
            return {"error": result.get("error") or "CloudOps 初配失败"}
        emit(f"[{self.key}] 已生成（{result.get('output_bytes', 0)} 字节）")
        return {"metrics": {"cloudops_init_bytes": result.get("output_bytes", 0)}}
