"""_io · steps 共用的输入文件定位与任务指标刷新助手。"""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...base import SkillContext
from ..services._common import as_str
from ..services.dispatch_plan_parser import (
    resolve_dispatch_plan_path,
    parse_dispatch_plan_with_sn,
    save_sn_pool,
)
from ..services.source_files import get_source_dir, sync_dispatch_plan_to_input
from ..services.task_store import get_tasks, load_tasks_state, save_tasks_state, task_summary, iso_now

# 同 run 内 re-parse 时按 id 保留的运行态字段（新会话 merge_runtime=False 时不保留）
_TASK_RUNTIME_KEYS = ("status", "progress_pct", "progress_records")
_STATE_PRESERVE_KEYS = ("last_dispatch_tasks", "dispatched_at", "esn_collected_at")

# 自动步固定时延（步进条 running + 分阶段日志；resume 重放时 preflight/plan_receive 跳过）
PREFLIGHT_PACE_SEC = 1.2
PLAN_RECEIVE_PACE_SEC = 1.8
SN_GENERATE_PACE_SEC = 1.5


def find_input(ctx: SkillContext, *keywords: str, exclude: tuple[str, ...] = ()) -> str | None:
    """在 Input/ 找文件名（不含扩展名也可）含全部 keywords、且不含任一 exclude 的首个 .xlsx。"""
    if not ctx.input_dir.exists():
        return None
    for p in sorted(ctx.input_dir.glob("*.xlsx")):
        name = p.name
        if any(k.lower() in name.lower() for k in keywords) and not any(
            e.lower() in name.lower() for e in exclude
        ):
            return str(p)
    return None


def find_inputs(ctx: SkillContext, *keywords: str) -> list[str]:
    """在 Input/ 找所有文件名含任一 keyword 的 .xlsx。"""
    if not ctx.input_dir.exists():
        return []
    out: list[str] = []
    for p in sorted(ctx.input_dir.glob("*.xlsx")):
        if any(k.lower() in p.name.lower() for k in keywords):
            out.append(str(p))
    return out


def tasks_state_path(ctx: SkillContext) -> Path:
    return ctx.runtime_dir / "tasks_state.json"


def should_merge_runtime_on_reparse(project: dict[str, Any]) -> bool:
    """同 run resume/go_back 重放时合并旧 tasks_state；全新启动不合并（避免旧会话缓存）。"""
    return is_pipeline_replay(project)


def is_pipeline_replay(project: dict[str, Any]) -> bool:
    """同 run resume/go_back 重放（非冷启动）。"""
    return bool(
        project.get("dispatch_rows")
        or project.get("dispatch_confirmed")
        or project.get("esn_rows")
        or project.get("tasks_confirmed")
        or project.get("principal_rows")
    )


def staged_cold_start_pace(
    project: dict[str, Any],
    emit: Callable[[str], None],
    *,
    total_sec: float,
    stages: list[str],
    skip_on_replay: bool = True,
) -> None:
    """分阶段 emit + sleep，让步进条可见推进；skip_on_replay 时 resume 重放跳过。"""
    if (skip_on_replay and is_pipeline_replay(project)) or total_sec <= 0 or not stages:
        return
    gap = total_sec / len(stages)
    for msg in stages:
        emit(msg)
        time.sleep(gap)


def reload_tasks_from_plan(ctx: SkillContext, *, merge_runtime: bool = True) -> list[dict]:
    """从上游实施计划 xlsx 重新解析，刷新 tasks_state.json + sn_pool.json。

    先 sync 源目录 → Input/，再 parse；merge_runtime=True 时按 task id 保留本 run 内下发/进度态。
    """
    sync_dispatch_plan_to_input(get_source_dir(ctx.work_root, ctx.project), ctx.input_dir)
    plan_path = resolve_dispatch_plan_path(ctx.input_dir)
    if not plan_path:
        return []

    tasks, sn_rows = parse_dispatch_plan_with_sn(plan_path)
    state_path = str(tasks_state_path(ctx))
    old_st = load_tasks_state(state_path) if merge_runtime else {"tasks": []}

    if merge_runtime:
        old_by_id = {
            as_str(t.get("id")): t
            for t in (old_st.get("tasks") or [])
            if isinstance(t, dict) and as_str(t.get("id"))
        }
        for t in tasks:
            old = old_by_id.get(as_str(t.get("id")))
            if not old:
                continue
            for k in _TASK_RUNTIME_KEYS:
                if k in old:
                    t[k] = old[k]

    new_st: dict[str, Any] = {
        "loaded_at": iso_now(),
        "source_plan": str(plan_path),
        "tasks": tasks,
    }
    if merge_runtime:
        for k in _STATE_PRESERVE_KEYS:
            if k in old_st:
                new_st[k] = old_st[k]

    save_tasks_state(state_path, new_st)
    save_sn_pool(ctx.runtime_dir / "sn_pool.json", source=str(plan_path), rows=sn_rows)
    return tasks


def refresh_task_metrics(ctx: SkillContext) -> dict:
    """读 tasks_state.json → 汇总指标（di_* 命名空间），供 step 返回到 metrics。"""
    path = str(tasks_state_path(ctx))
    st = load_tasks_state(path)
    tasks = get_tasks(path)
    return task_summary(tasks, state=st)
