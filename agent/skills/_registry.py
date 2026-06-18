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

    def reload(self, names: list[str] | None = None) -> dict:
        """热加载 skill（P4 · 缓存失效 ①工厂表 + ②实例缓存）。

        - `names=None`：重跑目录发现 → 重载全部 + 注册新增目录 + 注销已删目录。
        - `names=[...]`：只重载指定 skill（不存在的名按移除/报错处理）。

        重载方式：清掉该 skill 包在 `sys.modules` 的整棵子树后重新 import，拿到**最新代码**
        （仅 reload `skill.py` 不会刷新已缓存的 `steps/` 等子模块，故清子树）。

        编译图（第 ③ 层 `graph._compiled*`）由调用方配合 `graph.invalidate()` 失效——
        registry 不依赖 graph，避免反向耦合。返回 {reloaded, added, removed, errors}。
        """
        from .discovery import discover_skill_specs

        specs = {s.name: s for s in discover_skill_specs()}
        result: dict = {"reloaded": [], "added": [], "removed": [], "errors": {}}

        # 全量重发现时，注销目录已删的 skill（热卸载）
        if names is None:
            for gone in [n for n in list(self._builders) if n not in specs]:
                self._builders.pop(gone, None)
                self._cache.pop(gone, None)
                result["removed"].append(gone)

        targets = list(specs.keys()) if names is None else list(names)
        for name in targets:
            spec = specs.get(name)
            if spec is None:
                if name in self._builders:
                    self._builders.pop(name, None)
                    self._cache.pop(name, None)
                    result["removed"].append(name)
                else:
                    result["errors"][name] = "目录未发现"
                continue
            try:
                was_registered = name in self._builders
                mod = _fresh_import_skill(name, spec)
                self._cache.pop(name, None)            # ② 实例缓存失效
                self._builders[name] = getattr(mod, spec.factory)  # ① 工厂表刷新
                result["added" if not was_registered else "reloaded"].append(name)
            except Exception as e:  # noqa: BLE001 — 单个失败不拖垮其余
                result["errors"][name] = f"{type(e).__name__}: {e}"
        return result

    def list_metadata(self) -> list[dict]:
        """元数据门面：name + description + manifest（version/enabled/ui/runtime）。

        P1：`/agent/skills` 返回此结构驱动前端导航。无论实例化成败，每项 shape 一致
        （含 enabled/ui 默认值），避免前端遍历时空字段崩溃。
        """
        out = []
        for name in self._builders.keys():
            try:
                skill = self.get(name)
                md = getattr(skill, "metadata", None)
                if md is not None:
                    item = md.short()
                    if not item.get("name"):
                        item["name"] = name  # SKILL.md 缺 name 时以注册名（运行时 ID）兜底
                    out.append(item)
                else:
                    out.append(_fallback_meta(name, getattr(skill, "description", "")))
            except Exception as e:
                item = _fallback_meta(name, "")
                item["enabled"] = False   # 实例化失败 → 默认下线，避免前端挂坏入口
                item["error"] = str(e)
                out.append(item)
        return out


def _fresh_import_skill(name: str, spec):
    """清掉该 skill 包在 sys.modules 的整棵子树后重新 import skill.py（拿最新代码）。

    内置：包名 `agent.skills.<name>`；外部：父目录入 `sys.path`、包名 `<name>`。
    只清该 skill 自身子树（不动 base/llm/tools 等共享底座，也不动 `agent.skills` 父包）。
    新增目录（尚未导入）时清理循环为空，直接 import 即可。
    """
    import importlib
    import sys

    if getattr(spec, "builtin", True):
        pkg = f"agent.skills.{name}"
    else:
        root = str(spec.directory.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        pkg = name
    for mod_name in [k for k in list(sys.modules) if k == pkg or k.startswith(pkg + ".")]:
        sys.modules.pop(mod_name, None)
    return importlib.import_module(f"{pkg}.skill")


def _fallback_meta(name: str, description: str) -> dict:
    """无 SkillMetadata 时的兜底门面（shape 与 SkillMetadata.short() 对齐）。"""
    return {
        "name": name,
        "description": description,
        "version": "",
        "enabled": True,
        "ui": {"label": name, "route_key": name, "group": "", "icon": "", "order": 999},
        "runtime": {},
    }


# 模块级单例
registry = SkillRegistry()
