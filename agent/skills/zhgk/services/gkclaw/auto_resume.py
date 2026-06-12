"""GKCLAW 自动续跑判定。

ingest 只负责入站包落账与结果转写；是否唤醒 LangGraph 由这里根据
ingest 结果 + 任务账本元数据做纯判定，避免把 FastAPI/RUNS 依赖塞进协议层。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .registry import TaskRegistry


def auto_resume_target(*, runtime_dir: Path | str, ingest_result: dict[str, Any]) -> dict[str, Any]:
    """根据 ingest_zip 返回值判断是否应该自动从 wait_survey 续跑。

    返回结构固定包含 should_resume；可续跑时附带 run_id / skill_id / step / task_id。
    """
    task_id = str((ingest_result or {}).get("task_id") or "")
    if not bool((ingest_result or {}).get("merged")):
        return {"should_resume": False, "reason": "ingest_not_merged", "task_id": task_id}
    if not task_id:
        return {"should_resume": False, "reason": "missing_task_id", "task_id": ""}

    task = TaskRegistry(runtime_dir).get(task_id)
    if not task:
        return {"should_resume": False, "reason": "task_not_found", "task_id": task_id}

    run_id = str(task.get("aida_run_id") or "")
    step = str(task.get("aida_resume_step") or "wait_survey")
    skill_id = str(task.get("aida_skill_id") or "zhgk")
    if not run_id:
        return {"should_resume": False, "reason": "missing_run_id", "task_id": task_id}

    return {
        "should_resume": True,
        "run_id": run_id,
        "skill_id": skill_id,
        "step": step,
        "task_id": task_id,
    }
