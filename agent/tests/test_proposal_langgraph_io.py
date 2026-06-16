"""Tests for early intervention LangGraph path contracts."""
from __future__ import annotations

from pathlib import Path

from agent.constants.project_paths import contract_paths, proposal_paths
from agent.skills.early_io.contracts import CONTRACT_BOQ_STEPS, PROPOSAL_GEN_STEPS
from agent.skills import registry


def test_contract_paths_align_spec() -> None:
    c = contract_paths("")
    assert c["boq_device_parse"] == "早期介入/合同/解析结果/BOQ设备解析原始结果"
    assert c["boq_upload_in"] == "早期介入/合同/输入文件/BOQ"
    assert proposal_paths("")["device_boq_parse"] == c["boq_device_parse"]


def test_step_io_tables_non_empty() -> None:
    assert len(CONTRACT_BOQ_STEPS) >= 4
    assert len(PROPOSAL_GEN_STEPS) >= 5
    assert CONTRACT_BOQ_STEPS[2].step_key == "stage1_parse"
    assert PROPOSAL_GEN_STEPS[1].step_key == "ingest_contract"


def test_skills_register() -> None:
    names = {m["name"] for m in registry.list_metadata()}
    assert "contract_boq" in names
    assert "proposal_gen" in names


def test_contract_boq_graph_builds(monkeypatch) -> None:
    monkeypatch.setenv("AIDA_CHECKPOINT", "memory")
    skill = registry.get("contract_boq")
    graph = skill.build_graph()
    assert graph is not None
    assert len(skill.steps) == 5


def test_proposal_gen_graph_builds(monkeypatch) -> None:
    monkeypatch.setenv("AIDA_CHECKPOINT", "memory")
    skill = registry.get("proposal_gen")
    graph = skill.build_graph()
    assert graph is not None
    assert len(skill.steps) == 7
