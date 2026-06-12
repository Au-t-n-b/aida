"""L2 LEAF-SPINE 互联：VLAN + ETH-TRUNK + trunk 端口（对齐 a3_l2_net_interconnection）。"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import pandas as pd

from ni_io import get_switch_mlag_data

OUTPUT_COLUMNS = [
    "网络平面",
    "本端设备",
    "本端接口",
    "本端接口IP地址",
    "本端接口掩码",
    "本端ETH-TRUNK",
    "本端VLAN",
    "对端设备",
    "对端接口",
    "对端接口IP地址",
    "对端接口掩码",
    "对端ETH-TRUNK",
    "对端VLAN",
    "PVID",
    "端口类型",
    "标签",
]


def generate_port(used: Sequence[int]) -> int:
    current = 2
    while current in used:
        current += 1
    return current


def assign_port_value(
    df: pd.DataFrame,
    reserved_trunks: List[int],
    device_to_trunk: Dict[str, str],
    location: str,
) -> None:
    """对齐 utils.assign_port_value（leaf_trunk_list 离线为已占用 trunk 编号列表）。"""
    allocated: Dict[str, int] = {}
    for index, row in df.iterrows():
        device = row[f"{location}设备"]
        if device in allocated:
            df.at[index, f"{location}ETH-TRUNK"] = allocated[device]
            continue
        port_value = 2
        if device in device_to_trunk:
            paired = device_to_trunk[device]
            if paired in allocated:
                port_value = allocated[paired]
            else:
                port_value = generate_port(reserved_trunks + list(allocated.values()))
                allocated[device] = port_value
                allocated[paired] = port_value
            df.at[index, f"{location}ETH-TRUNK"] = port_value
        else:
            port_value = generate_port(reserved_trunks + list(allocated.values()))
            allocated[device] = port_value
            df.at[index, f"{location}ETH-TRUNK"] = port_value


def allocate_connection_l2(
    df: pd.DataFrame,
    vlan,
    network_type: str,
    switch_mlag_df: pd.DataFrame,
    old_df: pd.DataFrame,
    reserved_trunks: Optional[List[int]] = None,
) -> pd.DataFrame:
    device_to_trunk = switch_mlag_df.set_index("设备")["接入交换机"].to_dict()
    work = df.copy()
    work.loc[
        :,
        [
            "端口类型",
            "本端ETH-TRUNK",
            "本端VLAN",
            "对端ETH-TRUNK",
            "对端VLAN",
            "PVID",
            "标签",
            "网络平面",
            "本端接口IP地址",
            "本端接口掩码",
            "对端接口IP地址",
            "对端接口掩码",
        ],
    ] = ["trunk", "", "", "", "", "", "", "", "", "", "", ""]

    work["本端接口"] = work.iloc[:, 2].fillna("").astype(str) + work.iloc[:, 1].fillna("").astype(str)
    work["本端接口"] = work["本端接口"].str.strip()
    work["对端接口"] = work.iloc[:, 5].fillna("").astype(str) + work.iloc[:, 7].fillna("").astype(str)
    work["对端接口"] = work["对端接口"].str.strip()
    work = work.rename(columns={work.columns[0]: "本端设备", work.columns[8]: "对端设备"})
    work = work[
        [
            "本端设备",
            "对端设备",
            "本端ETH-TRUNK",
            "本端VLAN",
            "对端ETH-TRUNK",
            "对端VLAN",
            "PVID",
            "端口类型",
            "标签",
            "网络平面",
            "本端接口IP地址",
            "本端接口掩码",
            "对端接口IP地址",
            "对端接口掩码",
            "本端接口",
            "对端接口",
        ]
    ]
    work = work[OUTPUT_COLUMNS]

    leaf_reserved = list(reserved_trunks or [])
    spine_reserved: List[int] = []
    if not old_df.empty and "对端ETH-TRUNK" in old_df.columns:
        for v in old_df["对端ETH-TRUNK"].dropna().unique():
            try:
                spine_reserved.append(int(v))
            except (TypeError, ValueError):
                pass

    assign_port_value(work, leaf_reserved, device_to_trunk, "本端")
    assign_port_value(work, spine_reserved, device_to_trunk, "对端")
    work.loc[:, ["网络平面", "本端VLAN", "对端VLAN", "PVID", "标签"]] = [
        network_type,
        vlan,
        vlan,
        "",
        "INTER_LINK",
    ]
    return work


def build_mlag_from_connect_raw(df_all: pd.DataFrame) -> pd.DataFrame:
    return get_switch_mlag_data(df_all)
