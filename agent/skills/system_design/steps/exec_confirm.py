"""
step · 确认执行计划（确认型 HITL 门 · 对齐设计稿 confirm_request）

对齐《系统设计工作台-周二版》：用户输入指令并经意图识别后，弹出 confirm_request 确认卡；
将读取的输入件 + 将生成的产物展示给用户，确认后才进入平面规划 / LLD 融合。

机制：在 run() 内读 project.confirmations.exec；未确认 → 返回 hitl(need_inputs · ChoiceCard)，
execute_step 据此软中断。用户在 resume 选「确认执行」→ apply_resume_payload 把
confirmations.exec 写进 project（full_restart 重跑保留），本步放行进入平面规划。

⚠️ 完全不使用设计稿 mock：命令读自 intent_recognition 真实写入的 metrics.intent_command，
已就绪输入件读自 input_check 写入的 found_tags / state.files（无任何写死文件名）。
"""
from __future__ import annotations

import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from agent.sdui.projector_base import collect_metrics
from ..pipelines.inputs import FILE_CONFIG, label_of


# intent_command → 将读取 / 将生成（用户视角，对齐设计稿 confirm_request inputs/outputs 语义）
def _expected_io(intent_command: str, state: SkillState | None = None) -> tuple[list[str], list[str]]:
    cmd = str(intent_command or "").replace(" ", "")
    is_lld = ("完整LLD" in cmd) or ("融合" in cmd and "LLD" in cmd) or ("LLD" in cmd and "生成" in cmd)
    if is_lld:
        m = collect_metrics(state) if state else {}
        lld_file = str(m.get("lld_file") or "").strip()
        lld_name = os.path.basename(lld_file) if lld_file else "完整 LLD 设计文件"
        return (
            ["全部已生成的规划表", "项目信息收集表", "设备清单"],
            [lld_name],
        )
    return (
        ["端口连线表", "项目信息收集表", "网络平面配置"],
        [f"{intent_command} 结果表"],
    )


class ExecConfirmStep(BaseStep):
    key = "exec_confirm"
    name = "确认执行计划"
    internal = True  # HITL 确认门，基础设施步骤，豁免 SKILL.md 后端节点声明

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        from ..pipelines.delivery import should_skip_step

        route = str(state.get("route_to") or "")
        if route and should_skip_step(self.key, route):
            emit(f"[{self.key}] 交付续跑 · 跳过（→{route}）")
            return {"logs": [f"[exec_confirm] 交付续跑跳过（→{route}）"]}

        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("exec"):
            emit(f"[{self.key}] 执行计划已确认，进入平面规划")
            return {
                "logs": ["[exec_confirm] 执行计划已确认"],
                "metrics": {"exec_confirmed": True},
            }

        m = collect_metrics(state)
        cmd = str(m.get("intent_command") or "").strip()
        if not cmd:
            emit(f"[{self.key}] 尚未识别规划命令，跳过确认门")
            return {"logs": ["[exec_confirm] 跳过：尚未识别规划命令"]}

        inputs, outputs = _expected_io(cmd, state)

        # 已就绪输入件（读真实 found_tags + files，不 mock）
        found_tags = set(m.get("found_tags") or [])
        files = state.get("files") or {}
        ready = [
            label_of(tag) for tag in FILE_CONFIG
            if tag in found_tags or files.get(f"input_{tag}")
        ]
        ready_text = "、".join(ready) if ready else "（待输入件检查）"

        reason = (
            f"已识别命令「{cmd}」。\n"
            f"将读取输入件：{('、'.join(inputs))}（当前已就绪：{ready_text}）。\n"
            f"将生成产物：{('、'.join(outputs))}。\n"
            "确认后进入平面规划与 LLD 融合流水线。"
        )
        emit(f"[{self.key}] ⏸ 等待确认执行计划：{cmd}")
        return {
            "current_step": self.key,
            "steps": [self.make_record(
                "hitl", ended_at=self._now(),
                log_tail=[f"[{self.key}] 等待确认执行计划「{cmd}」"],
                metrics={"exec_confirmed": False},
            )],
            "logs": [f"[exec_confirm] 等待确认执行计划「{cmd}」"],
            "metrics": {"exec_confirmed": False},
            "hitl": {
                "step": self.key,
                "command": cmd,
                "io_reads": inputs,
                "io_writes": outputs,
                "reason": reason,
                "need_files": [],
                "need_inputs": [{
                    "id": "exec",
                    "label": cmd,
                    "options": [
                        {"label": "确认执行", "value": "confirm"},
                        {"label": "重新选择", "value": "cancel"},
                    ],
                }],
            },
        }
