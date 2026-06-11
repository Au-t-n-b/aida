"""
Step · 审批与分发（v4 · report_gen 意图专属）

意图: report_gen 专属

v4 审批闭环（设计文档「报告审批与分发」）：
  四件套就绪 → HITL 专家审批门（三选）：
    通过分发 → 四件套真实发邮件给全部干系人（走 agent/mailer.py）
    驳回补勘 → 记录驳回意见，引导用户发起「补充勘测」意图
    暂存     → 暂不分发，保留产物，后续随时可再触发

四件套 = 全量勘测结果表 + 问题清单表 + 风险识别结果表 + 工勘报告。
真实发信受 AIDA_SEND_EMAIL=1 控制，默认 dry-run。
"""
from __future__ import annotations
import os
import json
from datetime import datetime
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip


# 四件套 glob 模式 → 人类可读标签（实际文件名含 ACT001_... 前缀）
_REQUIRED_GLOBS: dict[str, str] = {
    "*工勘报告*.docx": "工勘报告.docx",
    "*全量勘测结果表*.xlsx": "全量勘测结果表.xlsx",
    "*问题清单表*.xlsx": "问题清单表.xlsx",
    "*风险识别结果表*.xlsx": "风险识别结果表.xlsx",
}


def _find_output_file(output_dir: Path, pattern: str) -> Path | None:
    matches = sorted(output_dir.glob(pattern))
    return matches[0] if matches else None


def _resolve_recipients(role_names: tuple[str, ...]) -> list[dict]:
    """从模块内置收件人配置解析（逐个角色常量兜底，自包含）。不可用 → []。"""
    from .. import recipients as _pc
    try:
        get_recipients = getattr(_pc, "get_recipients", None)
        if get_recipients is None:
            return []
        for rn in role_names:
            role = getattr(_pc, rn, None)
            if role is not None:
                rcs = get_recipients(role) or []
                if rcs:
                    return rcs
        return []
    except Exception:
        return []


class ReportDistributeStep(BaseStep):
    key = "report_distribute"
    name = "审批与分发"
    artifacts_pattern = []  # 不产文件

    # ── 四件套就绪检查 ──
    def _resolve_suite(self, ctx: SkillContext) -> tuple[dict[str, Path], list[str]]:
        resolved: dict[str, Path] = {}
        missing: list[str] = []
        for pattern, label in _REQUIRED_GLOBS.items():
            p = _find_output_file(ctx.output_dir, pattern)
            if p is None:
                missing.append(label)
            else:
                resolved[label] = p
        return resolved, missing

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        # 四件套缺失 → 先补产物（需先跑 report_gen）
        _, missing = self._resolve_suite(ctx)
        if missing:
            return {
                "ok": False,
                "missing": [f"ProjectData/Output/{m}" for m in missing],
                "note": "四件套未就绪，请先执行报告生成（report_gen_run）",
            }

        # 已有审批决策 → 放行进 run 执行决策
        if ctx.project.get("approval_decision"):
            return {"ok": True, "missing": []}

        # 否则呈现审批 HITL 门（三选）
        experts = _resolve_recipients(("ROLE_PD_TD_EXPERT", "ROLE_EXPERT", "ROLE_ALL_STAKEHOLDERS"))
        expert_hint = (
            f"将提交 {len(experts)} 位评审专家审批" if experts
            else "（未解析到评审专家，将以 dry-run 记录）"
        )
        note = f"四件套已就绪。{expert_hint}。请代表评审决策："
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [
                {
                    "id": "approval_choice",
                    "label": "专家审批决策",
                    "options": [
                        {
                            "label": "✓ 审批通过 · 分发全部干系人",
                            "value": "approve",
                            "description": "四件套邮件分发给全部项目干系人，流程闭环",
                        },
                        {
                            "label": "✗ 驳回 · 退回补充勘测",
                            "value": "reject",
                            "description": "记录驳回意见，需发起「补充勘测」意图补数据后重出报告",
                        },
                        {
                            "label": "⏸ 暂存 · 稍后处理",
                            "value": "hold",
                            "description": "暂不分发，保留四件套，后续随时可再触发审批",
                        },
                    ],
                }
            ],
            "note": note,
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        resolved, missing = self._resolve_suite(ctx)
        if missing:
            for f in missing:
                emit(f"[错误] 缺少四件套文件：{f}（需先执行 report_gen）")
            return {"error": f"report_distribute 缺产物：{', '.join(missing)}"}

        decision = ctx.project.get("approval_decision", "")

        # 项目信息
        project_name = "未知项目"
        proj_info = ctx.runtime_dir / "project_info.json"
        if proj_info.exists():
            try:
                info = json.loads(proj_info.read_text(encoding="utf-8"))
                project_name = info.get("项目名称", project_name)
            except Exception as e:
                emit(f"  [提示] project_info.json 解析失败：{e}")

        attachments = [str(p) for p in resolved.values()]
        suite_names = " / ".join(p.name for p in resolved.values())
        date_str = datetime.now().strftime("%Y%m%d")

        # ── 暂存 ──
        if decision == "hold":
            emit("=== 审批暂存 · 四件套保留，未分发 ===")
            emit(f"四件套：{suite_names}")
            return {"metrics": {
                "approval_status": "held", "email_sent": False,
                "attachments": len(attachments), "project_name": project_name,
            }}

        # ── 驳回补勘 ──
        if decision == "reject":
            emit("=== 审批驳回 · 退回补充勘测 ===")
            emit("请发起「补充勘测」意图：补充缺失/不满足项的数据后重新生成报告再提交审批。")
            return {"metrics": {
                "approval_status": "rejected", "email_sent": False,
                "attachments": len(attachments), "project_name": project_name,
                "next_action": "supplement",
            }}

        # ── 通过分发 ──
        recipients = _resolve_recipients(("ROLE_ALL_STAKEHOLDERS", "ROLE_PD_TD_EXPERT"))
        to = [r.get("email", "") for r in recipients if r.get("email")]
        emit(f"审批通过 · 分发干系人：{len(recipients)} 人")
        for r in recipients:
            emit(f"  [{r.get('role','')}] {r.get('name','')} <{r.get('email','')}>")

        subject = f"【智慧工勘·审批通过】{project_name} 工勘四件套 - {date_str}"
        body = (
            f"项目：{project_name}\n"
            f"评审结论：通过\n\n"
            f"随附工勘四件套：\n  " + "\n  ".join(p.name for p in resolved.values()) +
            "\n\n请查收。"
        )

        email_sent = False
        if not to:
            emit("[警告] 未解析到干系人收件人，分发跳过（四件套已就绪可手动分发）")
        else:
            from agent.mailer import send_mail
            res = send_mail(to, subject, body, attachments=attachments)
            if res.get("dry_run"):
                emit(f"  [dry-run] 分发邮件未真发（设 AIDA_SEND_EMAIL=1 启用）→ {len(to)} 人")
            elif res.get("ok"):
                email_sent = True
                emit(f"  ✓ 四件套已分发 → {len(to)} 人（via {res.get('via')}）")
            else:
                emit(f"  [警告] 分发邮件失败：{res.get('error')}")

        emit("=== 审批通过 · 分发完成（流程闭环）===")
        return {"metrics": {
            "approval_status": "approved", "email_sent": email_sent,
            "recipients": len(recipients), "attachments": len(attachments),
            "project_name": project_name,
        }}
