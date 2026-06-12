#!/usr/bin/env python3
"""Path helpers for offline device naming workflow (cwd contract + autodetect)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence


def resolve_local_only(p: Path) -> Path:
    if p.is_absolute():
        return p
    return (Path.cwd() / p).resolve()


def require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception:
        raise SystemExit(
            f"ERROR: {label} must be located under current working directory.\n"
            f"  resolved: {resolved}\n"
            f"  cwd:      {cwd}"
        )
    return resolved


def list_excel_files_in_cwd() -> List[Path]:
    cwd = Path.cwd().resolve()
    files: List[Path] = []
    for ext in (".xlsx", ".xls", ".XLSX", ".XLS", ".csv", ".CSV"):
        files.extend([p for p in cwd.rglob(f"*{ext}") if p.is_file()])
    uniq: List[Path] = []
    seen = set()
    for p in files:
        if p.name.startswith("~$"):
            continue
        rp = str(p.resolve())
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)
    return uniq


def pick_single(candidates: Sequence[Path], label: str) -> Path:
    if not candidates:
        raise SystemExit(
            f"ERROR: cannot auto-detect {label} in current directory.\n"
            f"  cwd: {Path.cwd().resolve()}\n"
            "Hint: put the file in cwd or pass an explicit path."
        )
    if len(candidates) > 1:
        formatted = "\n".join([f"  - {c}" for c in candidates])
        raise SystemExit(
            f"ERROR: multiple candidates found for {label}.\n{formatted}\n"
            "Hint: pass an explicit path."
        )
    return candidates[0]


def autodetect_location_in_cwd() -> Path:
    cands = [
        f
        for f in list_excel_files_in_cwd()
        if ("设备位置" in f.name) or ("004" in f.name)
    ]
    return pick_single(cands, "location (设备位置信息表)")


def autodetect_device_list_in_cwd() -> Path:
    cands = [f for f in list_excel_files_in_cwd() if "设备清单" in f.name]
    return pick_single(cands, "device-list (设备清单表)")


def autodetect_lld_in_cwd() -> Path:
    cands = [
        f
        for f in list_excel_files_in_cwd()
        if ("LLD" in f.name.upper() or "lld" in f.name)
        and ("ZTP" not in f.name.upper())
        and ("设备清单" not in f.name)
    ]
    return pick_single(cands, "lld (LLD设计)")


def autodetect_ztp_lld_in_cwd() -> Path:
    cands = [
        f
        for f in list_excel_files_in_cwd()
        if ("ZTP" in f.name.upper()) and ("LLD" in f.name.upper() or "lld" in f.name.lower())
    ]
    return pick_single(cands, "ztp-lld (ZTP_LLD)")


def autodetect_mapping_in_cwd() -> Path:
    files = list_excel_files_in_cwd()
    cands = [
        f
        for f in files
        if ("devicename-mapping" in f.name.lower())
        or ("mapping" in f.name.lower() and f.suffix.lower() in (".csv", ".xlsx", ".xls"))
        or ("映射" in f.name)
    ]
    if not cands:
        cands = [f for f in files if f.suffix.lower() in (".csv",) and "source" in f.name.lower()]
    return pick_single(cands, "mapping (source/target)")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def new_run_dir(out_dir: Path, restrict_to_cwd: bool = True) -> Path:
    if restrict_to_cwd:
        out_dir = require_under_cwd(out_dir, "out-dir")
    else:
        out_dir = resolve_local_only(out_dir)
    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def ztp_output_suffix(plane: Optional[int]) -> str:
    if plane is None:
        return "_ztp"
    return f"_ztp_l{plane}"
