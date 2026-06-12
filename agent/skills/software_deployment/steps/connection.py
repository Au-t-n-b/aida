"""Step 9 · 服务器连线检查（init_install / connection）。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._commission import commission_check, commission_run


class ConnectionStep(BaseStep):
    key = "connection"
    name = "服务器连线检查"
    artifacts_pattern = ["ProjectData/results/connection"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return commission_check(
            ctx,
            self.key,
            "确认执行服务器连线检查",
            "将通过 task_runner 下发 connection 命令（init_install）。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        return commission_run(ctx, emit, self.key, "connection")
