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
  apply_resume_payload 把确认写进 project（full_restart 重跑保留）。
"""
from __future__ import annotations

from typing import Any

from ..base import BaseSkill
from . import files as _guihua_files
from .bridge import get_guihua_root
from .path_config import get_input_dir, get_output_dir, get_parse_dir
from .sdui import project as _sdui_project
from .steps import (
    AdaptBuildStep,
    DataConfirmStep,
    ComboCreateStep,
    CabinetMoveStep,
    HandoffStep,
)

# hitl_step → 确认门名（四道门：数据准确 / 创建超节点 / 机柜落位 / 生成参数面）
_GATE_OF_STEP = {
    "data_confirm": "data",
    "combo_create": "combo",
    "cabinet_move": "move",
    "handoff": "handoff",
}


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
    file_handler = _guihua_files            # 资料包上传（设备信息表/机房机柜表 → 输入文件/）
    # 确认门走 full_restart（adapt_build 确定性重生成）；副作用步 sentinel 按 run_id 幂等。

    def prepare_work_root(self) -> None:
        """按规范初始化三个标准子目录（输入文件 / 解析结果 / 输出结果/建模仿真）。"""
        get_input_dir()
        get_parse_dir()
        get_output_dir()

    def initial_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        p = dict(payload or {})
        p.setdefault("project_name", "规划设计 · 建模仿真")
        p["confirmations"] = {}   # 新 run 强制重置确认状态，不复用旧确认
        return p

    def apply_resume_payload(
        self, project: dict[str, Any], payload: dict[str, Any], hitl_step: str
    ) -> dict[str, Any]:
        """把确认型 HITL 的选择并入 project（跨 full_restart 存活）。

        四道门顺序：data < combo < move < handoff。redo 标记在 apply_resume 中写入，
        供 cabinet_move / handoff 等步在需要时强制重跑副作用。
        """
        p = dict(project)
        confs = dict(p.get("confirmations") or {})
        gate = _GATE_OF_STEP.get(hitl_step)
        if not gate:
            p["confirmations"] = confs
            return p

        choice = str(payload.get("choice") or payload.get("value") or "confirm").lower()
        confirmed = choice in ("confirm", "confirmed", "ok", "yes", "true")
        if confirmed:
            confs[gate] = True
            # 下一道门确认 = 上一副作用步已跑完，清其 redo（防反复重发）
            if gate == "move":
                p.pop("_redo_create", None)
            elif gate == "handoff":
                p.pop("_redo_move", None)
        else:  # 否 / 回退：本门不放行，并清空其下游确认 + 标记下游重跑
            confs[gate] = False
            if gate == "data":
                for g in ("combo", "move", "handoff"):
                    confs[g] = False
                p["_redo_create"] = True
                p["_redo_move"] = True
                p["_redo_handoff"] = True
            elif gate == "combo":
                for g in ("move", "handoff"):
                    confs[g] = False
                p["_redo_create"] = True
            elif gate == "move":
                confs["handoff"] = False
                p["_redo_move"] = True
            elif gate == "handoff":
                p["_redo_handoff"] = True
        p["confirmations"] = confs
        return p


def get_guihua_skill():
    """单例工厂 · 延迟加载 llm_factory。注册见 agent/skills/__init__.py。"""
    from ...llm import get_llm
    return GuihuaSkill(work_root=get_guihua_root(), llm_factory=get_llm)
