"""
skill-discovery · 目录发现约定守门（规范 5 守门 · P3 约定优于配置）

背景：P3 起 skill 注册由 agent/skills/discovery.py 按目录约定发现，替代硬编码 _specs。
约定：每个 skill 目录（非下划线开头、含 skill.py）必须暴露工厂 ``get_<目录名>_skill``。
本守门保证「发现器扫到的每个 skill 都有合法工厂、无孤儿目录」——否则启动会**静默跳过**该 skill，
入口悄悄消失，难排查。

设计：纯 stdlib，按文件加载 discovery.py（不 import agent.skills 包，免触发重依赖），**无需 venv**。
工厂用文本检测（不实例化 skill，避免 venv / 业务依赖）。

退出码：违规 → 1；干净 → 0。

用法：
    python agent/scripts/lint_skill_discovery.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，✓/❌/中文会 UnicodeEncodeError → 强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # aida/
AGENT_SKILLS = PROJECT_ROOT / "agent" / "skills"


def _load_discovery_module():
    """按文件加载 discovery.py（不触发 agent.skills 包 import）。"""
    import importlib.util
    path = AGENT_SKILLS / "discovery.py"
    spec = importlib.util.spec_from_file_location("_aida_skill_discovery", path)
    mod = importlib.util.module_from_spec(spec)
    # 注册到 sys.modules：@dataclass 内部会按 cls.__module__ 反查模块命名空间（Py3.12+ 必需）
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def has_factory(skill_py_text: str, factory: str) -> bool:
    """文本检测 skill.py 是否定义了约定工厂（`def get_<name>_skill(`）。"""
    return re.search(rf"^def {re.escape(factory)}\s*\(", skill_py_text, re.M) is not None


def _builtin_skill_dirs(base: Path) -> list[Path]:
    """与 discovery 同口径的独立目录扫描（用于孤儿检测对照）。"""
    if not base.is_dir():
        return []
    return sorted(
        d for d in base.iterdir()
        if d.is_dir()
        and not d.name.startswith("_")
        and not d.name.startswith(".")
        and (d / "skill.py").exists()
    )


def main() -> int:
    discovery = _load_discovery_module()
    specs = discovery.discover_skill_specs()
    violations: list[str] = []

    if not specs:
        sys.stdout.write("[skill-discovery] ⚠ 未发现任何 skill（discovery 扫描为空？）\n")
        return 1

    # 1) 每个发现的 skill 必须有合法工厂 get_<name>_skill
    for s in specs:
        skill_py = s.directory / discovery.SKILL_ENTRY
        if not skill_py.exists():
            violations.append(f"[{s.name}] 目录缺 {discovery.SKILL_ENTRY}")
            continue
        text = skill_py.read_text(encoding="utf-8", errors="replace")
        if not has_factory(text, s.factory):
            violations.append(
                f"[{s.name}] {discovery.SKILL_ENTRY} 未定义工厂 `def {s.factory}(`"
                "（约定：目录名 → get_<name>_skill）"
            )

    # 2) 孤儿检测：内置目录里「像 skill」的目录必须都被发现器识别
    discovered_builtin = {s.name for s in specs if s.builtin}
    for d in _builtin_skill_dirs(AGENT_SKILLS):
        if d.name not in discovered_builtin:
            violations.append(f"[{d.name}] 含 skill.py 却未被发现器识别（孤儿目录）")

    if not violations:
        names = ", ".join(s.name for s in specs)
        sys.stdout.write(
            f"[skill-discovery] OK · 发现 {len(specs)} 个 skill，工厂约定一致（{names}）\n"
        )
        return 0

    sys.stdout.write(f"[skill-discovery] ❌ 发现 {len(violations)} 处问题：\n\n")
    for msg in violations:
        sys.stdout.write(f"  {msg}\n")
    sys.stdout.write(
        "\n说明：P3 起 skill 由目录约定发现（discovery.py）——目录名即 skill 名，"
        "须含 skill.py 且暴露 get_<name>_skill 工厂。\n"
        "  新增 skill 复制 skills/_template/，重命名目录与工厂即可（无需改 __init__.py）。\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
