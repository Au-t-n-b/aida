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
    """启动时按目录发现注册工厂引用，不实例化（lazy）。

    P3：用「约定优于配置」的目录发现（`discovery.discover_skill_specs`）替代硬编码 `_specs`——
    每个 skill 目录含 `skill.py` 暴露 `get_<name>_skill` 即被发现，**增删 skill = 增删目录**；
    外部 skill 放 `AIDA_SKILLS_PATH` 即可挂载，无需改本文件。

    机制不变：注册的仍是工厂引用（lazy），`build_graph` / HITL / SDUI / 泛化端点一律照旧。
    单个 skill 缺件 / 导入失败时**只跳过它**，不拖垮整个注册表。
    """
    import sys

    from .discovery import discover_skill_specs

    for spec in discover_skill_specs():
        try:
            if spec.builtin:
                mod = _import_builtin_skill(spec.name)
            else:
                mod = _import_external_skill(spec.name, spec.directory)
            registry.register(spec.name, getattr(mod, spec.factory))
        except Exception as e:  # noqa: BLE001 — 缺件/语法错都不应阻断其余 skill
            sys.stderr.write(f"[skills] 跳过 {spec.name}：{type(e).__name__}: {e}\n")


def _import_builtin_skill(name: str):
    """加载内置 skill 模块（`agent.skills.<name>.skill`），保持包内相对导入可用。"""
    import importlib

    return importlib.import_module(f".{name}.skill", package=__name__)


def _import_external_skill(name: str, directory):
    """加载 `AIDA_SKILLS_PATH` 下的外部 skill 包：父目录入 `sys.path`，按包名导入。

    要求外部 skill 为规范包（`<name>/__init__.py` + `<name>/skill.py`），
    这样其内部相对导入（`from .steps import ...`）与绝对导入（`from agent.skills.base ...`）皆可用。
    """
    import importlib
    import sys

    root = str(directory.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module(f"{name}.skill")


_register_all()

__all__ = [
    "BaseSkill", "BaseStep",
    "SkillContext", "SkillState",
    "StepResult", "CheckResult",
    "registry", "SkillRegistry",
    "SkillMetadata", "load_skill_md", "default_skill_md_path",
]
