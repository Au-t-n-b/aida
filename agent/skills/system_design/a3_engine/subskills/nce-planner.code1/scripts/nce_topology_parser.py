"""Parse NCE device names from the 007 port topology workbook."""

from __future__ import annotations

from pathlib import Path
from typing import List, Set

import pandas as pd

DEFAULT_SHEET = "计算带外管理面端口互联"


def _find_header_row(df_raw: pd.DataFrame) -> int:
    for idx in range(min(len(df_raw), 30)):
        row = df_raw.iloc[idx].astype(str).tolist()
        if any("设备命名" in str(cell) for cell in row):
            return idx
    raise ValueError("未找到包含'设备命名'的行，请检查端口互联表")


def load_topology_nce_devices(topology_path: str, sheet_name: str = DEFAULT_SHEET) -> List[str]:
    path = Path(topology_path)
    df_raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
    header_row = _find_header_row(df_raw)
    df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
    if df.empty:
        raise ValueError(f"sheet {sheet_name!r} 无数据")

    first_col = df.columns[0]
    devices: List[str] = []
    seen: Set[str] = set()
    for raw_name in df[first_col].astype(str):
        name = raw_name.strip()
        if not name or name.lower() in ("nan", "none"):
            continue
        upper = name.upper()
        if "NCEFB" not in upper and "NCEFI" not in upper:
            continue
        if name in seen:
            continue
        seen.add(name)
        devices.append(name)

    if not devices:
        raise ValueError("未找到名称为 NCEFB 或 NCEFI 的设备，请检查端口连线表内容")
    return devices


def split_nce_devices(devices: List[str]) -> tuple[List[str], List[str]]:
    fb_devices = [device for device in devices if "NCEFB" in device.upper()]
    fi_devices = [device for device in devices if "NCEFI" in device.upper()]
    return fb_devices, fi_devices


def load_mlag_peer_names(mlag_list_path: str) -> Set[str]:
    path = Path(mlag_list_path)
    names: Set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            names.add(item)
    return names
