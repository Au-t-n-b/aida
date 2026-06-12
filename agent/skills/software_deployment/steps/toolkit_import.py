"""Step 8 · 导入 Toolkit 配置。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._sd_ops import _chain, op_toolkit_import
from ._hitl import confirm_gate


class ToolkitImportStep(BaseStep):
    key = "toolkit_import"
    name = "导入 Toolkit"
    artifacts_pattern = ["ProjectData/plan/RunTime/toolkit_import.json"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        missing: list[str] = []
        if not _chain(ctx.work_root).get("step7_executor_config_at"):
            missing.append("ProjectData/plan/RunTime/toolkit_executor.json（需先 toolkit_executor）")
        if not _chain(ctx.work_root).get("step6_cloudops_full_at"):
            missing.append("ProjectData/plan/Output/CloudOps完整配置文件.xlsx")
        if missing:
            return {"ok": False, "missing": missing, "found": [], "note": ""}
        return confirm_gate(
            ctx.project,
            self.key,
            "确认导入 Toolkit",
            note="完整配置与执行机已就绪，请确认导入 Toolkit。",
            description="将上传 CloudOps完整配置文件.xlsx，并用最新完工清单刷新底表初始化状态。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 导入 Toolkit…")
        result = op_toolkit_import(ctx.work_root)
        if not result.get("ok"):
            for line in result.get("logs") or []:
                emit(f"  {line}")
            return {"error": result.get("error") or "Toolkit 导入失败"}
        emit(f"[{self.key}] {result.get('message', '导入完成')}")
        return {
            "metrics": {
                "toolkit_imported": True,
                "refreshed_rows": result.get("refreshed_rows", 0),
                "refreshed_devices": result.get("refreshed_devices", 0),
            }
        }
