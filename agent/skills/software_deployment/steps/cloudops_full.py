"""Step 6 · CloudOps 完整配置。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._sd_ops import _chain, op_cloudops_full, op_cloudops_material_check, slot_missing
from ._hitl import confirm_gate


class CloudopsFullStep(BaseStep):
    key = "cloudops_full"
    name = "CloudOps 完整配置"
    artifacts_pattern = ["ProjectData/plan/Output/CloudOps完整配置文件.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        missing: list[str] = []
        if not _chain(ctx.work_root).get("step5_cloudops_supplement_at"):
            missing.append("CloudOps 手工补充表（需先 cloudops_supplement）")
        missing.extend(slot_missing(ctx.work_root, "check_list"))
        if missing:
            return {"ok": False, "missing": missing, "found": [], "note": "需手工补充表与设备安装完工清单"}
        return confirm_gate(
            ctx.project,
            self.key,
            "确认生成 CloudOps 完整配置",
            note="材料已齐备，请确认生成完整配置文件。",
            description="将合并 input/cloudops 中所有完工清单，生成全量 CloudOps完整配置文件.xlsx。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 生成 CloudOps 完整配置…")
        result = op_cloudops_full(ctx.work_root)
        if not result.get("ok"):
            for line in result.get("logs") or []:
                emit(f"  {line}")
            return {"error": result.get("error") or "完整配置失败"}
        emit(f"[{self.key}] {result.get('message', '完成')}")
        emit(f"[{self.key}] 执行步骤 6b 材料检查（ZTP / 测试参数，不阻塞后续步骤）…")
        material = op_cloudops_material_check(ctx.work_root)
        if material.get("ok"):
            emit(f"  ZTP：{material.get('ztp_message', '')}")
            emit(f"  测试参数：{material.get('params_message', '')}")
        return {
            "metrics": {
                "cloudops_full": True,
                "cloudops_full_bytes": result.get("output_bytes", 0),
                "cloudops_server_rows": result.get("server_rows", 0),
                "cloudops_switch_rows": result.get("switch_rows", 0),
                "ztp_present": bool(material.get("ztp_present")),
                "params_present": bool(material.get("params_present")),
                "requires_ztp": bool(material.get("requires_ztp")),
            }
        }
