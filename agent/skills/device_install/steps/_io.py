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
from ..path_config import get_upstream_input_dir
from ..services.source_files import get_source_dir, sync_dispatch_plan_to_input
from ..services.task_store import get_tasks, load_tasks_state, save_tasks_state, task_summary, iso_now

# 同 run 内 re-parse 时按 id 保留的运行态字段（新会话 merge_runtime=False 时不保留）
_TASK_RUNTIME_KEYS = ("status", "progress_pct", "progress_records")
_STATE_PRESERVE_KEYS = ("last_dispatch_tasks", "dispatched_at", "esn_collected_at")

# 自动步固定时延（步进条 running + 分阶段日志；resume 重放时跳过）
PLAN_RECEIVE_PACE_SEC = 1.8
SN_GENERATE_PACE_SEC = 1.5


def _skip_input_xlsx(name: str) -> bool:
    """跳过 Excel 打开时产生的锁文件 / 临时文件（~$xxx.xlsx）。"""
    n = name.strip()
    return n.startswith("~$") or n.startswith(".~")


def _input_search_dirs(ctx: SkillContext) -> list[Path]:
    """输入 xlsx 搜索目录：上游 SSOT 目录 + HITL 上传的 ProjectData/Input/（去重）。"""
    seen: set[Path] = set()
    dirs: list[Path] = []
    for d in (get_upstream_input_dir(ctx.project), ctx.input_dir):
        resolved = d.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        dirs.append(resolved)
    return dirs


def find_input(ctx: SkillContext, *keywords: str, exclude: tuple[str, ...] = ()) -> str | None:
    """在上游输入目录找文件名含任一 keyword、且不含任一 exclude 的首个 .xlsx。"""
    for search_dir in _input_search_dirs(ctx):
        if not search_dir.exists():
            continue
        for p in sorted(search_dir.glob("*.xlsx")):
            name = p.name
            if _skip_input_xlsx(name):
                continue
            if any(k.lower() in name.lower() for k in keywords) and not any(
                e.lower() in name.lower() for e in exclude
            ):
                return str(p)
    return None


def find_inputs(ctx: SkillContext, *keywords: str) -> list[str]:
    """在上游输入目录找所有文件名含任一 keyword 的 .xlsx。"""
    out: list[str] = []
    seen_paths: set[str] = set()
    for search_dir in _input_search_dirs(ctx):
        if not search_dir.exists():
            continue
        for p in sorted(search_dir.glob("*.xlsx")):
            if _skip_input_xlsx(p.name):
                continue
            if any(k.lower() in p.name.lower() for k in keywords):
                ps = str(p)
                if ps not in seen_paths:
                    seen_paths.add(ps)
                    out.append(ps)
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


# ── 交付计划表（新流水线输入源）──────────────────────────────────────────────

DELIVERY_PLAN_KEYWORDS = ("交付计划", "delivery")
POSITION_KEYWORDS = ("设备位置", "位置表", "position")
ARRIVAL_KEYWORDS = ("到货",)


def find_delivery_plan(ctx: SkillContext) -> str | None:
    """在 Input/ 定位《交付计划表.xlsx》。"""
    return find_input(ctx, *DELIVERY_PLAN_KEYWORDS, exclude=("责任人", "实施计划"))


def find_position_table(ctx: SkillContext) -> str | None:
    return find_input(ctx, *POSITION_KEYWORDS)


def find_arrival_table(ctx: SkillContext) -> str | None:
    return find_input(ctx, *ARRIVAL_KEYWORDS)


def load_or_parse_delivery_tasks(ctx: SkillContext, *, emit=None) -> list[dict]:
    """任务单一事实源：同 run resume/go_back 复用 tasks_state；冷启动则重解析《交付计划表》。

    冷启动时即使磁盘上仍有旧 tasks_state.json（上一轮会话残留），也须重解析，
    否则任务 status 可能仍为「已下发」，导致「计划下发」界面无待下发条目。
    """
    from ..services.plan_parser import parse_delivery_plan

    state_path = str(tasks_state_path(ctx))
    if is_pipeline_replay(ctx.project):
        return get_tasks(state_path)

    plan_path = find_delivery_plan(ctx)
    if not plan_path:
        raise RuntimeError(
            f"未找到《交付计划表.xlsx》，请将上游交付计划表放入：{get_upstream_input_dir(ctx.project)}"
        )
    tasks = parse_delivery_plan(plan_path)
    if not tasks:
        raise RuntimeError(
            "未从《交付计划表》解析到任何 7.x 安装任务，请检查 ACTIVITY_ID 列。"
        )
    save_tasks_state(state_path, {"loaded_at": iso_now(), "source_plan": plan_path, "tasks": tasks})
    if emit:
        emit(f"[plan] ✓ 已解析《交付计划表》→ {len(tasks)} 条三级安装任务")
    return tasks
