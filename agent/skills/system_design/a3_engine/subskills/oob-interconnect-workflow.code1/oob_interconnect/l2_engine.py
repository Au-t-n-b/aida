"""二层互联规划引擎：填写 VLAN、ETH-Trunk、端口类型 trunk、标签 INTER_LINK。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from oob_interconnect.constants import INTER_LINK_LABEL, SPINE_TOKEN, TRUNK_PORT_TYPE
from oob_interconnect.load_007 import get_all_switch_mlag_data, get_switch_data_l2
from oob_interconnect.resource import get_vlan_for_plane
from oob_interconnect.trunk_assign import assign_port_value, build_used_trunks_per_device

logger = logging.getLogger(__name__)


OUTPUT_COLUMNS_ORDER = [
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


def allocate_connection(
    df: pd.DataFrame,
    vlan,
    network_type: str,
    switch_mlag_df: pd.DataFrame,
    interconnect_history_path: Optional[str | Path] = None,
    access_plan_path: Optional[str | Path] = None,
    trunk_by_device: Optional[dict[str, list[int]]] = None,
) -> pd.DataFrame:
    device_to_trunk = (
        switch_mlag_df.set_index("设备")["接入交换机"].to_dict() if not switch_mlag_df.empty else {}
    )
    placeholder_cols = [
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
    ]
    df = df.copy()
    df.loc[:, placeholder_cols] = [TRUNK_PORT_TYPE, "", "", "", "", "", "", "", "", "", "", ""]
    df["本端接口"] = (df.iloc[:, 2].fillna("") + df.iloc[:, 1].fillna("")).str.strip()
    df["对端接口"] = (df.iloc[:, 5].fillna("") + df.iloc[:, 7].fillna("")).str.strip()
    df.rename(columns={df.columns[0]: "本端设备", df.columns[8]: "对端设备"}, inplace=True)
    df = df[OUTPUT_COLUMNS_ORDER]

    if trunk_by_device is None:
        trunk_by_device = build_used_trunks_per_device(interconnect_history_path, access_plan_path)
    assign_port_value(df, trunk_by_device, device_to_trunk, "本端")
    assign_port_value(df, trunk_by_device, device_to_trunk, "对端")
    df.loc[:, ["网络平面", "本端VLAN", "对端VLAN", "PVID", "标签"]] = [
        network_type,
        vlan,
        vlan,
        "",
        INTER_LINK_LABEL,
    ]
    return df


def run_l2_core(
    topology_path: str,
    sheet_name: str,
    resource_path: str,
    plane_config: dict[str, dict[str, str]],
    interconnect_history_path: Optional[str | Path] = None,
    access_plan_path: Optional[str | Path] = None,
    trunk_by_device: Optional[dict[str, list[int]]] = None,
    keyword: Optional[str] = None,
    network_type: Optional[str] = None,
) -> pd.DataFrame:
    if sheet_name not in plane_config:
        raise ValueError(f"平面 '{sheet_name}' 不在平面配置中。")
    plane = plane_config[sheet_name]
    actual_sheet_name = plane.get("sheet_name", sheet_name)
    kw = keyword or plane["keyword"]
    peer_kw = plane.get("peer_keyword", SPINE_TOKEN)
    nt = network_type or plane["network_type"]
    switch_data, _ = get_switch_data_l2(topology_path, actual_sheet_name, kw, peer_kw)
    vlan = get_vlan_for_plane(resource_path, nt)
    logger.info("%s VLAN: %s", nt, vlan)
    switch_mlag_df = get_all_switch_mlag_data(topology_path, actual_sheet_name)
    return allocate_connection(
        switch_data,
        vlan,
        nt,
        switch_mlag_df,
        interconnect_history_path,
        access_plan_path,
        trunk_by_device=trunk_by_device,
    )
