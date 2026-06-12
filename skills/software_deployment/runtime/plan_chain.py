# -*- coding: utf-8 -*-
"""计划三步（①～③）进度：仅 deploy_chain，不再使用 state.json。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deploy_chain import load_chain, merge_chain, save_chain


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(skill_root: Path, path: str | Path) -> str:
    p = Path(path).resolve()
    try:
        return str(p.relative_to(skill_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _legacy_state_path(skill_root: Path) -> Path:
    return skill_root / "ProjectData" / "plan" / "RunTime" / "state.json"


def remove_legacy_state_file(skill_root: Path) -> bool:
    """删除已废弃的 state.json（若存在）。"""
    p = _legacy_state_path(skill_root)
    if p.is_file():
        p.unlink()
        return True
    return False


PLAN_CHAIN_KEYS: tuple[str, ...] = (
    "step1_plan_receive_at",
    "step1_second_tasks_path",
    "step1_scene_path",
    "step1_task_count",
    "step2_plan_split_at",
    "step2_third_tasks_path",
    "step2_testcase_path",
    "step2_third_task_count",
    "step3_plan_dispatch_at",
    "step3_lld_path",
    "step3_device_base_path",
    "step3_dispatch_record_path",
    "step3_checklist_path",
)


def derive_plan_step(chain: dict[str, Any]) -> str:
    if str(chain.get("step3_plan_dispatch_at") or "").strip():
        return "dispatched"
    if str(chain.get("step2_plan_split_at") or "").strip():
        return "split"
    if str(chain.get("step1_plan_receive_at") or "").strip():
        return "received"
    return "idle"


def is_step3_done(chain: dict[str, Any]) -> bool:
    return bool(str(chain.get("step3_plan_dispatch_at") or "").strip())


def migrate_chain_from_state(skill_root: Path) -> dict[str, Any]:
    """一次性：从旧 state.json 回填 deploy_chain，随后删除 state.json。"""
    chain = load_chain(skill_root)
    sp = _legacy_state_path(skill_root)
    if not sp.is_file():
        return chain

    try:
        raw = json.loads(sp.read_text(encoding="utf-8"))
        legacy = str(raw.get("step") or "idle").strip().lower()
    except Exception:
        remove_legacy_state_file(skill_root)
        return chain

    plan = skill_root / "ProjectData" / "plan"
    updates: dict[str, Any] = {}

    if legacy in {"received", "split", "dispatched", "dispatch"} and not chain.get("step1_plan_receive_at"):
        inp = plan / "Input" / "second_level_tasks.json"
        if inp.is_file():
            updates["step1_plan_receive_at"] = _iso_now()
            updates["step1_second_tasks_path"] = _rel(skill_root, inp)
            try:
                tasks = json.loads(inp.read_text(encoding="utf-8")).get("tasks") or []
                updates["step1_task_count"] = len(tasks) if isinstance(tasks, list) else 0
            except Exception:
                pass
        scene = plan / "RunTime" / "scene.json"
        if scene.is_file():
            updates["step1_scene_path"] = _rel(skill_root, scene)

    if legacy in {"split", "dispatched", "dispatch"} and not chain.get("step2_plan_split_at"):
        third = plan / "Output" / "third_level_tasks.json"
        if third.is_file():
            updates["step2_plan_split_at"] = _iso_now()
            updates["step2_third_tasks_path"] = _rel(skill_root, third)
            try:
                tasks = json.loads(third.read_text(encoding="utf-8")).get("tasks") or []
                updates["step2_third_task_count"] = len(tasks) if isinstance(tasks, list) else 0
            except Exception:
                pass
    if legacy in {"dispatched", "dispatch"} and not chain.get("step3_plan_dispatch_at"):
        base = plan / "Output" / "device_base_table.json"
        if base.is_file():
            updates["step3_plan_dispatch_at"] = _iso_now()
            updates["step3_device_base_path"] = _rel(skill_root, base)
        dr = plan / "Output" / "dispatch_record.json"
        if dr.is_file():
            updates["step3_dispatch_record_path"] = _rel(skill_root, dr)
            try:
                rec = json.loads(dr.read_text(encoding="utf-8"))
                if isinstance(rec, dict) and rec.get("lldPath"):
                    updates["step3_lld_path"] = str(rec["lldPath"])
            except Exception:
                pass

    if updates:
        chain = merge_chain(skill_root, **updates)
    remove_legacy_state_file(skill_root)
    return chain


def mark_step1_complete(
    skill_root: Path,
    *,
    second_tasks_path: str | Path,
    task_count: int,
    scene_path: str | Path | None = None,
) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "step1_plan_receive_at": _iso_now(),
        "step1_second_tasks_path": _rel(skill_root, second_tasks_path),
        "step1_task_count": task_count,
    }
    if scene_path and Path(scene_path).is_file():
        kw["step1_scene_path"] = _rel(skill_root, scene_path)
    remove_legacy_state_file(skill_root)
    return merge_chain(skill_root, **kw)


def mark_step2_complete(
    skill_root: Path,
    *,
    third_tasks_path: str | Path,
    third_task_count: int,
    testcase_path: str | Path | None = None,
) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "step2_plan_split_at": _iso_now(),
        "step2_third_tasks_path": _rel(skill_root, third_tasks_path),
        "step2_third_task_count": third_task_count,
    }
    if testcase_path and Path(testcase_path).is_file():
        kw["step2_testcase_path"] = _rel(skill_root, testcase_path)
    remove_legacy_state_file(skill_root)
    return merge_chain(skill_root, **kw)


def mark_step3_complete(
    skill_root: Path,
    *,
    lld_path: str | Path,
    device_base_path: str | Path,
    dispatch_record_path: str | Path,
    checklist_path: str | Path | None = None,
) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "step3_plan_dispatch_at": _iso_now(),
        "step3_lld_path": _rel(skill_root, lld_path) if lld_path else "",
        "step3_device_base_path": _rel(skill_root, device_base_path),
        "step3_dispatch_record_path": _rel(skill_root, dispatch_record_path),
    }
    if checklist_path and Path(checklist_path).is_file():
        kw["step3_checklist_path"] = _rel(skill_root, checklist_path)
    remove_legacy_state_file(skill_root)
    return merge_chain(skill_root, **kw)


def clear_plan_from_step(skill_root: Path, from_step: int) -> dict[str, Any]:
    if from_step < 1:
        from_step = 1
    if from_step > 3:
        return load_chain(skill_root)
    idx = {1: 0, 2: 4, 3: 8}[from_step]
    chain = load_chain(skill_root)
    for key in PLAN_CHAIN_KEYS[idx:]:
        if key.endswith("_count"):
            chain[key] = 0
        else:
            chain[key] = None
    save_chain(skill_root, chain)
    remove_legacy_state_file(skill_root)
    return chain
