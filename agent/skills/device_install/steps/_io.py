"""_io · steps 共用的输入文件定位与任务指标刷新助手。"""
from __future__ import annotations

from pathlib import Path

from ...base import SkillContext
from ..services.task_store import get_tasks, load_tasks_state, task_summary


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


def refresh_task_metrics(ctx: SkillContext) -> dict:
    """读 tasks_state.json → 汇总指标（di_* 命名空间），供 step 返回到 metrics。"""
    path = str(tasks_state_path(ctx))
    st = load_tasks_state(path)
    tasks = get_tasks(path)
    return task_summary(tasks, state=st)
