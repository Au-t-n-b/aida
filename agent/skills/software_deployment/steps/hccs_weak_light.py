"""Step 12 · 灵衢光链路检查（init_install / hccs_weak_light）。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._commission import commission_check, commission_run


class HccsWeakLightStep(BaseStep):
    key = "hccs_weak_light"
    name = "灵衢光链路检查"
    artifacts_pattern = ["ProjectData/results/hccs_weak_light"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return commission_check(
            ctx,
            self.key,
            "确认执行灵衢光链路检查",
            "将通过 task_runner 下发 hccs_weak_light 命令（init_install）。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        return commission_run(
            ctx,
            emit,
            self.key,
            "hccs_weak_light",
            mark_init_install_complete=True,
        )
