# -*- coding: utf-8 -*-
"""演示/联调（仅 Skill 目录内）：按步骤清理 deploy_chain/Output，默认保留 input 材料。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deploy_chain import clear_from_step, load_chain
from plan_chain import clear_plan_from_step, remove_legacy_state_file


def _plan_rt(skill_root: Path) -> Path:
    return skill_root / "ProjectData" / "plan" / "RunTime"


def _plan_out(skill_root: Path) -> Path:
    return skill_root / "ProjectData" / "plan" / "Output"


def _unlink_if_exists(path: Path) -> bool:
    if path.is_file():
        path.unlink()
        return True
    return False


def _glob_unlink(dir_path: Path, pattern: str) -> list[str]:
    removed: list[str] = []
    if not dir_path.is_dir():
        return removed
    for p in dir_path.glob(pattern):
        if p.is_file():
            p.unlink()
            removed.append(str(p.name))
    return removed


def _remove_plan_outputs(skill_root: Path, *, include_second_normalized: bool) -> list[str]:
    removed: list[str] = []
    out = _plan_out(skill_root)
    inp = skill_root / "ProjectData" / "plan" / "Input"
    for name in (
        "third_level_tasks.json",
        "dispatch_record.json",
        "device_base_table.json",
        "test_activities.json",
    ):
        if _unlink_if_exists(out / name):
            removed.append(f"plan/Output/{name}")
    removed.extend(f"plan/Output/{n}" for n in _glob_unlink(out, "全量设备完工清单列表_*.xlsx"))
    removed.extend(f"plan/Output/{n}" for n in _glob_unlink(out, "CloudOps*.xlsx"))
    if include_second_normalized and _unlink_if_exists(inp / "second_level_tasks.json"):
        removed.append("plan/Input/second_level_tasks.json")
    return removed


def reset_workspace(
    skill_root: Path,
    *,
    scope: str = "all",
    from_step: int | None = None,
) -> dict[str, Any]:
    key = str(scope or "all").strip().lower()
    # `reset_scope=all` is the dashboard "演示重置" contract. Some cards also
    # include the current `from_step`; full reset must still return to Step 1.
    step = None if key == "all" else from_step
    if step is None:
        mapping = {
            "all": 1,
            "plan": 1,
            "receive": 1,
            "split": 2,
            "dispatch": 3,
            "cloudops": 4,
            "co": 4,
        }
        step = mapping.get(key, 1)

    removed: list[str] = []
    notes: list[str] = []

    if step <= 1:
        clear_plan_from_step(skill_root, 1)
        removed.extend(_remove_plan_outputs(skill_root, include_second_normalized=True))
        clear_from_step(skill_root, 4)
        rt = _plan_rt(skill_root)
        for name in (
            "scene.json",
            "toolkit_executor.json",
            "toolkit_import.json",
            "file_index.json",
        ):
            if _unlink_if_exists(rt / name):
                removed.append(f"plan/RunTime/{name}")
        notes.append("进度已回到步骤 ① 之前（deploy_chain 已清）；input 收件箱未删。")
    elif step == 2:
        clear_plan_from_step(skill_root, 2)
        removed.extend(_remove_plan_outputs(skill_root, include_second_normalized=False))
        clear_from_step(skill_root, 4)
        notes.append("进度已回到步骤 ② 之前；可重新「拆分计划」。")
    elif step == 3:
        clear_plan_from_step(skill_root, 3)
        removed.extend(_remove_plan_outputs(skill_root, include_second_normalized=False))
        clear_from_step(skill_root, 4)
        notes.append("进度已回到步骤 ③ 之前；可重新「下发计划」。")
    elif step == 4:
        clear_from_step(skill_root, 4)
        removed.extend(_glob_unlink(_plan_out(skill_root), "CloudOps*.xlsx"))
        notes.append("已清空 CloudOps ④～⑥ 进度与 xlsx；计划三步保持完成。")
    elif step == 5:
        clear_from_step(skill_root, 5)
        for name in ("CloudOps配置_手工补充.xlsx", "CloudOps完整配置文件.xlsx"):
            if _unlink_if_exists(_plan_out(skill_root) / name):
                removed.append(f"plan/Output/{name}")
        removed.extend(_glob_unlink(_plan_out(skill_root), "CloudOps完整*.xlsx"))
        notes.append("已清空步骤 ⑤～⑥；可重新「补充」。")
    elif step == 6:
        clear_from_step(skill_root, 6)
        for name in ("CloudOps完整配置文件.xlsx",):
            if _unlink_if_exists(_plan_out(skill_root) / name):
                removed.append(f"plan/Output/{name}")
        notes.append("已清空步骤 ⑥ 及后续；可重新「完整配置」。")
    elif step == 7:
        clear_from_step(skill_root, 7)
        ep = _plan_rt(skill_root) / "toolkit_executor.json"
        if _unlink_if_exists(ep):
            removed.append("plan/RunTime/toolkit_executor.json")
        notes.append("已清空步骤 ⑦ 及后续；可重新「设置调测设备」。")
    elif step >= 8:
        clear_from_step(skill_root, 8)
        notes.append("已清空步骤 ⑧ 及后续；可重新「导入 Toolkit」。")

    remove_legacy_state_file(skill_root)

    return {
        "fromStep": step,
        "scope": scope,
        "removed": removed,
        "notes": notes,
        "chainPath": str((_plan_rt(skill_root) / "deploy_chain.json").resolve()),
    }
