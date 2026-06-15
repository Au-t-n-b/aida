"""
GKCLAW 入站推送 · mailgw 收信后回调 Agent，触发 poll + wait_survey step_retry。

mailgw 只 POST 本模块处理的端点；ingest 仍走 gkclaw.ingest + mailbox（边界 B5）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

GKCLAW_TASK_ID_RE = re.compile(r"task-\d{8,20}-[A-Z0-9]+(?:-\d+)?", re.I)
GKCLAW_MAIL_HINT_RE = re.compile(
    r"task\.(import_ack|result|error)|\[gkclaw\]", re.I
)


def parse_task_id_from_subject(subject: str) -> str | None:
    m = GKCLAW_TASK_ID_RE.search(subject or "")
    return m.group(0) if m else None


def is_gkclaw_mail_subject(subject: str) -> bool:
    return bool(GKCLAW_MAIL_HINT_RE.search(subject or ""))


def should_defer_inbound_retry(plan: dict[str, Any], *, subject: str) -> bool:
    """Result/error 已入站但当前 run 暂不可触发时，允许稍后补触发。"""
    if plan.get("trigger"):
        return False
    if not re.search(r"task\.(result|error)", subject or "", re.I):
        return False
    return str(plan.get("reason") or "") in {
        "no_active_run",
        "run_not_at_wait_survey",
        "run_busy",
    }


def step_has_terminal_record(state: dict[str, Any], step_key: str) -> bool:
    for s in reversed(state.get("steps") or []):
        if s.get("key") == step_key:
            return s.get("status") in ("completed", "hitl", "failed")
    return False


def pipeline_stalled(state: dict[str, Any], step_keys: list[str]) -> str | None:
    """current_step 已指向某步但该步无终态记录 → 返回待续跑 step key。"""
    if state.get("error"):
        return None
    if (state.get("hitl") or {}).get("step"):
        return None
    cur = str(state.get("current_step") or "").strip()
    if not cur or cur not in step_keys:
        return None
    if step_has_terminal_record(state, cur):
        return None
    return cur


def find_run_by_task_id(runs: dict[str, dict], task_id: str) -> str | None:
    tid = task_id.strip()
    if not tid:
        return None
    for run_id, entry in runs.items():
        state = entry.get("state") or {}
        metrics = state.get("metrics") or {}
        if metrics.get("gkclaw_task_id") == tid:
            return run_id
        for s in state.get("steps") or []:
            sm = s.get("metrics") or {}
            if sm.get("gkclaw_task_id") == tid:
                return run_id
    return None


def _survey_table_path(work_root: Path) -> str | None:
    info = work_root / "ProjectData" / "RunTime" / "project_info.json"
    if info.exists():
        try:
            path = json.loads(info.read_text(encoding="utf-8")).get("survey_table_path", "")
            if path and Path(path).exists():
                return path
        except Exception:
            pass
    out = work_root / "ProjectData" / "Output"
    if out.exists():
        tables = sorted(out.glob("*全量勘测结果表*.xlsx"))
        if tables:
            return str(tables[0])
    return None


def poll_gkclaw_inbox(*, work_root: Path) -> dict[str, Any]:
    from agent.skills.zhgk.services.gkclaw.ingest import poll_and_ingest

    runtime = work_root / "ProjectData" / "RunTime"
    input_dir = work_root / "ProjectData" / "Input"
    return poll_and_ingest(
        runtime_dir=runtime,
        input_dir=input_dir,
        survey_table_path=_survey_table_path(work_root),
    )


def resolve_inbound_step(state: dict[str, Any], step_keys: list[str]) -> str | None:
    hitl_step = (state.get("hitl") or {}).get("step") or ""
    if hitl_step:
        return str(hitl_step)
    cur = str(state.get("current_step") or "")
    if cur == "wait_survey" and cur in step_keys:
        return cur
    return pipeline_stalled(state, step_keys)


def plan_inbound_action(
    *,
    runs: dict[str, dict],
    skill_step_keys: list[str],
    step_retry_keys: list[str],
    task_id: str | None,
) -> dict[str, Any]:
    """决定 inbound 后是否 step_retry 以及目标 run/step。"""
    run_id = find_run_by_task_id(runs, task_id) if task_id else None
    if not run_id:
        return {"run_id": None, "step": None, "trigger": False, "reason": "no_active_run"}

    state = runs[run_id]["state"]
    step = resolve_inbound_step(state, skill_step_keys)
    if not step:
        return {
            "run_id": run_id,
            "step": None,
            "trigger": False,
            "reason": "run_not_at_wait_survey",
        }
    if step not in step_retry_keys:
        return {
            "run_id": run_id,
            "step": step,
            "trigger": False,
            "reason": "step_not_retryable",
        }
    task = runs[run_id].get("task")
    if task is not None and not task.done():
        return {
            "run_id": run_id,
            "step": step,
            "trigger": False,
            "reason": "run_busy",
        }
    return {"run_id": run_id, "step": step, "trigger": True, "reason": "ok"}


def should_chain_after_wait_survey(
    *, prev_step: str, state: dict[str, Any], step_retry_keys: list[str]
) -> str | None:
    """GKCLAW 回传后自动推进到下一个非人工等待节点，直到遇到 HITL。"""
    if (state.get("hitl") or {}).get("step") or state.get("error"):
        return None
    nxt = str(state.get("current_step") or "")
    expected = {
        "task_dispatch": "wait_survey",
        "wait_survey": "assess",
        "assess": "issue_list",
        "issue_list": "resurvey_gate",
        "resurvey_gate": "report_gen_run",
        "report_gen_run": "report_distribute",
    }.get(prev_step)
    if nxt == expected and expected in step_retry_keys:
        return expected
    return None
