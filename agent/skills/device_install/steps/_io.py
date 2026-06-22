"""_io · steps 共用的上游文件定位（数据中心 API）与任务指标刷新助手。"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ...base import SkillContext
from .. import dc_io
from .. import dc_paths
from ..services.task_store import get_tasks, load_tasks_state, save_tasks_state, task_summary, iso_now

# 自动步固定时延（步进条 running + 分阶段日志；resume 重放时跳过）
PLAN_RECEIVE_PACE_SEC = 1.8
SN_GENERATE_PACE_SEC = 1.5

DELIVERY_PLAN_KEYWORDS = ("交付计划", "delivery")
POSITION_KEYWORDS = ("设备位置", "位置表", "position")
ARRIVAL_KEYWORDS = ("到货",)


def tasks_state_path(ctx: SkillContext):
    return dc_io.tasks_state_path(ctx)


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


def refresh_task_metrics(ctx: SkillContext) -> dict:
    """读 tasks_state.json → 汇总指标（di_* 命名空间），供 step 返回到 metrics。"""
    path = str(tasks_state_path(ctx))
    st = load_tasks_state(path)
    tasks = get_tasks(path)
    return task_summary(tasks, state=st)


# ── 上游三表定位（数据中心 → scratch；DC 不可达降级挂载盘）──────────────────────

def find_delivery_plan(ctx: SkillContext) -> str | None:
    """定位《交付计划表》（pm-plan/输出结果）。"""
    p = dc_io.fetch_to_scratch(
        ctx,
        dc_paths.delivery_plan_loc(),
        keywords=DELIVERY_PLAN_KEYWORDS,
        exclude=("责任人", "实施计划"),
    )
    return str(p) if p else None


def find_position_table(ctx: SkillContext) -> str | None:
    """定位《设备位置表》（ops-design/输出结果/建模仿真）。"""
    p = dc_io.fetch_to_scratch(ctx, dc_paths.position_loc(), keywords=POSITION_KEYWORDS)
    return str(p) if p else None


def find_arrival_table(ctx: SkillContext) -> str | None:
    """定位《到货信息表》（pm-plan/输入文件）。"""
    p = dc_io.fetch_to_scratch(ctx, dc_paths.arrival_loc(), keywords=ARRIVAL_KEYWORDS)
    return str(p) if p else None


def load_or_parse_delivery_tasks(ctx: SkillContext, *, emit=None) -> list[dict]:
    """任务单一事实源：同 run resume/go_back 复用 tasks_state；冷启动则重解析《交付计划表》。

    冷启动时即使 scratch 上仍有旧 tasks_state.json（上一轮会话残留），也须重解析，
    否则任务 status 可能仍为「已下发」，导致「计划下发」界面无待下发条目。
    """
    from ..services.plan_parser import parse_delivery_plan

    state_path = str(tasks_state_path(ctx))
    if is_pipeline_replay(ctx.project):
        return get_tasks(state_path)

    plan_path = find_delivery_plan(ctx)
    if not plan_path:
        loc = dc_paths.delivery_plan_loc()
        raise RuntimeError(
            f"未找到《交付计划表.xlsx》，请确认上游已交付至数据中心 {loc.describe()}"
            f"（或挂载盘 {loc.disk_dir()}）"
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
