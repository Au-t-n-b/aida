"""
AIDA Agent Skills · 通用 Skill 抽象层

设计目标：
- 让所有业务场景 Skill（智慧工勘 / 规划设计 / 设备安装 / 部署调测）按同一套接口编写
- LangGraph 编排自动生成
- 每个 Step 都是可观测的（Langfuse / LangSmith trace 友好）
- LLM 调用走统一的 langchain_openai 客户端 → 自动捕获

入口：
    from agent.skills import registry
    registry.list_metadata()         # 渐进式暴露 · 仅 name + description
    skill = registry.get("zhgk")     # 真正加载（含 SKILL.md frontmatter）
    graph = skill.build_graph()
"""
from .base import BaseSkill, BaseStep, SkillContext, SkillState, StepResult, CheckResult
from ._registry import registry, SkillRegistry
from ._loader import SkillMetadata, load_skill_md, default_skill_md_path


def _register_all():
    """目录自动发现：扫 agent/skills/<name>/skill.py，注册其 get_<name>_skill 工厂。

    加一个 skill = 新建 agent/skills/<name>/（skill.py 暴露 get_<name>_skill），
    **无需改本文件**——消除「每加一个 skill 都要碰 __init__.py」这个高冲突注册点
    （VIBECODING_HARNESS.md §7 · P1a）。约定由 lint_module_boundaries.py 守门。

    规则：
    - 只认 agent/skills/ 下的**目录**且含 skill.py；下划线/点开头的目录
      （`_template` 脚手架、`__pycache__` 等）跳过，不注册。
    - 工厂名约定 `get_<dirname>_skill`，注册 id = 目录名。
    - 单个 skill 导入失败 / 缺工厂时**只跳过它**并打印 stderr，不拖垮整个注册表——
      否则一个未提交的可选 skill（如 device_install）会让全部 skill 不可用。
    """
    import importlib
    import sys
    from pathlib import Path

    skills_dir = Path(__file__).resolve().parent
    for child in sorted(skills_dir.iterdir()):
        name = child.name
        if not child.is_dir() or name[0] in "_." or not (child / "skill.py").is_file():
            continue
        try:
            mod = importlib.import_module(f".{name}.skill", package=__name__)
            registry.register(name, getattr(mod, f"get_{name}_skill"))
        except Exception as e:  # noqa: BLE001 — 缺件/语法/缺工厂都不应阻断其余 skill
            sys.stderr.write(f"[skills] 跳过 {name}：{type(e).__name__}: {e}\n")


_register_all()

__all__ = [
    "BaseSkill", "BaseStep",
    "SkillContext", "SkillState",
    "StepResult", "CheckResult",
    "registry", "SkillRegistry",
    "SkillMetadata", "load_skill_md", "default_skill_md_path",
]
