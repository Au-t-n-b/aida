"""
SendMailTool · 邮件发送工具（即时工具，会话/step 均可调）

走 mailer.py 统一出口（铁律③），默认 dry-run。
典型场景：工勘报告分发、干系人通知。
"""
from __future__ import annotations

from typing import Any

from .base import Tool


class SendMailTool(Tool):
    @property
    def name(self) -> str:
        return "send_mail"

    @property
    def description(self) -> str:
        return (
            "发送邮件（如工勘报告分发、干系人通知）。可带附件。"
            "默认 dry-run 不会真发，除非环境显式开启 AIDA_SEND_EMAIL=1。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "收件人邮箱列表",
                },
                "subject": {"type": "string", "description": "邮件主题", "minLength": 1},
                "body": {"type": "string", "description": "邮件正文", "minLength": 1},
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：附件文件路径列表",
                },
            },
            "required": ["to", "subject", "body"],
        }

    def execute(
        self,
        to: list[str],
        subject: str,
        body: str,
        attachments: list[str] | None = None,
        **_: Any,
    ) -> Any:
        from agent.mailer import send_mail
        return send_mail(to, subject, body, attachments=attachments)
