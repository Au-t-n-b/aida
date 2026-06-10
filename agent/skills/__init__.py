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
    """启动时只注册工厂引用，不实例化（lazy）"""
    from .zhgk.skill import get_zhgk_skill
    registry.register("zhgk", get_zhgk_skill)

    from .guihua.skill import get_guihua_skill
    registry.register("guihua", get_guihua_skill)

    from .xtsj.skill import get_xtsj_skill
    registry.register("xtsj", get_xtsj_skill)

    from .device_install.skill import get_device_install_skill
    registry.register("device_install", get_device_install_skill)


_register_all()

__all__ = [
    "BaseSkill", "BaseStep",
    "SkillContext", "SkillState",
    "StepResult", "CheckResult",
    "registry", "SkillRegistry",
    "SkillMetadata", "load_skill_md", "default_skill_md_path",
]
