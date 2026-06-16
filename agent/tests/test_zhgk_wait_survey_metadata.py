import json
from pathlib import Path

from openpyxl import Workbook

from agent.skills.base import SkillContext
from agent.skills.zhgk.services.gkclaw.registry import TaskRegistry
from agent.skills.zhgk.steps.wait_survey import (
    _build_app_wait_label,
    _build_survey_merge_metadata,
    _is_initial_app_mode,
)


def test_build_app_wait_label_is_concise():
    assert _build_app_wait_label("task-20260614-K1903-0001") == "等待现场 App 勘测回传"


def test_build_survey_merge_metadata_uses_mailgw_as_video_survey():
    meta = _build_survey_merge_metadata(
        {"source": "mailgw", "completed_at": "2026-06-14 18:00:00"},
        2,
        fallback_time="2026-06-14 18:01:00",
    )

    assert meta == {
        "survey_result_source": "第2次视频工勘",
        "survey_result_time": "2026-06-14 18:00:00",
        "survey_result_source_type": "video",
    }


def test_build_survey_merge_metadata_defaults_to_manual_upload():
    meta = _build_survey_merge_metadata(
        {},
        1,
        fallback_time="2026-06-14 17:35:00",
    )

    assert meta == {
        "survey_result_source": "第1次手动上传",
        "survey_result_time": "2026-06-14 17:35:00",
        "survey_result_source_type": "manual",
    }


def _write_survey_table(path: Path, latest_result: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["序号", "检查内容", "最新检查结果"])
    ws.append([1, "园区入口道路满足要求", latest_result])
    wb.save(path)
    wb.close()


def test_completed_initial_app_task_with_merged_table_exits_wait_mode(tmp_path: Path):
    work_root = tmp_path
    runtime_dir = work_root / "ProjectData" / "RunTime"
    output_dir = work_root / "ProjectData" / "Output"
    input_dir = work_root / "ProjectData" / "Input"
    runtime_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    input_dir.mkdir(parents=True)

    table = output_dir / "ACT001_全量勘测结果表.xlsx"
    _write_survey_table(table, "现场确认满足")
    task_id = "task-20260615012202504-K1903"
    (runtime_dir / "project_info.json").write_text(
        json.dumps({"gkclaw_task_id": task_id, "survey_table_path": str(table)}, ensure_ascii=False),
        encoding="utf-8",
    )
    reg = TaskRegistry(runtime_dir)
    reg.create_task(
        task_id=task_id,
        task_payload={"task_name": "现场勘测", "assignees": []},
        zip_path="outbox/task.zip",
        table_fingerprint="sha256:test",
        project={"project_code": "K1903"},
        dry_run=False,
    )
    reg.set_state(task_id, "completed")
    ctx = SkillContext(
        skill_id="zhgk",
        work_root=work_root,
        run_id="run-test",
        project={"dispatch_decision": "dispatch"},
    )

    assert _is_initial_app_mode(ctx) is False
