"""zhgk HITL 续跑路由。"""
from __future__ import annotations

from agent.skills.zhgk.pipelines.resume import resolve_resume_route_to


def test_filter_build_upload_resumes_to_filter_build() -> None:
    route = resolve_resume_route_to(
        hitl_step="filter_build",
        project={"intent": "survey_work"},
        payload={"uploaded": ["入场评估标准表.xlsx"]},
        prev_state={},
    )
    assert route == "filter_build"
