"""
topo_confirm · 第 4 步「拓扑确认」（确认型 HITL 门）

同 device_confirm 模式，门控 project.confirmations.topo。
用户复核节点/链路/分组后放行最后的拓扑连接。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult


class TopoConfirmStep(BaseStep):
    key = "topo_confirm"
    name = "拓扑确认"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("topo"):
            return {"ok": True, "missing": [], "found": ["confirmations.topo"], "note": ""}
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": "请核对拓扑结构（节点、链路、母线/机柜分组）是否符合设计意图。",
            "need_inputs": [{
                "id": "topo",
                "label": "确认拓扑结构",
                "options": [
                    {"label": "拓扑正确，完成连接", "value": "confirm"},
                    {"label": "回退重看", "value": "redo"},
                ],
            }],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 拓扑已确认，进入拓扑连接")
        return {"metrics": {"topo_confirmed": True}}
