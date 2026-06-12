"""ETH-Trunk 分配：从 2 起递增并跳过已占用编号；MLAG 配对设备共享同一编号。

历史已占用 Trunk 可来自两类 xlsx：

- 互联规划历史：含「本端设备/本端ETH-TRUNK」「对端设备/对端ETH-TRUNK」。
- 接入规划：含「设备/ETH-TRUNK」（设备列可为「设备」「设备名称」「本端设备」之一）。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from oob_interconnect.constants import DEFAULT_TRUNK_START

logger = logging.getLogger(__name__)


def generate_port(used_port_list: list[int] | None, start: int = DEFAULT_TRUNK_START) -> int:
    used = set(used_port_list or [])
    cur = start
    while cur in used:
        cur += 1
    return cur


def build_used_trunks_per_device(
    interconnect_history_path: Optional[str | Path],
    access_plan_path: Optional[str | Path],
) -> dict[str, list[int]]:
    used: dict[str, list[int]] = {}

    def add(dev, val) -> None:
        if dev is None or (isinstance(dev, float) and pd.isna(dev)):
            return
        s = str(dev).strip()
        if not s:
            return
        try:
            v = int(float(val))
        except (TypeError, ValueError):
            return
        used.setdefault(s, []).append(v)

    if interconnect_history_path and Path(interconnect_history_path).is_file():
        try:
            df = pd.read_excel(interconnect_history_path, sheet_name=0, header=0)
            if "本端设备" in df.columns and "本端ETH-TRUNK" in df.columns:
                for _, r in df.iterrows():
                    add(r["本端设备"], r["本端ETH-TRUNK"])
            if "对端设备" in df.columns and "对端ETH-TRUNK" in df.columns:
                for _, r in df.iterrows():
                    add(r["对端设备"], r["对端ETH-TRUNK"])
        except Exception as e:  # noqa: BLE001
            logger.warning("读取互联规划历史失败: %s", e)

    if access_plan_path and Path(access_plan_path).is_file():
        try:
            df = pd.read_excel(access_plan_path, sheet_name=0, header=0)
            dev_col = next((c for c in ("设备", "设备名称", "本端设备") if c in df.columns), None)
            if dev_col and "ETH-TRUNK" in df.columns:
                for _, r in df.iterrows():
                    add(r[dev_col], r["ETH-TRUNK"])
        except Exception as e:  # noqa: BLE001
            logger.warning("读取接入规划失败: %s", e)

    for k in list(used.keys()):
        used[k] = sorted(set(used[k]))
    return used


def assign_port_value(
    df: pd.DataFrame,
    switch_trunk_list: dict[str, list[int]],
    device_to_trunk: dict,
    location: str,
) -> None:
    """
    在 ``df`` 上为 ``{location}ETH-TRUNK`` 列写入分配结果。

    - ``switch_trunk_list``：设备名 → 已占用 Trunk 编号列表。
    - ``device_to_trunk``：MLAG 配对（设备 → 对端设备）；存在时两端共用同一编号。
    """
    allocated_switch_ports: dict[str, int] = {}

    def ensure_list(dev: str) -> list[int]:
        switch_trunk_list.setdefault(dev, [])
        return switch_trunk_list[dev]

    for index, row in df.iterrows():
        device = row[f"{location}设备"]
        if device in allocated_switch_ports:
            df.at[index, f"{location}ETH-TRUNK"] = allocated_switch_ports[device]
            continue
        if device in device_to_trunk:
            paired_device = device_to_trunk[device]
            if paired_device in allocated_switch_ports:
                port_value = allocated_switch_ports[paired_device]
            else:
                u1 = list(switch_trunk_list.get(device) or [])
                u2 = list(switch_trunk_list.get(paired_device) or [])
                port_value = generate_port(sorted(set(u1 + u2)))
                ensure_list(device).append(port_value)
                ensure_list(paired_device).append(port_value)
                allocated_switch_ports[device] = port_value
                allocated_switch_ports[paired_device] = port_value
            df.at[index, f"{location}ETH-TRUNK"] = port_value
        else:
            port_value = generate_port(switch_trunk_list.get(device))
            ensure_list(device).append(port_value)
            allocated_switch_ports[device] = port_value
            df.at[index, f"{location}ETH-TRUNK"] = port_value
