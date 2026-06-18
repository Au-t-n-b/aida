"""report_distribute · 审批与分发（报告附件邮件）."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..path_config import get_parse_dir, get_output_dir
from ._intent_guard import should_skip


_APPROVAL_FORM_INPUT = {
    "id": "approval_mail",
    "type": "form",
    "label": "填写审批邮件",
    "payloadKey": "approval_mail",
    "submitLabel": "发送审批邮件",
    "helpText": "附件将自动带上已生成的工勘报告。多个邮箱可用逗号、分号或换行分隔。",
    "fields": [
        {
            "key": "approval_email",
            "label": "审批人员邮箱",
            "placeholder": "approver@example.com",
            "required": True,
        },
        {
            "key": "approval_subject",
            "label": "邮件主题",
            "placeholder": "【智慧工勘】工勘报告审批 - 智算 Q3 · 客户甲一期",
            "required": True,
        },
        {
            "key": "approval_body",
            "label": "邮件正文",
            "placeholder": "请审批附件中的工勘报告。",
            "required": True,
        },
    ],
}


def _find_output_file(output_dir: Path, pattern: str) -> Path | None:
    matches = sorted(output_dir.glob(pattern))
    return matches[0] if matches else None


def _read_project_info(ctx: SkillContext) -> dict:
    info_path = get_parse_dir() / "project_info.json"
    if info_path.exists():
        try:
            return json.loads(info_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _default_subject(ctx: SkillContext) -> str:
    project_name = str(ctx.project.get("project_name") or _read_project_info(ctx).get("project_name") or "项目")
    return f"【智慧工勘】工勘报告审批 - {project_name}"


def _default_body(ctx: SkillContext) -> str:
    info = _read_project_info(ctx)
    project_name = str(ctx.project.get("project_name") or info.get("project_name") or "项目")
    room_name = str(ctx.project.get("room_name") or info.get("room_name") or "")
    return (
        f"请审批附件中的工勘报告。\n\n"
        f"项目：{project_name}\n"
        f"机房：{room_name}\n"
        f"提交时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    )


def _split_emails(raw: str) -> list[str]:
    import re

    vals = [x.strip() for x in re.split(r"[,;；，\s]+", raw or "") if x.strip()]
    return vals


class ReportDistributeStep(BaseStep):
    key = "report_distribute"
    name = "审批与分发"
    artifacts_pattern = []  # 不产文件

    def _resolve_report(self, ctx: SkillContext) -> Path | None:
        info = _read_project_info(ctx)
        saved = str(info.get("mock_report_path") or info.get("report_path") or "").strip()
        if saved and Path(saved).is_file():
            return Path(saved)
        return (
            _find_output_file(get_output_dir(), "*工勘报告*.pdf")
            or _find_output_file(get_output_dir(), "*工勘报告*.docx")
        )

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        report = self._resolve_report(ctx)
        if report is None:
            return {
                "ok": False,
                "missing": ["输出结果/*工勘报告*.pdf"],
                "note": "工勘报告附件未就绪，请先执行报告生成",
            }

        if ctx.project.get("approval_email"):
            return {"ok": True, "missing": []}

        form = dict(_APPROVAL_FORM_INPUT)
        form["fields"] = [dict(f) for f in _APPROVAL_FORM_INPUT["fields"]]
        for f in form["fields"]:
            if f["key"] == "approval_subject":
                f["defaultValue"] = _default_subject(ctx)
            elif f["key"] == "approval_body":
                f["defaultValue"] = _default_body(ctx)
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [form],
            "note": f"工勘报告已就绪：{report.name}。请填写审批邮件并发送。",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        report = self._resolve_report(ctx)
        if report is None:
            emit("[错误] 缺少工勘报告附件（需先执行 report_gen_run）")
            return {"error": "report_distribute 缺少工勘报告附件"}

        info = _read_project_info(ctx)
        project_name = str(ctx.project.get("project_name") or info.get("project_name") or "未知项目")
        recipients = _split_emails(str(ctx.project.get("approval_email") or ""))
        subject = str(ctx.project.get("approval_subject") or _default_subject(ctx))
        body = str(ctx.project.get("approval_body") or _default_body(ctx))
        attachments = [str(report)]

        if not recipients:
            return {"error": "report_distribute 缺少审批人员邮箱"}

        email_sent = False
        emit(f"[report_distribute] 审批邮件收件人：{', '.join(recipients)}")
        emit(f"[report_distribute] 附件：{report.name}")
        from agent.mailer import send_mail
        res = send_mail(recipients, subject, body, attachments=attachments)
        if res.get("dry_run"):
            emit(f"[report_distribute] dry-run：审批邮件未真发（设 AIDA_SEND_EMAIL=1 启用）→ {len(recipients)} 人")
        elif res.get("ok"):
            email_sent = True
            emit(f"[report_distribute] ✓ 审批邮件已发送 → {len(recipients)} 人（via {res.get('via')}）")
        else:
            emit(f"[report_distribute] [警告] 审批邮件发送失败：{res.get('error')}")
            return {"error": f"审批邮件发送失败：{res.get('error')}"}

        emit("=== 审批与分发完成 ===")
        return {"metrics": {
            "approval_status": "submitted", "email_sent": email_sent,
            "recipients": len(recipients), "recipient_emails": recipients,
            "attachments": len(attachments), "report_path": str(report),
            "project_name": project_name,
        }}
