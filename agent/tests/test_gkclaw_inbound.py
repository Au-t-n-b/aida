"""GKCLAW inbound 与 pipeline stall 辅助函数单测。"""
from __future__ import annotations

from agent.gkclaw_inbound import (
    find_run_by_task_id,
    parse_task_id_from_subject,
    pipeline_stalled,
    plan_inbound_action,
    should_chain_after_wait_survey,
    should_defer_inbound_retry,
)


def test_parse_task_id_from_subject():
    subj = "[gkclaw] task.result task-20260612-K1903-000002"
    assert parse_task_id_from_subject(subj) == "task-20260612-K1903-000002"


def test_parse_timestamp_task_id_from_subject():
    subj = "[gkclaw] task.result task-20260614191328096-K1903"
    assert parse_task_id_from_subject(subj) == "task-20260614191328096-K1903"


def test_pipeline_stalled_wait_survey():
    state = {
        "current_step": "wait_survey",
        "hitl": {},
        "steps": [
            {"key": "task_dispatch", "status": "completed"},
        ],
    }
    keys = ["task_dispatch", "wait_survey", "assess"]
    assert pipeline_stalled(state, keys) == "wait_survey"


def test_pipeline_stalled_not_when_step_completed():
    state = {
        "current_step": "assess",
        "hitl": {},
        "steps": [
            {"key": "wait_survey", "status": "completed"},
            {"key": "assess", "status": "completed"},
        ],
    }
    assert pipeline_stalled(state, ["wait_survey", "assess"]) is None


def test_find_run_by_task_id():
    runs = {
        "run-abc": {
            "state": {
                "metrics": {"gkclaw_task_id": "task-20260612-K1903-000002"},
                "steps": [],
            }
        }
    }
    assert find_run_by_task_id(runs, "task-20260612-K1903-000002") == "run-abc"


def test_plan_inbound_triggers_wait_survey():
    runs = {
        "run-x": {
            "state": {
                "current_step": "wait_survey",
                "hitl": {},
                "metrics": {"gkclaw_task_id": "task-20260612-K1903-000002"},
                "steps": [{"key": "task_dispatch", "status": "completed"}],
            },
            "task": None,
        }
    }
    plan = plan_inbound_action(
        runs=runs,
        skill_step_keys=["task_dispatch", "wait_survey", "assess"],
        step_retry_keys=["wait_survey", "assess"],
        task_id="task-20260612-K1903-000002",
    )
    assert plan["trigger"] is True
    assert plan["run_id"] == "run-x"
    assert plan["step"] == "wait_survey"


def test_should_chain_wait_survey_to_assess():
    state = {
        "current_step": "assess",
        "hitl": {},
        "error": None,
    }
    assert should_chain_after_wait_survey(
        prev_step="wait_survey",
        state=state,
        step_retry_keys=["wait_survey", "assess"],
    ) == "assess"


def test_should_chain_wait_survey_to_assess_when_current_step_stale():
    """复勘第 N 轮上传后 current_step 可能仍指向下游，仍应链到 assess。"""
    state = {
        "current_step": "issue_list",
        "hitl": {},
        "steps": [
            {"key": "wait_survey", "status": "completed", "metrics": {"survey_round": 3}},
            {"key": "assess", "status": "completed"},
        ],
    }
    assert should_chain_after_wait_survey(
        prev_step="wait_survey",
        state=state,
        step_retry_keys=["wait_survey", "assess", "issue_list"],
    ) == "assess"


def test_should_chain_assess_to_issue_list_after_inbound():
    state = {
        "current_step": "issue_list",
        "hitl": {},
        "error": None,
    }
    assert should_chain_after_wait_survey(
        prev_step="assess",
        state=state,
        step_retry_keys=["wait_survey", "assess", "issue_list", "resurvey_gate"],
    ) == "issue_list"


def test_should_chain_issue_list_to_resurvey_gate_after_inbound():
    state = {
        "current_step": "resurvey_gate",
        "hitl": {},
        "error": None,
    }
    assert should_chain_after_wait_survey(
        prev_step="issue_list",
        state=state,
        step_retry_keys=["wait_survey", "assess", "issue_list", "resurvey_gate"],
    ) == "resurvey_gate"


def test_inbound_run_busy_is_deferred_for_later_retry():
    plan = {
        "run_id": "run-x",
        "step": "wait_survey",
        "trigger": False,
        "reason": "run_busy",
    }

    assert should_defer_inbound_retry(plan, subject="[gkclaw] task.result task-20260612-K1903-000002")


def test_inbound_import_ack_is_not_deferred():
    plan = {
        "run_id": "run-x",
        "step": "wait_survey",
        "trigger": False,
        "reason": "run_busy",
    }

    assert not should_defer_inbound_retry(plan, subject="[gkclaw] task.import_ack task-20260612-K1903-000002")
