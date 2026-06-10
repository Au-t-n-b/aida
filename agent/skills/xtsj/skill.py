"""XtsjSkill · 系统设计（a3 智能网络开局）· dispatch 模型 PoC。

验证「编排器型模块」能落进 aida：dispatch_mode=True 时 build_graph 生成
START → _dispatch →（按 project["command"] 选中的 handler）→ END（见 base.py）。
每条 a3 命令映射成一个 step（key = 命令 id）；PoC 实装 input_check（a3 sd_query_inputs）。
后续命令（地址规划 / 平面 / 互联 / LLD）按 A3-MIGRATION-PLAN §3 追加 step 即可。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..base import BaseSkill
from .sdui import project as _sdui_project
from .steps import InputCheckStep, AddressPlanStep

# a3 sd_* action / 标准命令 → 本 skill 命令（step.key）。
# 前端右面板 start 不带 command 时走 default_command；会话/菜单可带 action/text 经此归一化。
SD_TO_COMMAND: dict[str, str] = {
    "sd_query_inputs":    "input_check",
    "检查输入件是否妥当":   "input_check",
    "检查输入件":          "input_check",
    "sd_batch_ip":        "address_plan",
    "地址规划":            "address_plan",
    "地址批规划":          "address_plan",
    "ip规划":             "address_plan",
}


def _get_xtsj_root() -> Path:
    """系统设计工作区根。优先 env XTSJ_ROOT，否则复用 a3 工作区（含 ProjectData/Input）。
    不存在则创建 —— registry.list_metadata() 会实例化每个 skill，此处禁止 raise。"""
    raw = os.environ.get("XTSJ_ROOT", "").strip()
    root = (
        Path(raw) if raw
        else Path.home() / ".nanobot" / "workspace" / "skills" / "a3-intelligent-network-opening"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


class XtsjSkill(BaseSkill):
    name = "xtsj"
    description = "系统设计（a3 智能网络开局）· 命令分发：输入检查 / 地址规划 / 互联 / LLD（PoC）"
    # 编排形态：命令分发（菜单式），区别于 zhgk/guihua 的线性 DAG
    dispatch_mode = True
    default_command = "input_check"
    # 每条命令一个 handler step（key = 命令 id）；顺序无关（dispatch 按 command 选中）
    steps = [
        InputCheckStep(),
        AddressPlanStep(),
        # 后续：InterconnectStep(...) / LldGenerateStep(...)
    ]
    sdui_projector = staticmethod(_sdui_project)

    def initial_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        """把 start 请求的 command / action / text 归一化为 project["command"]，供 _dispatch_router 选中。"""
        p = dict(payload or {})
        raw = str(p.get("command") or p.get("action") or p.get("text") or "").strip()
        p["command"] = SD_TO_COMMAND.get(raw, raw or self.default_command)
        p.setdefault("project_name", "系统设计 · 智能网络开局")
        return p


def get_xtsj_skill():
    """单例工厂 · 延迟加载 llm + work_root。注册见 agent/skills/__init__.py。"""
    from ...llm import get_llm
    return XtsjSkill(work_root=_get_xtsj_root(), llm_factory=get_llm)
