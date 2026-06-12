#!/usr/bin/env python3
"""Generate 设备清单表 from 设备位置信息表 (offline, no EDM)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from naming_path_utils import new_run_dir, require_under_cwd, resolve_local_only

SHEET_DEFAULT = "设备位置信息"
OUTPUT_NAME = "设备清单表.xlsx"
OUTPUT_SHEET = "设备信息"
REQUIRED_COLUMNS = ["设备名称", "所属机房", "所属机柜", "安装起始U位"]
OUTPUT_COLUMNS = ["编号", "设备名称", "所属机房", "所属机柜", "安装起始U位", "客户定义设备名称"]
BLANK_PANEL = "空挡板"


def generate_device_list_df(
    location_path: Path,
    *,
    sheet_name: str = SHEET_DEFAULT,
) -> pd.DataFrame:
    df = pd.read_excel(location_path, sheet_name=sheet_name, header=0, dtype=str)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"设备位置信息表缺少列: {missing}，实际: {list(df.columns)}")

    selected = df[REQUIRED_COLUMNS].copy()
    selected = selected[selected["设备名称"].astype(str).str.strip() != BLANK_PANEL]
    selected.insert(0, "编号", range(1, len(selected) + 1))
    selected["客户定义设备名称"] = ""
    return selected[OUTPUT_COLUMNS]


def generate_device_list(
    *,
    location_path: Path,
    sheet_name: str = SHEET_DEFAULT,
    out_dir: Path = Path("output"),
    restrict_to_cwd: bool = True,
) -> Path:
    if restrict_to_cwd:
        location_path = require_under_cwd(location_path, "location")
    else:
        location_path = resolve_local_only(location_path)

    if not location_path.is_file():
        raise ValueError(f"设备位置信息表不存在: {location_path}")

    df = generate_device_list_df(location_path, sheet_name=sheet_name)
    run_dir = new_run_dir(out_dir, restrict_to_cwd=restrict_to_cwd)
    out_path = run_dir / OUTPUT_NAME
    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=OUTPUT_SHEET)
    return out_path
