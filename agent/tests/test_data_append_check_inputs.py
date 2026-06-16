"""data_append 两阶段 HITL：先选追加/跳过，选追加后再上传（可选）并确认。"""
from __future__ import annotations

from pathlib import Path

from agent.skills.base import SkillContext
from agent.skills.zhgk.steps.data_append import DataAppendStep


def _ctx(work_root: Path, project: dict | None = None) -> SkillContext:
    return SkillContext(
        skill_id="zhgk",
        work_root=work_root,
        run_id="run-test",
        project=project or {"intent": "survey_work"},
    )


def test_data_append_phase1_choice_hitl(tmp_path: Path) -> None:
    check = DataAppendStep().check_inputs(_ctx(tmp_path))
    assert check["ok"] is False
    assert check["need_inputs"][0]["id"] == "data_append_choice"


def test_data_append_phase2_after_append_choice(tmp_path: Path) -> None:
    check = DataAppendStep().check_inputs(
        _ctx(tmp_path, {"intent": "survey_work", "data_append_choice": "append"})
    )
    assert check["ok"] is False
    assert check["need_inputs"][0]["id"] == "data_append_upload"
    assert check["need_inputs"][0].get("upload_hint")


def test_data_append_ok_after_confirm(tmp_path: Path) -> None:
    check = DataAppendStep().check_inputs(
        _ctx(
            tmp_path,
            {
                "intent": "survey_work",
                "data_append_choice": "append",
                "data_append_confirmed": True,
            },
        )
    )
    assert check["ok"] is True


def test_data_append_skip_skips_phase2(tmp_path: Path) -> None:
    check = DataAppendStep().check_inputs(
        _ctx(tmp_path, {"intent": "survey_work", "data_append_choice": "skip"})
    )
    assert check["ok"] is True
