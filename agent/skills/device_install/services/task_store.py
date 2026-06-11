"""
task_store · 任务状态单一事实源（tasks_state.json）读写 + 汇总指标。

汇总指标供 SDUI 投影器渲染「进展查询 / 计划查询 / 设备总览」等只读视图——
投影器是纯函数不读盘，故由各 step 把 task_summary() 结果写入 state.metrics。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_tasks_state(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"tasks": []}


def save_tasks_state(path: str, state: dict) -> None:
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_tasks(path: str) -> list[dict]:
    state = load_tasks_state(path)
    tasks = state.get("tasks")
    return [t for t in tasks if isinstance(t, dict)] if isinstance(tasks, list) else []


# 任务状态 → 默认进度百分比（无用户覆盖 progress_pct 时使用）
_STATUS_PCT = {"已完成": 100, "进行中": 60, "已下发": 20, "待下发": 0, "暂停/受阻": 0}


def progress_pct_for_task(t: dict) -> int:
    """读取任务进度：优先 progress_pct，否则按状态映射。"""
    if t.get("progress_pct") is not None:
        try:
            return max(0, min(100, int(t["progress_pct"])))
        except (TypeError, ValueError):
            pass
    return _STATUS_PCT.get(str(t.get("status", "待下发")), 0)


def _dispatch_scope_keys(state: dict) -> tuple[set[str], set[tuple[str, str]]]:
    """从 tasks_state 取计划下发勾选范围（id 集 + (unit, activity_id) 集）。"""
    ids: set[str] = set()
    keys: set[tuple[str, str]] = set()
    for dt in state.get("last_dispatch_tasks") or []:
        if not isinstance(dt, dict):
            continue
        tid = str(dt.get("id") or "").strip()
        if tid:
            ids.add(tid)
        unit = str(dt.get("unit") or "").strip()
        aid = str(dt.get("activity_id") or "").strip()
        if unit or aid:
            keys.add((unit, aid))
    return ids, keys


def _task_in_dispatch_scope(t: dict, ids: set[str], keys: set[tuple[str, str]]) -> bool:
    tid = str(t.get("id") or "").strip()
    if ids and tid and tid in ids:
        return True
    key = (str(t.get("unit") or "").strip(), str(t.get("activity_id") or "").strip())
    return bool(keys and key in keys)


def dispatch_progress_rows(state: dict, *, row_limit: int = 50) -> list[dict]:
    """计划下发勾选任务 → DataTable 行（含 id / progress）。"""
    ids, keys = _dispatch_scope_keys(state)
    if not ids and not keys:
        return []
    tasks = [t for t in (state.get("tasks") or []) if isinstance(t, dict)]
    scoped = [t for t in tasks if _task_in_dispatch_scope(t, ids, keys)]
    rows: list[dict] = []
    for t in scoped[:row_limit]:
        rows.append({
            "id": str(t.get("id") or ""),
            "unit": str(t.get("unit") or ""),
            "activity_id": str(t.get("activity_id") or ""),
            "activity_name": str(t.get("activity_name") or ""),
            "principal": str(t.get("principal") or t.get("owner") or ""),
            "end_date": str(t.get("end_date") or ""),
            "status": str(t.get("status") or "待下发"),
            "progress": progress_pct_for_task(t),
        })
    return rows


def patch_task_progress(path: str, updates: list[dict]) -> dict:
    """批量写入 progress_pct，返回供 SDUI metrics 刷新的 di_* 片段。"""
    st = load_tasks_state(path)
    tasks = [t for t in (st.get("tasks") or []) if isinstance(t, dict)]
    by_id = {str(t.get("id") or ""): t for t in tasks if t.get("id")}
    for u in updates:
        if not isinstance(u, dict):
            continue
        tid = str(u.get("id") or "").strip()
        if not tid or tid not in by_id:
            continue
        raw = u.get("progress", u.get("progress_pct"))
        try:
            pct = max(0, min(100, int(raw if raw is not None else 0)))
        except (TypeError, ValueError):
            continue
        by_id[tid]["progress_pct"] = pct
    st["tasks"] = tasks
    save_tasks_state(path, st)
    summary = task_summary(tasks)
    summary["di_dispatch_progress_rows"] = dispatch_progress_rows(st)
    return summary


def count_by_status(tasks: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tasks:
        s = str(t.get("status", "待下发"))
        out[s] = out.get(s, 0) + 1
    return out


def task_summary(tasks: list[dict], *, row_limit: int = 50, state: dict | None = None) -> dict:
    """汇总任务指标（写入 metrics，命名空间前缀 di_）。
    返回扁平 dict：di_total / di_done / di_in_progress / di_pending / di_dispatched
    / di_by_unit_rows（list[list]）/ di_task_rows（list[list]）
    / di_dispatch_progress_rows（list[dict]，计划下发勾选范围）。
    """
    total = len(tasks)
    by_status = count_by_status(tasks)
    done = by_status.get("已完成", 0)
    in_prog = by_status.get("进行中", 0)
    pending = by_status.get("待下发", 0)
    dispatched = sum(1 for t in tasks if t.get("status") != "待下发")

    # 按管理单元统计
    by_unit: dict[str, dict] = {}
    for t in tasks:
        u = str(t.get("unit", "未知"))
        by_unit.setdefault(u, {"total": 0, "done": 0})
        by_unit[u]["total"] += 1
        if t.get("status") == "已完成":
            by_unit[u]["done"] += 1
    unit_rows = [
        [u, str(c["total"]), str(c["done"]),
         f"{int(c['done'] / c['total'] * 100) if c['total'] else 0}%"]
        for u, c in sorted(by_unit.items())
    ]

    # 任务明细表（前 row_limit 条）
    task_rows = [
        [
            str(t.get("unit", "")),
            str(t.get("activity_id", "")),
            str(t.get("activity_name", "")),
            str(t.get("principal") or t.get("owner", "")),
            str(t.get("end_date", "")),
            str(t.get("status", "待下发")),
        ]
        for t in tasks[:row_limit]
    ]

    out = {
        "di_total": total,
        "di_done": done,
        "di_in_progress": in_prog,
        "di_pending": pending,
        "di_dispatched": dispatched,
        "di_completion_pct": int(done / total * 100) if total else 0,
        "di_by_unit_rows": unit_rows,
        "di_task_rows": task_rows,
        "di_dispatch_progress_rows": dispatch_progress_rows(state) if state else [],
    }
    return out
