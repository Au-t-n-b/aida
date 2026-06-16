"""zhgk HITL 续跑路由。"""
from __future__ import annotations

from agent.skills.zhgk.pipelines.resume import resolve_resume_route_to
from agent.skills.zhgk.skill import ZhgkSkill


def test_filter_build_upload_resumes_to_filter_build() -> None:
    route = resolve_resume_route_to(
        hitl_step="filter_build",
        project={"intent": "survey_work"},
        payload={"uploaded": ["入场评估标准表.xlsx"]},
        prev_state={},
    )
    assert route == "filter_build"


def test_wait_survey_upload_excludes_stale_assess_steps() -> None:
    skill = ZhgkSkill(work_root=__import__("pathlib").Path("."))
    prev = {
        "steps": [
            {"key": "wait_survey", "status": "completed"},
            {"key": "assess", "status": "completed", "metrics": {"assess_未勘测": 75}},
            {"key": "issue_list", "status": "completed"},
            {"key": "preflight", "status": "completed"},
        ],
    }
    extras, _ = skill.build_resume_init_state(
        prev,
        {"intent": "survey_work"},
        "wait_survey",
        {"uploaded": ["复勘结果表.xlsx"]},
    )
    assert extras.get("route_to") == "assess"
    seeded_keys = {s.get("key") for s in extras.get("steps") or []}
    assert "assess" not in seeded_keys
    assert "issue_list" not in seeded_keys
    assert "preflight" in seeded_keys
