"""
模板 · 新业务场景 Skill 顶层组装。复制本目录(`_template/`)为 `agent/skills/<name>/`。

全局替换（复制后改这些占位符）：
  xxx           → 你的 skill id（小写下划线，如 modeling / install / deploy）
  Xxx           → 类名前缀（如 Modeling）
  get_xxx_skill → 工厂名
  XXX_ROOT      → 环境变量名（如 MODELING_ROOT），在 agent/.env 设置

配套：A 层 `skills/<name>/SKILL.md`（frontmatter.name 必须与此处 name 一致）。
细则 docs/30_skill开发/31_手写规范/SKILL-DEVELOPMENT.md；照抄速查 docs/10_快速开始/AGENT_QUICKSTART.md。
"""
from __future__ import annotations
import os
from pathlib import Path

from ..base import BaseSkill
from .sdui import project as _sdui_project
from .steps import ExampleStep   # 按业务增减；preflight 预检步可从 zhgk/steps/preflight.py 复制


def _get_xxx_root() -> Path:
    """✏️ 替换为你的模块根目录解析逻辑。
    规范：优先读环境变量 XXX_ROOT，否则用默认路径；不存在则创建。
    ⚠️ 不要 raise —— registry.list_metadata()（/agent/skills 接口）会实例化每个 skill，
    若此处抛异常会让该接口 500（guihua 踩过，改用 mkdir 兜底）。"""
    raw = os.environ.get("XXX_ROOT", "").strip()
    root = Path(raw) if raw else Path.home() / ".nanobot" / "workspace" / "skills" / "xxx"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


class XxxSkill(BaseSkill):
    name = "xxx"                        # ✏️ 必改：与 A 层 SKILL.md frontmatter.name 一致
    description = "<一句话模块描述>"      # 启动时会被 SKILL.md frontmatter.description 覆盖
    # 顺序即 DAG 顺序
    steps = [
        ExampleStep(),
        # <按业务顺序追加更多 step>
    ]
    # SDUI 投影器（填写后 SSE 层自动路由，不需改 main.py）
    sdui_projector = staticmethod(_sdui_project)

    # ── 可选钩子（按需取消注释；全集见 agent/skills/base.py）──
    # file_handler = _xxx_files          # 文件型 HITL：提供 infer_upload_kind/save_upload/check_*
    # step_retry_keys = ["some_step"]    # 仅重试该步（避免补料后重跑前序 LLM）；不可与确认型 HITL 同用
    #
    # def initial_project(self, payload):                 # 补默认值（确认型 HITL 需预置 confirmations）
    #     p = dict(payload or {}); p.setdefault("confirmations", {}); return p
    #
    # def apply_resume_payload(self, project, payload, hitl_step):
    #     # 确认型 HITL：把 ChoiceCard 选择（payload["choice"]）写进 project，
    #     # 因 full_restart 重跑保留 project 而跨重跑存活。参考 GuihuaSkill。
    #     return project


def get_xxx_skill():
    """单例工厂 · 延迟加载 llm + work_root。注册见 agent/skills/__init__.py。"""
    from ...llm import get_llm
    return XxxSkill(work_root=_get_xxx_root(), llm_factory=get_llm)
