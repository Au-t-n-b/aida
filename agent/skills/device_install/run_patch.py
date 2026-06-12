"""
run_patch · 设备安装 skill 内「非 HITL 重跑」的运行时补丁（由 file_handler.merge_run_patch 暴露）。

AIDA 通用入口：POST /agent/{skill}/run-patch → skill.file_handler.merge_run_patch。
业务逻辑仅在本模块，main.py 不做 skill 名硬编码。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .services.task_store import patch_task_progress as _patch_task_progress


def merge_run_patch(work_root: Path, run_state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """合并运行时补丁。返回 {"ok": bool, "error"?: str}；成功时原地更新 run_state。"""
    action = str(payload.get("action") or payload.get("stepId") or "").strip()
    if action == "go_back":
        from .go_back import apply_go_back
        return apply_go_back(work_root, run_state)
    if action == "task_progress":
        return _merge_task_progress(work_root, run_state, payload.get("rows") or [])
    return {"ok": False, "error": f"unsupported run-patch action: {action or '(empty)'}"}


def _merge_task_progress(work_root: Path, run_state: dict[str, Any], rows: list) -> dict[str, Any]:
    path = work_root / "ProjectData" / "RunTime" / "tasks_state.json"
    metrics = _patch_task_progress(str(path), rows if isinstance(rows, list) else [])
    for s in run_state.get("steps") or []:
        if isinstance(s, dict):
            s.setdefault("metrics", {}).update(metrics)
    return {"ok": True}
