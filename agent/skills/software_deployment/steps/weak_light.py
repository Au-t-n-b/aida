"""Step 11 · 服务器弱光检查（init_install / weak_light）。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._commission import commission_check, commission_run


class WeakLightStep(BaseStep):
    key = "weak_light"
    name = "服务器弱光检查"
    artifacts_pattern = ["ProjectData/results/weak_light"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return commission_check(
            ctx,
            self.key,
            "确认执行服务器弱光检查",
            "将通过 task_runner 下发 weak_light 命令（init_install）。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        return commission_run(ctx, emit, self.key, "weak_light")
