"""proposal_gen · early.proposal.table_gen LangGraph Skill。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..base import BaseSkill
from .sdui import project as _sdui_project
from .steps import (
    AssembleDeviceTableStep,
    AssembleServiceMaintStep,
    IngestContractStep,
    ParseTechProposalStep,
    ParseTestcasesStep,
    PreflightStep,
    TableGenReleaseStep,
)


def _get_proposal_gen_root() -> Path:
    raw = os.environ.get("PROPOSAL_GEN_ROOT", "").strip()
    if raw:
        return Path(raw).resolve()
    return (Path.home() / ".aida" / "skills" / "proposal_gen").resolve()


class ProposalGenSkill(BaseSkill):
    name = "proposal_gen"
    description = (
        "早期介入·交付预案生成（early.proposal.table_gen 主线）。"
        "读取合同 BOQ 解析结果，解析技术建议书/测试用例，组装各章表并落盘。"
    )
    steps = [
        PreflightStep(),
        IngestContractStep(),
        ParseTechProposalStep(),
        ParseTestcasesStep(),
        AssembleDeviceTableStep(),
        AssembleServiceMaintStep(),
        TableGenReleaseStep(),
    ]
    sdui_projector = staticmethod(_sdui_project)

    def apply_resume_payload(
        self, project: dict[str, Any], payload: dict[str, Any], hitl_step: str
    ) -> dict[str, Any]:
        project = dict(project)
        choice = str(payload.get("choice") or "").strip()
        if hitl_step == "table_gen_release" and choice in ("save_draft", "release"):
            project["release_confirm"] = choice
        return project

    def build_resume_init_state(
        self,
        prev: dict[str, Any],
        project: dict[str, Any],
        hitl_step: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if hitl_step == "table_gen_release":
            extras: dict[str, Any] = {"route_to": "table_gen_release"}
            if prev.get("files"):
                extras["files"] = dict(prev.get("files") or {})
            return extras, project
        return {}, project


def get_proposal_gen_skill():
    from ...llm import get_llm

    return ProposalGenSkill(work_root=_get_proposal_gen_root(), llm_factory=get_llm)
