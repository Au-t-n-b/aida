"""
GuihuaSkill · 规划设计（建模仿真）· AIDA 第二个业务场景 Skill

线下移植自 Desktop/skill/jmfz 的建模仿真流程（规划设计前半段）：
  设备适配 → 数据确认 → 创建超节点 → 机柜落位 → 移交设备安装。
验证 1→N 泛化：注册到 registry 即自动拥有图 + /agent/guihua/* 全套端点，未改 main.py/graph.py。

核心能力（对应 jmfz api_adapt + auto_dragd）：
- 设备适配（adapt_build）：确定性解析 + 调仿真 API（queryDeviceModel/querySlotMapping）匹配
  型号/板卡评分 → 生成适配信息表（非 LLM）。无内网 dry-run 时复用 fixture 兜底。
- 超节点创建/机柜落位（combo_create/cabinet_move）：batchCreateCombo×5 + batchMoveNodes×162，
  统一走 services/sim_api.py（铁律④：唯一出口 + 留痕 + 默认 dry-run）。
- 三道确认型 HITL（data/move/handoff）：check_inputs 返回 need_inputs(ChoiceCard)，resume 经
  apply_resume_payload 把确认写进 project（full_restart 重跑保留）；副作用步用 sentinel 幂等。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..base import BaseSkill
from . import files as _guihua_files
from .sdui import project as _sdui_project
from .steps import (
    AdaptBuildStep,
    DataConfirmStep,
    ComboCreateStep,
    CabinetMoveStep,
    HandoffStep,
)

# hitl_step → 确认门名（三道门：数据准确 / 已刷新落位 / 移交设备安装）
_GATE_OF_STEP = {"data_confirm": "data", "cabinet_move": "move", "handoff": "handoff"}
# 选 redo 时要重跑的副作用步标记（data 改了适配表 → 需重新创建/落位）
_REDO_FLAG_OF_GATE = {"data": "_redo_create", "move": "_redo_move"}


def _get_guihua_root() -> Path:
    """规划设计工作区根。优先 env GUIHUA_ROOT，否则复用 nanobot jmfz 工作区
    （已含 ProjectData/Input 等）。不存在则创建，保证 registry.get('guihua') 不抛。"""
    raw = os.environ.get("GUIHUA_ROOT", "").strip()
    root = Path(raw) if raw else Path.home() / ".nanobot" / "workspace" / "skills" / "jmfz"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


class GuihuaSkill(BaseSkill):
    name = "guihua"
    description = "规划设计（建模仿真）· 设备适配→数据确认→创建超节点→机柜落位→移交设备安装（jmfz 线下移植）"
    steps = [
        AdaptBuildStep(),
        DataConfirmStep(),
        ComboCreateStep(),
        CabinetMoveStep(),
        HandoffStep(),
    ]
    sdui_projector = staticmethod(_sdui_project)
    file_handler = _guihua_files            # 资料包上传（设备信息表/机房机柜表 → Input/）
    # 确认门走 full_restart（adapt_build 确定性重生成，副作用步用 sentinel 幂等防重复）；无 step_retry。

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
                for f in ("_redo_create", "_redo_move"):
                    p.pop(f, None)
            else:  # redo / 回退
                confs[gate] = False
                if gate == "data":
                    # 重做适配表 → 下游需重新创建/落位，并清空后续确认
                    p["_redo_create"] = True
                    p["_redo_move"] = True
                    confs["move"] = False
                    confs["handoff"] = False
                elif gate == "move":
                    p["_redo_move"] = True   # 让 cabinet_move 从头重发
        p["confirmations"] = confs
        return p


def get_guihua_skill():
    """单例工厂 · 延迟加载 llm_factory。注册见 agent/skills/__init__.py。"""
    from ...llm import get_llm
    return GuihuaSkill(work_root=_get_guihua_root(), llm_factory=get_llm)
