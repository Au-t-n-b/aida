"""Step 1 · 接收二级任务。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._sd_ops import op_plan_receive, slot_missing
from ._hitl import confirm_gate


class PlanReceiveStep(BaseStep):
    key = "plan_receive"
    name = "接收二级任务"
    artifacts_pattern = ["ProjectData/plan/Input/second_level_tasks.json"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        missing = slot_missing(ctx.work_root, "second_level_tasks")
        if not missing:
            return confirm_gate(
                ctx.project,
                self.key,
                "确认接收二级任务",
                note="已检测到二级任务材料，请确认沿用当前材料并接收。",
                description="将读取 ProjectData/input/plan_receive 并写入 plan/Input/second_level_tasks.json。",
            )
        return {
            "ok": False,
            "missing": missing,
            "found": [],
            "note": "请将「部署调测任务列表.xlsx」放入 ProjectData/input/plan_receive/",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 接收二级任务…")
        result = op_plan_receive(ctx.work_root, prefer_inbox=True)
        if not result.get("ok"):
            return {"error": result.get("error") or "接收失败"}
        emit(f"[{self.key}] 已接收 {result.get('count', 0)} 条 → plan/Input/second_level_tasks.json")
        return {"metrics": {"task_count": result.get("count", 0), "step": "received"}}
