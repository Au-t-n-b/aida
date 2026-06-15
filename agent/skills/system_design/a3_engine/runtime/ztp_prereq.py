"""ZTP 场景：缺失中间产物时自动 subprocess 补齐（Skill-First runtime）。"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from naming_input_resolver import find_ztp_lld
from skill_root import resolve_capability_root
from subprocess_runner import run_l3_subprocess

GENERATE_ZTP_LLD = "生成ZTP设计文件"

ZTP_SCAN_COMMANDS = frozenset(
    {
        GENERATE_ZTP_LLD,
        "生成ZTP配置文件",
        "生成灵衢开局文件",
    }
)

ZTP_NAMING_COMMAND_PREFIX = "ZTP名称替换"


def project_data_dir(skill_root: Path) -> Path:
    return skill_root / "ProjectData"


def _safe_run_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "").strip("_")
    return safe or "run"


def _is_ztp_lld_file(path: Path) -> bool:
    upper = path.name.upper()
    return path.suffix.lower() in {".xlsx", ".xls"} and "ZTP" in upper and "LLD" in upper


def _copy_ztp_lld_to_output(src: Path, skill_root: Path) -> Path:
    output_dir = skill_root / "ProjectData" / "Output"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = output_dir / f"{src.stem}_{stamp}{src.suffix}"
    if dst.exists():
        stem, suffix = dst.stem, dst.suffix
        counter = 2
        while dst.exists():
            dst = output_dir / f"{stem}_{counter}{suffix}"
            counter += 1
    shutil.copy2(src, dst)
    return dst


def ensure_ztp_lld(
    skill_root: Path,
    *,
    run_id: str,
    input_007: Path,
    input_resource: Path,
) -> Optional[Path]:
    """若 ProjectData 中无 ZTP_LLD，则自动执行「生成ZTP设计文件」（含子 skill 链式前置）。"""
    existing = find_ztp_lld(skill_root)
    if existing is not None:
        return existing

    try:
        capability_root = resolve_capability_root(skill_root)
    except FileNotFoundError:
        return None

    safe = _safe_run_id(run_id)
    work_dir = skill_root / "ProjectData" / "Work" / safe / "ztp_auto_prereq"
    raw_output = work_dir / "raw_output"
    raw_output.mkdir(parents=True, exist_ok=True)

    result = run_l3_subprocess(
        GENERATE_ZTP_LLD,
        capability_root=capability_root,
        skill_root=skill_root,
        topology=input_007,
        resource=input_resource,
        out_dir=raw_output,
        scan_dir=project_data_dir(skill_root),
    )
    if result.status != "ok":
        return None

    ztp_src: Path | None = None
    for path in result.output_files:
        if _is_ztp_lld_file(path):
            ztp_src = path
            break
    if ztp_src is None:
        for path in raw_output.rglob("*.xlsx"):
            if _is_ztp_lld_file(path):
                ztp_src = path
                break
    if ztp_src is None:
        return None

    return _copy_ztp_lld_to_output(ztp_src, skill_root)


def uses_ztp_auto_prereq(command: str) -> bool:
    return command in ZTP_SCAN_COMMANDS or command.startswith(ZTP_NAMING_COMMAND_PREFIX)
