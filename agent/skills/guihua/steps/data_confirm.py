"""
data_confirm · 建模仿真第 2 步「数据确认」（确认型 HITL 门 · gate=data）

对应交互：用户点「设备数据准确」→ 左对话框「数据已确认，是否开始创建超节点」是/否。
机制同旧 device_confirm：check_inputs 检查 project.confirmations.data；未确认 → need_inputs
（ChoiceCard）软中断。confirm → apply_resume_payload 写 confirmations.data=True（full_restart
重跑保留），本步放行 → 进入 combo_create 创建超节点。
"""
from __future__ import annotations

from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..services.compat_table import _parse_combo_from_md

COMPAT_TABLE_REL = "ProjectData/RunTime/compat_table.md"


class DataConfirmStep(BaseStep):
    key = "data_confirm"
    name = "数据确认"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("data"):
            return {"ok": True, "missing": [], "found": ["confirmations.data"], "note": ""}

        combo = ""
        compat = ctx.work_root / COMPAT_TABLE_REL
        if compat.is_file():
            try:
                combo = _parse_combo_from_md(compat)
            except Exception:
                combo = ""
        combo_txt = f"（超节点组合：{combo}）" if combo else ""
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": f"请核对「设备数据」页签的设备适配信息表{combo_txt}，确认型号/板卡/数量无误后开始创建超节点。",
            "need_inputs": [{
                "id": "data",
                "label": "设备数据是否准确，开始创建超节点？",
                "options": [
                    {"label": "数据准确，创建超节点", "value": "confirm"},
                    {"label": "重新生成适配表", "value": "redo"},
                ],
            }],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 设备数据已确认，进入超节点创建")
        return {"metrics": {"data_confirmed": True}}
