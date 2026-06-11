"""
PresentChoicesTool · 向用户呈现选项，等待确认后继续

专为「发信/发 IM 前确认」设计，也适用于任何需要用户选择的场景。
模型调此工具后，chat_engine 立即结束本轮 ReAct、yield choices 事件；
用户选择后以新消息继续——无需额外 HITL 基础设施，复用无状态多轮机制。

不要用纯文本「回复1或2」替代此工具。
"""
from __future__ import annotations

from typing import Any

from .base import Tool


class PresentChoicesTool(Tool):
    @property
    def name(self) -> str:
        return "present_choices"

    @property
    def description(self) -> str:
        return (
            "在需要用户确认或选择时调用（如：发邮件/IM 前确认收件人和内容、多策略择一）。"
            "本轮 ReAct 立即结束，前端展示选项卡；用户选择后以新消息续对话。"
            "不要用纯文本问「回复1或2」，必须使用此工具。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "要问用户的问题（简明、含关键信息如收件人/内容摘要）",
                    "minLength": 1,
                },
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "选项显示文本"},
                            "value": {"type": "string", "description": "传回值（不填则同 label）"},
                        },
                        "required": ["label"],
                    },
                    "description": "选项列表（2-4 项，如「确认发送 / 取消」）",
                    "minItems": 2,
                    "maxItems": 4,
                },
            },
            "required": ["question", "options"],
        }

    def execute(self, question: str, options: list[dict[str, Any]], **_: Any) -> Any:
        # chat_engine 拦截此工具、不调 execute；此处仅保险兜底
        return {"_present_choices": True, "question": question, "options": options}
