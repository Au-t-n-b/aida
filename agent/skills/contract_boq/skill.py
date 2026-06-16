"""contract_boq · early.contract.boq_parse LangGraph Skill。"""
from __future__ import annotations

import os
from pathlib import Path

from ..base import BaseSkill
from .sdui import project as _sdui_project
from .steps import (
    BoqInputCheckStep,
    PreflightStep,
    PublishOutputsStep,
    Stage1ParseStep,
    Stage2DeviceTableStep,
)


def _get_contract_boq_root() -> Path:
    raw = os.environ.get("CONTRACT_BOQ_ROOT", "").strip()
    if raw:
        return Path(raw).resolve()
    return (Path.home() / ".aida" / "skills" / "contract_boq").resolve()


class ContractBoqSkill(BaseSkill):
    name = "contract_boq"
    description = (
        "早期介入·合同 BOQ 解析（early.contract.boq_parse）。"
        "将 BOQ xlsx 经 uniEx clone-boq 解析为 normalized.json 与建模仿真设备信息表，"
        "落盘至早期介入/合同/解析结果 与 输出结果。"
    )
    steps = [
        PreflightStep(),
        BoqInputCheckStep(),
        Stage1ParseStep(),
        Stage2DeviceTableStep(),
        PublishOutputsStep(),
    ]
    sdui_projector = staticmethod(_sdui_project)


def get_contract_boq_skill():
    from ...llm import get_llm

    return ContractBoqSkill(work_root=_get_contract_boq_root(), llm_factory=get_llm)
