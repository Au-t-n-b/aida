"""Step 10 · 灵衢连线检查（init_install / lq_connection）。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._commission import commission_check, commission_run


class LqConnectionStep(BaseStep):
    key = "lq_connection"
    name = "灵衢连线检查"
    artifacts_pattern = ["ProjectData/results/lq_connection"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return commission_check(
            ctx,
            self.key,
            "确认执行灵衢连线检查",
            "将通过 task_runner 下发 lq_connection 命令（init_install）。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        return commission_run(ctx, emit, self.key, "lq_connection")
