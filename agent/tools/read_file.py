"""
ReadFileTool · 示例工具（demo）

演示「工具规范」：JSON Schema 参数 + cast + validate + execute。
读取文本文件内容，可选限制最大字节数。

后续可照此模式补：web_search / doc_text / site_survey 等（参考 nanobot 工具集）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Tool, ToolError


class ReadFileTool(Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取一个文本文件的内容，返回其文本（可用 max_bytes 限制读取大小）。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径（绝对或相对）",
                    "minLength": 1,
                },
                "max_bytes": {
                    "type": "integer",
                    "description": "最多读取的字节数",
                    "minimum": 1,
                    "maximum": 1_000_000,
                },
            },
            "required": ["path"],
        }

    def execute(self, path: str, max_bytes: int = 100_000, **_: Any) -> str:
        p = Path(path)
        if not p.is_file():
            return ToolError(f"文件不存在：{path}")
        try:
            data = p.read_bytes()[:max_bytes]
            return data.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            return ToolError(f"读取失败：{e}")
