"""proposal_gen · early.proposal.table_gen LangGraph Skill。"""
from __future__ import annotations

from typing import Any

from agent.config import BUSINESS_ROOT

from ..base import BaseSkill
from ..early_io.paths import ensure_proposal_ipo_dirs
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

    def prepare_work_root(self) -> None:
        """Steps resolve per-project paths via early_io; no ProjectData subtree."""
        pass

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

    return ProposalGenSkill(work_root=BUSINESS_ROOT, llm_factory=get_llm)


def ensure_proposal_gen_dirs(project: dict[str, Any] | None) -> None:
    """Public helper for preflight / external callers."""
    ensure_proposal_ipo_dirs(project)
