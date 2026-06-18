"""
Skill 目录发现器（P3 · 约定优于配置）

替代 ``__init__.py`` 里硬编码的 ``_specs`` 列表：按目录约定发现 skill——
**目录名即 skill 名，目录内含 ``skill.py`` 暴露 ``get_<name>_skill`` 工厂** 即被注册。
于是「增删 skill = 增删一个目录」，不再改 ``__init__.py``；外部 skill 放
``AIDA_SKILLS_PATH``（``os.pathsep`` 分隔的根目录列表）即可挂载。

机制不变：本模块只回答「有哪些 skill、工厂叫什么、在哪个目录」，
真正的注册 / `build_graph` 编译 / HITL / SDUI 一律仍由现有 registry 与 BaseSkill 负责。

刻意只依赖标准库：守门（lint_skill_discovery / lint_skill_manifest）可按文件独立加载本模块，
无需 venv、不触发 ``_register_all`` 的重依赖，保证「契约≡代码」（lint 与运行时用同一套发现逻辑）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_SKILLS_PATH = "AIDA_SKILLS_PATH"   # os.pathsep 分隔的外部 skill 根目录列表
SKILL_ENTRY = "skill.py"               # 约定入口文件（目录内有它才算 skill）


@dataclass(frozen=True)
class SkillSpec:
    """一个被发现的 skill 的注册说明。"""

    name: str          # = 目录名
    factory: str       # = get_<name>_skill（约定工厂名）
    directory: Path    # skill 目录绝对路径
    builtin: bool      # True=随仓库内置（agent/skills 下）；False=来自 AIDA_SKILLS_PATH


def factory_name(skill_name: str) -> str:
    """约定工厂名：目录 ``<name>`` → ``get_<name>_skill``。"""
    return f"get_{skill_name}_skill"


def _is_skill_dir(d: Path) -> bool:
    """是否为合法 skill 目录：是目录、非下划线/点开头（_template/__pycache__/.* 跳过）、含 skill.py。"""
    return (
        d.is_dir()
        and not d.name.startswith("_")
        and not d.name.startswith(".")
        and (d / SKILL_ENTRY).exists()
    )


def builtin_dir() -> Path:
    """内置 skill 根目录（= 本包目录）。"""
    return Path(__file__).resolve().parent


def external_roots() -> list[Path]:
    """解析 ``AIDA_SKILLS_PATH``（os.pathsep 分隔）为去重后的存在目录列表。"""
    raw = os.environ.get(ENV_SKILLS_PATH, "").strip()
    if not raw:
        return []
    out: list[Path] = []
    seen: set[str] = set()
    for part in raw.split(os.pathsep):
        part = part.strip()
        if not part:
            continue
        p = Path(part).expanduser()
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        if p.is_dir():
            out.append(p)
    return out


def discover_skill_specs(base: Path | None = None) -> list[SkillSpec]:
    """发现内置 + 外部 skill，返回按 name 排序、去重（内置优先）的 SkillSpec 列表。

    - 内置：``base``（默认本包目录）下每个含 ``skill.py`` 的非下划线目录。
    - 外部：``AIDA_SKILLS_PATH`` 各根目录下同理；同名时不覆盖内置。

    顺序：按 name 排序（确定性）。注册顺序对运行时无影响——端点按路径参数泛化、
    ``/agent/skills`` 与导航分别按 set / ui.order 消费，均与注册顺序无关。
    """
    root = base or builtin_dir()
    found: dict[str, SkillSpec] = {}

    if root.is_dir():
        for d in sorted(root.iterdir()):
            if _is_skill_dir(d):
                found.setdefault(d.name, SkillSpec(d.name, factory_name(d.name), d, True))

    for ext in external_roots():
        for d in sorted(ext.iterdir()):
            if _is_skill_dir(d) and d.name not in found:
                found[d.name] = SkillSpec(d.name, factory_name(d.name), d, False)

    return [found[k] for k in sorted(found)]
