"""
step · 确认发布（确认型 HITL 门 · 对齐设计稿 finalize + test_check）

对齐《系统设计工作台-周二版》：FinalizeCard 双按钮（检查测试用例 / 确认发布），
点击「检查测试用例」弹出 TestCheckCard，确认后解锁「确认发布」。

机制：在 run() 内读 project.confirmations.publish；未确认 → 返回 hitl(finalize/test_check UI)。
用户在 resume 选「确认发布」→ apply_resume_payload 把 confirmations.publish 写进 project，
本步放行进入 publish。

⚠️ 不使用设计稿 mock：产物计数读自前序 step 真实写入的 metrics（lld_file / ztp_file 等）。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from agent.sdui.projector_base import collect_metrics


class PublishConfirmStep(BaseStep):
    key = "publish_confirm"
    name = "确认发布"
    internal = True  # HITL 确认门，基础设施步骤，豁免 SKILL.md 后端节点声明

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("publish"):
            emit(f"[{self.key}] 已确认发布，写回交付进度")
            return {
                "logs": ["[publish_confirm] 已确认发布"],
                "metrics": {"publish_confirmed": True},
                "route_to": "",  # 清除续跑跳转，避免 publish 步 router 回跳本步
            }

        m = collect_metrics(state)
        ready_bits: list[str] = []
        if m.get("lld_file"):
            ready_bits.append("完整 LLD 设计文件")
        if m.get("ztp_file"):
            ready_bits.append("ZTP 开局文件")
        files = state.get("files") or {}
        if files.get("input_Test_Case"):
            ready_bits.append("测试用例")
        ready_text = "、".join(ready_bits) if ready_bits else "已生成产物"

        checked = bool(confs.get("publish_checked"))
        test_check_pending = bool(confs.get("publish_test_check_pending"))

        # TestCheckCard：点击「检查测试用例」后弹出，确认后解锁发布。
        # 测试用例拷贝 / 输出件高亮由 apply_resume_payload + SDUI 引导完成，此处不再触发 LLD 等副作用。
        if test_check_pending and not checked:
            emit(f"[{self.key}] ⏸ 检查测试用例确认中")
            result: StepResult = {
                "current_step": self.key,
                "steps": [self.make_record(
                    "hitl", ended_at=self._now(),
                    log_tail=[f"[{self.key}] 检查测试用例"],
                    metrics={"publish_confirmed": False, "publish_checked": False},
                )],
                "logs": ["[publish_confirm] 检查测试用例"],
                "metrics": {"publish_confirmed": False, "publish_checked": False},
                "hitl": {
                    "step": self.key,
                    "ui": "test_check",
                    "title": "检查测试用例",
                    "reason": "是否已经检查了测试用例？确认后即可继续发布。",
                    "need_files": [],
                    "need_inputs": [],
                },
            }
            return result

        # FinalizeCard：双按钮（检查测试用例 + 确认发布）
        reason = (
            f"发布前请先在右侧「关键输出件」核对测试用例与{ready_text}。"
            if not checked
            else (
                f"测试用例已检查。确认无误后发布交付（{ready_text}），"
                "将写回项目活动进度并完成本次系统设计任务。"
            )
        )
        emit(f"[{self.key}] ⏸ 等待{'确认发布' if checked else '检查测试用例并发布'}")
        return {
            "current_step": self.key,
            "steps": [self.make_record(
                "hitl", ended_at=self._now(),
                log_tail=[f"[{self.key}] 等待确认发布"],
                metrics={"publish_confirmed": False, "publish_checked": checked},
            )],
            "logs": ["[publish_confirm] 等待确认发布"],
            "metrics": {"publish_confirmed": False, "publish_checked": checked},
            "hitl": {
                "step": self.key,
                "ui": "finalize",
                "title": "确认发布",
                "reason": reason,
                "publish_checked": checked,
                "need_files": [],
                "need_inputs": [],
            },
        }
