"""hotreload · 运行时热插拔单个 skill 目录包（零重启）

P1a 让"加 skill"靠目录自动发现，但那次发现只在进程 import 时跑一次。本模块让它能在
**运行中**针对单个 skill 再跑一遍并清缓存 —— 把目录包放进 agent/skills/<name>/ 后，
调一次 reload_skill(name)（或 POST /agent/admin/reload）即生效，进程不重启。

机制（三步）：
  ① purge sys.modules["agent.skills.<name>*"] 再 import（绕开 importlib 浅重载，连 steps/* 一起换新）
  ② registry.register(name, 新 get_<name>_skill)
  ③ graph.invalidate(name) + registry._cache.pop(name)  → 下次 /start 用新代码重建图

事务化：新代码 import 失败 → 回滚 sys.modules、保留旧版、返回 error（坏编辑不污染、不崩、
不影响其它 skill 与在跑的 run）。这正是它优于 `uvicorn --reload`（整 app 重启、改错即崩、丢全部 run）之处。
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

PKG = __package__  # "agent.skills"


def _prefix(name: str) -> str:
    return f"{PKG}.{name}"


def _purge_modules(name: str) -> dict[str, Any]:
    """删掉 sys.modules 里该 skill 的所有（子）模块，返回被删的备份（回滚用）。"""
    pre = _prefix(name)
    backup = {k: v for k, v in sys.modules.items() if k == pre or k.startswith(pre + ".")}
    for k in backup:
        del sys.modules[k]
    return backup


def _restore_modules(name: str, backup: dict[str, Any]) -> None:
    """回滚：清掉可能半 import 的，再把旧模块放回去。"""
    _purge_modules(name)
    sys.modules.update(backup)


def _is_legal(name: str) -> bool:
    """与 discover_skill_names 同规则 + 防路径穿越/注入：合法标识符、非下划线/点开头。"""
    return bool(name) and name.isidentifier() and name[0] not in "_."


def _unregister(name: str) -> None:
    from . import registry
    from .. import graph
    registry._builders.pop(name, None)
    registry._cache.pop(name, None)
    _purge_modules(name)
    graph.invalidate(name)


def reload_skill(name: str) -> dict:
    """热重载 / 热加载 / 卸载单个 skill。

    返回 {ok: bool, skill, action, error?}，action ∈ added | reloaded | removed | error。
    """
    from . import registry
    from .. import graph

    if not _is_legal(name):
        return {"ok": False, "skill": name, "action": "error", "error": "非法 skill 名"}

    pkg_dir = Path(__file__).resolve().parent / name
    if not (pkg_dir / "skill.py").is_file():
        # 目录/skill.py 不在 → 已注册则卸载，否则报错
        if name in registry._builders:
            _unregister(name)
            return {"ok": True, "skill": name, "action": "removed"}
        return {"ok": False, "skill": name, "action": "error",
                "error": f"agent/skills/{name}/skill.py 不存在"}

    was_registered = name in registry._builders
    backup = _purge_modules(name)
    try:
        mod = importlib.import_module(f".{name}.skill", package=PKG)
        factory = getattr(mod, f"get_{name}_skill")
    except Exception as e:  # noqa: BLE001 — 坏编辑回滚，保留旧版
        _restore_modules(name, backup)
        return {"ok": False, "skill": name, "action": "error",
                "error": f"{type(e).__name__}: {e}"}

    registry.register(name, factory)
    registry._cache.pop(name, None)
    graph.invalidate(name)
    return {"ok": True, "skill": name, "action": "reloaded" if was_registered else "added"}


def rescan() -> dict:
    """全量重扫 agent/skills/：磁盘上的全部 reload/add，已注册但磁盘已无的卸载。"""
    from . import registry, discover_skill_names
    disk = set(discover_skill_names())
    known = set(registry._builders.keys())
    results = [reload_skill(n) for n in sorted(disk)]
    for gone in sorted(known - disk):
        _unregister(gone)
        results.append({"ok": True, "skill": gone, "action": "removed"})
    return {"ok": all(r["ok"] for r in results), "results": results}
