"""
step · 输入执行计划（确认型 HITL 门 · 对齐设计稿 next_stage）

对齐《系统设计工作台-周二版》：完整 LLD 融合完成后，弹出「输入执行计划」让用户选择
下一步——「设备名称替换（可选）+ ZTP 开局」或「跳过名称替换，直接生成 ZTP」。

机制：在 run() 内读 project.stage.chosen；未选择 → 返回 hitl(need_inputs · ChoiceCard)。
用户在 resume 选定 → apply_resume_payload 把 project.stage = {chosen:True, naming:bool} 写回
（full_restart 重跑保留）。下游 naming_replace 据 stage.naming 决定执行 / 跳过。

⚠️ single/batch 菜单式模式不经此门（plane_planning 已 route_to=publish 直接跳过本节点）。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from agent.sdui.projector_base import collect_metrics


class StageSelectStep(BaseStep):
    key = "stage_select"
    name = "输入执行计划"

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        from ..pipelines.delivery import should_skip_step

        route = str(state.get("route_to") or "")
        if route and should_skip_step(self.key, route):
            stage = (ctx.project or {}).get("stage") or {}
            emit(f"[{self.key}] 交付续跑 · 跳过（→{route}）")
            return {
                "logs": [f"[stage_select] 交付续跑跳过（→{route}）"],
                "metrics": {
                    "stage_chosen": bool(stage.get("chosen")),
                    "stage_naming": bool(stage.get("naming")),
                },
            }

        m = collect_metrics(state)
        # 安全兜底：菜单式模式不应到达此节点（route_to 已跳过），到达则放行不阻断
        if m.get("sd_mode") in ("single", "batch"):
            return {"logs": ["[stage_select] 菜单式模式，跳过执行计划选择"],
                    "metrics": {"stage_chosen": True, "stage_naming": False}}

        stage = (ctx.project or {}).get("stage") or {}
        if stage.get("chosen"):
            naming = bool(stage.get("naming"))
            emit(f"[{self.key}] 执行计划已选择：{'设备名称替换 + ZTP' if naming else '跳过名称替换 · 直接 ZTP'}")
            return {
                "logs": [f"[stage_select] 已选择：naming={naming}"],
                "metrics": {"stage_chosen": True, "stage_naming": naming},
            }

        emit(f"[{self.key}] ⏸ 等待选择执行计划（设备名称替换 / 直接 ZTP）")
        return {
            "current_step": self.key,
            "steps": [self.make_record(
                "hitl", ended_at=self._now(),
                log_tail=[f"[{self.key}] 等待选择下一步执行计划"],
                metrics={"stage_chosen": False},
            )],
            "logs": ["[stage_select] 等待选择下一步执行计划"],
            "metrics": {"stage_chosen": False},
            "hitl": {
                "step": self.key,
                "reason": (
                    "完整 LLD 设计已融合完成。请选择下一步执行计划：\n"
                    "· 设备名称替换（可选）：把规划设备名替换为现网命名，再生成 ZTP；\n"
                    "· 直接 ZTP：跳过名称替换，保留规划设备名直接生成开局文件。"
                ),
                "need_files": [],
                "need_inputs": [{
                    "id": "stage",
                    "label": "选择下一步执行计划",
                    "options": [
                        {"label": "设备名称替换 + 生成 ZTP 开局文件", "value": "rename_ztp"},
                        {"label": "跳过名称替换，直接生成 ZTP", "value": "skip_ztp"},
                    ],
                }],
            },
        }
