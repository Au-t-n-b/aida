"""Step 3 · 下发设备底表。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._sd_ops import _chain, op_plan_dispatch, slot_missing
from ._hitl import confirm_gate


class PlanDispatchStep(BaseStep):
    key = "plan_dispatch"
    name = "下发设备底表"
    artifacts_pattern = [
        "ProjectData/plan/Output/device_base_table.json",
        "ProjectData/plan/Output/dispatch_record.json",
    ]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        missing: list[str] = []
        if not _chain(ctx.work_root).get("step2_plan_split_at"):
            missing.append("ProjectData/plan/Output/third_level_tasks.json（需先 plan_split）")
        missing.extend(slot_missing(ctx.work_root, "lld_design"))
        if missing:
            return {"ok": False, "missing": missing, "found": [], "note": "需 LLD 设计 xlsx"}
        return confirm_gate(
            ctx.project,
            self.key,
            "确认下发设备底表",
            note="LLD 与三级计划已齐备，请确认生成设备底表。",
            description="将写入 device_base_table.json、dispatch_record.json 与设备完工清单宽表。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 下发设备底表…")
        proj_id = str((ctx.project or {}).get("project_id") or "nanobot-local")
        result = op_plan_dispatch(ctx.work_root, project_id=proj_id)
        if not result.get("ok"):
            return {"error": result.get("error") or "下发失败"}
        emit(f"[{self.key}] 设备底表 {result.get('device_rows', 0)} 行")
        return {
            "metrics": {
                "device_rows": result.get("device_rows", 0),
                "step": "dispatched",
                "scene_spec": result.get("scene_spec") or {},
                "device_tasks_preview": result.get("device_tasks_preview") or [],
                "device_stats": result.get("device_stats") or {},
            }
        }
