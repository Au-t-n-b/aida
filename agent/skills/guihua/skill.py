"""
GuihuaSkill · 规划设计（建模仿真）· AIDA 第二个业务场景 Skill

线下移植自 nanobot jmfz 的五阶段流程（BOQ提取→设备确认→创建设备→拓扑确认→拓扑连接）。
验证 1→N 泛化：注册到 registry 即自动拥有图 + /agent/guihua/* 全套端点，未改 main.py/graph.py。

与 zhgk 的差异（第二 skill 压测出的能力面）：
- 确认型 HITL（设备确认/拓扑确认）：check_inputs 返回 need_inputs(ChoiceCard)，
  resume 经 apply_resume_payload 把确认写进 project（full_restart 重跑保留）。
- BOQ 提取走真 LLM + doc_read_xlsx；结果缓存避免重跑重复调模型。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..base import BaseSkill
from . import files as _guihua_files
from .sdui import project as _sdui_project
from .steps import (
    BoqExtractStep,
    DeviceConfirmStep,
    DeviceCreateStep,
    TopoConfirmStep,
    TopoLinkStep,
)

# hitl_step → 确认门名
_GATE_OF_STEP = {"device_confirm": "device", "topo_confirm": "topo"}


def _get_guihua_root() -> Path:
    """规划设计工作区根。优先 env GUIHUA_ROOT，否则复用 nanobot jmfz 工作区
    （已含 ProjectData/Input 等）。不存在则创建，保证 registry.get('guihua') 不抛。"""
    raw = os.environ.get("GUIHUA_ROOT", "").strip()
    root = Path(raw) if raw else Path.home() / ".nanobot" / "workspace" / "skills" / "jmfz"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


class GuihuaSkill(BaseSkill):
    name = "guihua"
    description = "规划设计（建模仿真）· 五阶段 BOQ→设备→创建→拓扑→连接（jmfz 线下移植）"
    steps = [
        BoqExtractStep(),
        DeviceConfirmStep(),
        DeviceCreateStep(),
        TopoConfirmStep(),
        TopoLinkStep(),
    ]
    sdui_projector = staticmethod(_sdui_project)
    file_handler = _guihua_files            # 资料包上传（bundle → Input/）
    # 确认门走 full_restart（boq_extract 有缓存，重跑不重复调 LLM）；无 step_retry。

    def initial_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        p = dict(payload or {})
        p.setdefault("project_name", "规划设计 · 建模仿真")
        p.setdefault("confirmations", {})
        return p

    def apply_resume_payload(
        self, project: dict[str, Any], payload: dict[str, Any], hitl_step: str
    ) -> dict[str, Any]:
        """把确认型 HITL 的选择并入 project（跨 full_restart 存活）。"""
        p = dict(project)
        confs = dict(p.get("confirmations") or {})
        gate = _GATE_OF_STEP.get(hitl_step)
        if gate:
            choice = str(payload.get("choice") or payload.get("value") or "confirm").lower()
            if choice in ("confirm", "confirmed", "ok", "yes", "true"):
                confs[gate] = True
                p.pop("_redo_boq", None)
            else:  # redo / 回退
                confs[gate] = False
                if gate == "device":
                    p["_redo_boq"] = True   # 让 boq_extract 跳过缓存重新抽取
        p["confirmations"] = confs
        return p


def get_guihua_skill():
    """单例工厂 · 延迟加载 llm_factory。注册见 agent/skills/__init__.py。"""
    from ...llm import get_llm
    return GuihuaSkill(work_root=_get_guihua_root(), llm_factory=get_llm)
