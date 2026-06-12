"""从 007 端口连线表解析 CCAE 设备列表。"""

from __future__ import annotations

from pathlib import Path
from typing import List, Set

import pandas as pd

DEFAULT_SHEET = "计算带外管理面端口互联"


def _find_header_row(df_raw: pd.DataFrame) -> int:
    for i in range(min(len(df_raw), 30)):
        row = df_raw.iloc[i].astype(str).tolist()
        if any("设备命名" in str(c) for c in row):
            return i
    return 0


def load_topology_ccae_devices(
    topology_path: str,
    sheet_name: str = DEFAULT_SHEET,
) -> List[str]:
    path = Path(topology_path)
    df_raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
    header_row = _find_header_row(df_raw)
    df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
    if df.empty:
        raise ValueError(f"sheet {sheet_name!r} 无数据")

    first_col = df.columns[0]
    series = df[first_col].astype(str)
    devices: List[str] = []
    seen: Set[str] = set()
    for name in series:
        name = str(name).strip()
        if not name or name.lower() in ("nan", "none"):
            continue
        if "CCAE" not in name.upper():
            continue
        if name in seen:
            continue
        seen.add(name)
        devices.append(name)

    if not devices:
        raise ValueError(
            f"{sheet_name} 中未找到 CCAE 设备（首列需包含 CCAE），请检查端口连线表"
        )
    return devices


def load_mlag_peer_names(mlag_list_path: str) -> Set[str]:
    path = Path(mlag_list_path)
    names: Set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            names.add(s)
    return names
