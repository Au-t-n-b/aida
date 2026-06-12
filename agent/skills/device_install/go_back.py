"""
go_back · 主建设流水线「返回上一步」（skill 内 run-patch 实现，不改框架/前端）。

通过 SDUI 中 submitMode=run-patch / stepId=go_back 的按钮触发；
原地更新 run_state + 磁盘任务态，并重建目标步 HITL（保留 project 内已填草稿）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..base import SkillContext
from .pipeline import DI_STEP_NAMES, DI_STEP_ORDER
from .steps.task_dispatch import TaskDispatchStep
from .steps.esn_fill import EsnFillStep
from .services.task_store import load_tasks_state, save_tasks_state, task_summary

# 主建设流：当前步 → 返回目标步（仅含可交互回退）
_BACK_TO: dict[str, str] = {
    "esn_fill": "task_dispatch",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _step_index(key: str) -> int:
    try:
        return DI_STEP_ORDER.index(key)
    except ValueError:
        return 0


def _steps_by_key(state: dict[str, Any]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for s in state.get("steps") or []:
        if isinstance(s, dict) and s.get("key"):
            out[s["key"]] = s
    return out


def _past_dispatch(state: dict[str, Any]) -> bool:
    """是否已走过计划下发（sn / esn 至少执行过一次）。"""
    by = _steps_by_key(state)
    return (
        by.get("sn_generate", {}).get("status") == "completed"
        or by.get("esn_fill", {}).get("status") in ("completed", "hitl")
    )


def _current_interactive_step(state: dict[str, Any]) -> str:
    hitl_step = (state.get("hitl") or {}).get("step") or ""
    if hitl_step in DI_STEP_ORDER:
        return hitl_step
    return ""


def resolve_go_back_target(state: dict[str, Any]) -> str | None:
    """解析可回退目标步；不可回退时返回 None。"""
    cur = _current_interactive_step(state)
    if not cur:
        return None
    if cur == "task_dispatch" and not _past_dispatch(state):
        return None
    return _BACK_TO.get(cur)


def can_go_back(state: dict[str, Any]) -> bool:
    return resolve_go_back_target(state) is not None


def _ctx(work_root: Path, run_state: dict[str, Any]) -> SkillContext:
    return SkillContext(
        skill_id=run_state.get("skill_id") or "device_install",
        work_root=work_root,
        run_id=run_state.get("run_id") or "",
        project=dict(run_state.get("project") or {}),
    )


def _revert_dispatch_batch(work_root: Path) -> int:
    """将上一轮下发批次的任务恢复为「待下发」，便于重新勾选。"""
    path = work_root / "ProjectData" / "RunTime" / "tasks_state.json"
    st = load_tasks_state(str(path))
    tasks = [t for t in st.get("tasks", []) if isinstance(t, dict)]
    batch_ids = {
        str(t.get("id"))
        for t in (st.get("last_dispatch_tasks") or [])
        if isinstance(t, dict) and t.get("id")
    }
    n = 0
    for t in tasks:
        tid = str(t.get("id") or "")
        if tid not in batch_ids:
            continue
        if t.get("status") in ("已下发", "进行中", "已完成"):
            t["status"] = "待下发"
            t.pop("progress_pct", None)
            n += 1
    st["tasks"] = tasks
    save_tasks_state(str(path), st)
    return n


def _clear_downstream_artifacts(work_root: Path) -> None:
    runtime = work_root / "ProjectData" / "RunTime"
    output = work_root / "ProjectData" / "Output"
    sn_meta = runtime / "sn_tables.json"
    if sn_meta.is_file():
        sn_meta.unlink()
    if output.is_dir():
        for pat in ("SN扫码表_*.xlsx", "完工清单_*.xlsx", "设备安装完工报告.xlsx"):
            for f in output.glob(pat):
                try:
                    f.unlink()
                except OSError:
                    pass


def _prepare_project_for_target(project: dict[str, Any], target: str) -> dict[str, Any]:
    """保留用户草稿，清除下游确认标记。"""
    p = dict(project)
    if target == "task_dispatch":
        p.pop("dispatch_confirmed", None)
        p.pop("esn_rows", None)
        # 保留 dispatch_rows（勾选状态）
    return p


def _rebuild_hitl(ctx: SkillContext, target: str) -> dict[str, Any] | None:
    if target == "task_dispatch":
        check = TaskDispatchStep().check_inputs(ctx)
    elif target == "esn_fill":
        check = EsnFillStep().check_inputs(ctx)
    else:
        return None
    if check.get("ok"):
        return None
    return {
        "step": target,
        "reason": check.get("note") or f"已返回「{DI_STEP_NAMES.get(target, target)}」，可在原有基础上继续修改。",
        "need_files": [],
        "need_inputs": [],
        "need_edit": check.get("need_edit"),
    }


def _append_step_records(run_state: dict[str, Any], target: str) -> None:
    """追加 step 记录覆盖 stepper 展示（后写覆盖同 key）。"""
    steps: list[dict] = run_state.setdefault("steps", [])
    target_idx = _step_index(target)
    now = _iso_now()
    for key in DI_STEP_ORDER:
        idx = _step_index(key)
        name = DI_STEP_NAMES.get(key, key)
        if idx < target_idx:
            continue
        if key == target:
            steps.append({
                "key": key, "name": name, "status": "hitl",
                "started_at": now, "ended_at": now, "progress": 0,
                "log_tail": [f"[go_back] 已返回此步，保留先前操作"],
            })
        elif idx > target_idx:
            steps.append({
                "key": key, "name": name, "status": "pending",
                "started_at": now, "progress": 0,
            })


def apply_go_back(work_root: Path, run_state: dict[str, Any]) -> dict[str, Any]:
    target = resolve_go_back_target(run_state)
    if not target:
        return {"ok": False, "error": "当前步骤不支持返回上一步"}

    project = _prepare_project_for_target(run_state.get("project") or {}, target)
    run_state["project"] = project

    reverted = _revert_dispatch_batch(work_root)
    _clear_downstream_artifacts(work_root)

    ctx = _ctx(work_root, run_state)
    ctx.project = project
    hitl = _rebuild_hitl(ctx, target)
    if not hitl:
        return {"ok": False, "error": f"无法重建「{target}」编辑界面，请重置会话后重试"}

    _append_step_records(run_state, target)
    run_state["hitl"] = hitl
    run_state["current_step"] = target
    run_state["error"] = ""
    total = len(DI_STEP_ORDER)
    run_state["overall_progress"] = int(100 * _step_index(target) / total) if total else 0
    run_state.setdefault("logs", []).append(
        f"[go_back] ← 返回「{DI_STEP_NAMES.get(target, target)}」"
        f"（已恢复 {reverted} 条任务为待下发，保留先前勾选草稿）"
    )

    # 刷新聚合 metrics（任务进展表等）
    ts_path = work_root / "ProjectData" / "RunTime" / "tasks_state.json"
    st = load_tasks_state(str(ts_path))
    tasks = [t for t in (st.get("tasks") or []) if isinstance(t, dict)]
    summary = task_summary(tasks, state=st)
    for s in reversed(run_state.get("steps") or []):
        if isinstance(s, dict) and s.get("key") == target:
            s.setdefault("metrics", {}).update(summary)
            break

    return {"ok": True, "target": target, "reverted_tasks": reverted}
