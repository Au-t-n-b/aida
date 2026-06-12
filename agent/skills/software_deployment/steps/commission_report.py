"""Step 13 · 调测报告汇总。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._sd_ops import _chain, op_commission_report
from ._hitl import confirm_gate


class CommissionReportStep(BaseStep):
    key = "commission_report"
    name = "调测报告汇总"
    artifacts_pattern = [
        "ProjectData/results/调测报告汇总_latest.xlsx",
    ]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if not _chain(ctx.work_root).get("step9_init_install_at"):
            return {
                "ok": False,
                "missing": ["init_install 四条命令未完成（需先 hccs_weak_light）"],
                "found": [],
                "note": "",
            }
        return confirm_gate(
            ctx.project,
            self.key,
            "确认生成调测报告",
            note="四条 init_install 检查已完成，请确认生成报告汇总。",
            description="将汇总 connection / lq_connection / weak_light / hccs_weak_light 结果。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 生成调测报告…")
        result = op_commission_report(ctx.work_root)
        if not result.get("ok"):
            return {"error": result.get("error") or "报告生成失败"}
        emit(f"[{self.key}] {result.get('message', '完成')}")
        if result.get("report_path"):
            emit(f"  报告：{result.get('report_path')}")
        from ..sdui import SD_STEP_ORDER

        try:
            pct = int(100 * (SD_STEP_ORDER.index(self.key) + 1) / len(SD_STEP_ORDER))
        except ValueError:
            pct = 100

        return {
            "current_step": self.key,
            "overall_progress": pct,
            "metrics": {
                "report_generated": True,
                "report_path": result.get("report_path", ""),
                "report_name": result.get("report_name", ""),
                "tested_commands": result.get("tested_commands", 0),
                "total_commands": result.get("total_commands", 4),
                "untested_commands": result.get("untested_commands", 0),
                "detail_sheets": result.get("detail_sheets", 0),
            },
        }
