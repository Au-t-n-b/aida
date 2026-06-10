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
    """启动时只注册工厂引用，不实例化（lazy）。

    单个 skill 缺目录 / 导入失败时**只跳过它**，不拖垮整个注册表——
    否则一个未提交的可选 skill（如 device_install）会让全部 skill 不可用。
    """
    import sys

    # (skill 名, "模块路径:工厂函数名")
    _specs = [
        ("zhgk",           ".zhgk.skill:get_zhgk_skill"),
        ("guihua",         ".guihua.skill:get_guihua_skill"),
        ("xtsj",           ".xtsj.skill:get_xtsj_skill"),
        ("device_install", ".device_install.skill:get_device_install_skill"),
    ]
    import importlib
    for name, target in _specs:
        mod_path, factory_name = target.split(":")
        try:
            mod = importlib.import_module(mod_path, package=__name__)
            registry.register(name, getattr(mod, factory_name))
        except Exception as e:  # noqa: BLE001 — 缺件/语法错都不应阻断其余 skill
            sys.stderr.write(f"[skills] 跳过 {name}：{type(e).__name__}: {e}\n")


_register_all()

__all__ = [
    "BaseSkill", "BaseStep",
    "SkillContext", "SkillState",
    "StepResult", "CheckResult",
    "registry", "SkillRegistry",
    "SkillMetadata", "load_skill_md", "default_skill_md_path",
]
