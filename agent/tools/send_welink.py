"""
SendWelinkTool · 即时消息发送工具（会话/step 均可调）

走 notifier.py 统一出口（《交付 Claw/Agent 工程范式》规范 4 · 副作用统一），默认 dry-run。
典型场景：工勘审批通知、干系人告警、跨团队进展播报。
"""
from __future__ import annotations

from typing import Any

from .base import Tool


class SendWelinkTool(Tool):
    @property
    def name(self) -> str:
        return "send_welink"

    @property
    def description(self) -> str:
        return (
            "通过小鲁班/WeLink 发送即时消息（如工勘审批通知、干系人告警）。"
            "支持纯文本、HTML 富文本及等宽表格格式。"
            "默认 dry-run 不会真发，需环境 AIDA_SEND_IM=1 才真实发送。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "receiver": {
                    "type": "string",
                    "description": "收件人：群 ID 或工号",
                    "minLength": 1,
                },
                "content": {
                    "type": "string",
                    "description": "消息正文（支持 HTML <span style=...> 富文本）",
                },
                "sender": {
                    "type": "string",
                    "description": "可选：发件人工号（不填则由网关决定）",
                },
                "table_headers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：表格列标题，与 table_rows 配合生成等宽文本表格",
                },
                "table_rows": {
                    "type": "array",
                    "items": {"type": "array"},
                    "description": "可选：表格行数据（列表的列表）",
                },
            },
            "required": ["receiver"],
        }

    def execute(
        self,
        receiver: str,
        content: str = "",
        sender: str | None = None,
        table_headers: list[str] | None = None,
        table_rows: list[list[Any]] | None = None,
        **_: Any,
    ) -> Any:
        from agent.notifier import send_welink
        return send_welink(
            receiver,
            content,
            table_headers=table_headers,
            table_rows=table_rows,
            sender=sender,
        )
