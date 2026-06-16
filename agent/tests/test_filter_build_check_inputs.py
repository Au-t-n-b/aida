"""filter_build 前置检查：两张底表共用一次 HITL。"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.skills.zhgk.steps.filter_build import FilterBuildStep
from agent.skills.base import SkillContext


def _ctx(work_root: Path) -> SkillContext:
    return SkillContext(
        skill_id="zhgk",
        work_root=work_root,
        run_id="run-test",
        project={"intent": "survey_work", "generation_cooling": "A3-液冷"},
    )


def test_filter_build_hitl_requires_both_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = tmp_path / "zhgk"
    work.mkdir()
    monkeypatch.setenv("ZHGK_ROOT", str(work))

    check = FilterBuildStep().check_inputs(_ctx(work))
    assert check["ok"] is False
    assert "ProjectData/Template/入场评估标准表.xlsx" in check["missing"]
    assert "ProjectData/Template/工勘常见高风险库.xlsx" in check["missing"]


def test_filter_build_ok_when_both_templates_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = tmp_path / "zhgk"
    for rel in (
        "ProjectData/Template/入场评估标准表.xlsx",
        "ProjectData/Template/工勘常见高风险库.xlsx",
    ):
        p = work / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    monkeypatch.setenv("ZHGK_ROOT", str(work))

    check = FilterBuildStep().check_inputs(_ctx(work))
    assert check["ok"] is True
    assert check["missing"] == []
