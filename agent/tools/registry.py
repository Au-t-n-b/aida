"""
ToolRegistry · 工具注册表（对应《交付 Claw/Agent 工程范式》§4.2）

移植并适配自 nanobot（agent/tools/registry.py），execute 同步化。

职责：
  - register / get / has 工具
  - get_definitions() → OpenAI function 列表（喂会话 ReAct）
  - execute(name, params) → cast → validate → run，出错回提示让模型自纠
"""
from __future__ import annotations

from typing import Any

from .base import Tool, is_tool_error


class ToolRegistry:
    """工具注册表，支持动态注册与受控执行。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def get_definitions(self, allowed: list[str] | None = None) -> list[dict[str, Any]]:
        """OpenAI function 定义列表；allowed 给定时只返回白名单内的（受控子任务用）。"""
        tools = self._tools.values()
        if allowed is not None:
            tools = [t for t in tools if t.name in allowed]
        return [t.to_schema() for t in tools]

    def execute(self, name: str, params: dict[str, Any]) -> Any:
        """按名执行：cast → validate → run。出错附「换个方法重试」提示，便于模型自纠。"""
        hint = "\n\n[分析上面的错误并换一种方式重试。]"
        tool = self._tools.get(name)
        if not tool:
            return f"Error: 工具 '{name}' 不存在。可用：{', '.join(self.tool_names)}"
        try:
            params = tool.cast_params(params)
            errors = tool.validate_params(params)
            if errors:
                return f"Error: 工具 '{name}' 参数不合法：" + "; ".join(errors) + hint
            result = tool.execute(**params)
            if is_tool_error(result):
                # 字符串错误追加自纠提示（模型可读）；结构化 dict 错误原样返回
                return (result + hint) if isinstance(result, str) else result
            return result
        except Exception as e:  # noqa: BLE001 — 工具异常需回给模型，不向上抛
            return f"Error executing {name}: {e}" + hint

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
