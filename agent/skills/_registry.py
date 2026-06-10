"""
SkillRegistry · 渐进式暴露的最小实现

只暴露 Skill 元数据 (name + description)，不预加载 SKILL.md 正文 / step 实现。
路由层（未来的 Planner / Router）拿这份 metadata 决定调用哪个 Skill。
"""
from __future__ import annotations
from typing import Callable, Iterable

from .base import BaseSkill


class SkillRegistry:
    """全局 Skill 注册表（单例风格，但不强制）。"""

    def __init__(self):
        self._builders: dict[str, Callable[[], BaseSkill]] = {}
        self._cache: dict[str, BaseSkill] = {}

    def register(self, name: str, builder: Callable[[], BaseSkill]) -> None:
        """注册一个 Skill 工厂（lazy，避免启动时拉网络/读盘）"""
        self._builders[name] = builder

    def get(self, name: str) -> BaseSkill:
        if name not in self._cache:
            if name not in self._builders:
                raise KeyError(f"Skill '{name}' 未注册")
            self._cache[name] = self._builders[name]()
        return self._cache[name]

    def names(self) -> list[str]:
        return list(self._builders.keys())

    def list_metadata(self) -> list[dict]:
        """渐进式暴露：只返回元数据门面（name + description），不触发 step 加载"""
        out = []
        for name in self._builders.keys():
            try:
                skill = self.get(name)
                md = getattr(skill, "metadata", None)
                if md is not None:
                    out.append(md.short())
                else:
                    out.append({"name": name, "description": getattr(skill, "description", "")})
            except Exception as e:
                out.append({"name": name, "description": "", "error": str(e)})
        return out


# 模块级单例
registry = SkillRegistry()
