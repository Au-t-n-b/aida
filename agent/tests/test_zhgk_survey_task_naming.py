"""survey_context / 任务包命名。"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from agent.skills.zhgk.services.gkclaw.mapping import build_task_payload
from agent.skills.zhgk.services.survey_context import format_survey_task_name, resolve_survey_context
from agent.skills.zhgk.services.survey_task_package import build_survey_task_package


def test_format_survey_task_name_with_jd_project():
    name = format_survey_task_name(
        project_name="京东三期",
        room_name="401",
    )
    assert name == "京东三期·401 现场勘测"


def test_zhgk_initial_project_uses_payload_name():
    from agent.skills.zhgk.skill import ZhgkSkill
    from pathlib import Path

    skill = ZhgkSkill(work_root=Path("."))
    proj = skill.initial_project({
        "project_name": "京东三期",
        "project_code": "K1903",
        "room_name": "401",
    })
    assert proj["project_name"] == "京东三期"
    assert proj["project_code"] == "K1903"
    assert proj["room_name"] == "401"


def test_format_survey_task_name_with_project_and_room():
    name = format_survey_task_name(
        project_name="智算 Q3 · 客户甲一期",
        room_name="A 机房",
    )
    assert name == "智算 Q3 · 客户甲一期·A 机房 现场勘测"


def test_resolve_survey_context_prefers_project_over_info():
    ctx = resolve_survey_context(
        {"project_name": "当前项目", "room_name": "B 机房", "activity_id": "ACT002"},
        {"project_name": "旧项目", "room_name": "旧机房", "activity_id": "ACT001"},
    )
    assert ctx["project_name"] == "当前项目"
    assert ctx["room_name"] == "B 机房"
    assert ctx["activity_id"] == "ACT002"


def test_resolve_survey_context_falls_back_to_english_info_keys():
    ctx = resolve_survey_context(
        {},
        {"project_name": "智算 Q3 · 客户甲一期", "room_name": "C 机房", "activity_id": "ACT001"},
    )
    assert ctx["project_name"] == "智算 Q3 · 客户甲一期"
    assert ctx["room_name"] == "C 机房"


def test_build_survey_task_package_manifest_task_name(tmp_path: Path):
    table = tmp_path / "survey.xlsx"
    table.write_bytes(b"xlsx")
    zip_path = build_survey_task_package(
        str(table),
        str(tmp_path / "out"),
        project_name="智算 Q3 · 客户甲一期",
        room_name="A 机房",
        activity_id="ACT001",
    )
    assert "ACT001_智算 Q3 · 客户甲一期_A 机房_勘测任务包.zip" in zip_path.replace("\\", "/")
    with zipfile.ZipFile(zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["task_name"] == "智算 Q3 · 客户甲一期·A 机房 现场勘测"


def test_build_task_payload_task_name_matches_project_room():
    payload = build_task_payload(
        task_id="task-001",
        rows=[{
            "序号": 1,
            "细分场景": "硬装",
            "勘测要素": "接地",
            "项目": "接地线",
            "检查内容": "检查",
            "勘测方法": "现场勘测",
        }],
        base_items=[],
        project={
            "project_name": "智算 Q3 · 客户甲一期",
            "room_name": "A 机房",
            "activity_id": "ACT001",
        },
        assignees=[{"surveyor_name": "张三", "surveyor_code": "S001"}],
    )
    assert payload["task_name"] == "智算 Q3 · 客户甲一期·A 机房 现场勘测"
