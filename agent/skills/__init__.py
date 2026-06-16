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
from pathlib import Path

from .base import BaseSkill, BaseStep, SkillContext, SkillState, StepResult, CheckResult
from ._registry import registry, SkillRegistry
from ._loader import SkillMetadata, load_skill_md, default_skill_md_path


def discover_skill_names(skills_dir: Path | None = None) -> list[str]:
    """目录自动发现的 skill 名（运行时单一真相）。

    规则：agent/skills/<name>/ 是**目录**、非下划线/点开头（跳过 `_template`/`__pycache__`）、
    且含 skill.py。被 `_register_all`（启动注册）与 `hotreload`（运行时热重载/重扫）共用，
    保证"哪些算 skill"只有一处定义。lint_module_boundaries.py 另有一份 venv-free 文本版镜像本规则。
    """
    base = skills_dir or Path(__file__).resolve().parent
    out: list[str] = []
    for child in sorted(base.iterdir()):
        name = child.name
        if child.is_dir() and name[0] not in "_." and (child / "skill.py").is_file():
            out.append(name)
    return out


def _register_all():
    """启动时按目录自动发现注册所有 skill 工厂（工厂名约定 `get_<dirname>_skill`，注册 id = 目录名）。

    加一个 skill = 新建 agent/skills/<name>/，**无需改本文件**（VIBECODING_HARNESS.md §7 · P1a）。
    单个 skill 导入失败 / 缺工厂时**只跳过它**，不拖垮整个注册表。
    运行中热插拔（零重启）见 agent/skills/hotreload.py。
    """
    import importlib
    import sys

    for name in discover_skill_names():
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
    "discover_skill_names",
]
