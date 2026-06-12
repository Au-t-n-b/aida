# -*- coding: utf-8 -*-
"""步骤 ③：从 plan_dispatch 输入目录解析 LLD 设计文件路径。"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _runtime_dir(skill_root: Path) -> Path:
    return skill_root / "runtime"


def _ensure_runtime_path(skill_root: Path) -> None:
    rt = _runtime_dir(skill_root)
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))


def _unlink_if_exists(path: Path) -> None:
    if path.is_file():
        path.unlink()


def _invalidate_lld_derived_outputs(skill_root: Path) -> None:
    """New LLD invalidates Step 3+ derived files, while keeping split output."""
    _ensure_runtime_path(skill_root)
    from deploy_chain import clear_from_step  # noqa: WPS433
    from plan_chain import clear_plan_from_step  # noqa: WPS433

    clear_plan_from_step(skill_root, 3)
    clear_from_step(skill_root, 4)

    out = skill_root / "ProjectData" / "plan" / "Output"
    for name in ("dispatch_record.json", "device_base_table.json"):
        _unlink_if_exists(out / name)
    for pat in ("全量设备完工清单列表_*.xlsx", "CloudOps*.xlsx"):
        for p in out.glob(pat):
            _unlink_if_exists(p)
    rt = skill_root / "ProjectData" / "plan" / "RunTime"
    for name in ("toolkit_import.json",):
        _unlink_if_exists(rt / name)


def resolve_lld_path(skill_root: Path) -> str:
    root = Path(skill_root).resolve()
    _ensure_runtime_path(root)
    from input_registry import get_active_file, promote_new_lld_if_present  # noqa: WPS433

    promoted = promote_new_lld_if_present(root)
    if promoted.get("changed"):
        _invalidate_lld_derived_outputs(root)

    active = get_active_file(root, "lld_design")
    active_path = str(active.get("absPath") or "")
    if active_path:
        return active_path

    base = root / "ProjectData" / "input" / "plan_dispatch"
    if not base.is_dir():
        return ""

    candidates: list[Path] = []
    for pat in (
        "*LLD*设计*.xlsx",
        "*LLD设计*.xlsx",
        "*系统设计*LLD*.xlsx",
        "*LLD*.xlsx",
        "lld/*LLD*设计*.xlsx",
    ):
        for p in base.glob(pat):
            if not p.is_file():
                continue
            try:
                rp = p.resolve()
                if (base / "active") in rp.parents or (base / "archive") in rp.parents:
                    continue
            except Exception:
                pass
            candidates.append(p)
    if not candidates:
        return ""

    def _score(p: Path) -> tuple[int, float, str]:
        name = p.name
        s = 0
        if "LLD设计" in name:
            s += 10
        if re.search(r"LLD.*设计", name):
            s += 5
        return (s, p.stat().st_mtime, name)

    best = sorted(candidates, key=_score, reverse=True)[0]
    return str(best.resolve())
