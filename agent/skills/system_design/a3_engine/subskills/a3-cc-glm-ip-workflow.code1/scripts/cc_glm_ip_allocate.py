"""存储管理面 IP 分配（对齐 a3_l2_cc_glm / a3_cc_glm 主循环）。"""

from __future__ import annotations

import re
from ipaddress import IPv4Address, IPv4Network
from typing import Dict, List, Optional, Tuple

import pandas as pd

from cc_glm_io import WEB_NETWORK_TYPE_NAME
from cc_glm_segment_rules import (
    SwitchGateway,
    enumerate_usable_ips_in_pool,
    is_non_assignable_plan_segment,
)
from dw_manage_segment_rules import parse_ip_pool_bounds


def get_usable_ips_str(
    subnet: IPv4Network,
    gateway: IPv4Address,
    pool_start: IPv4Address,
    pool_end: IPv4Address,
) -> List[str]:
    return [
        str(ip)
        for ip in enumerate_usable_ips_in_pool(subnet, gateway, pool_start, pool_end)
    ]


def get_usable_ip(usable_ips: List[str], i: int) -> str:
    if i < len(usable_ips):
        return usable_ips[i]
    raise ValueError(f"网段中可用IP数：{len(usable_ips)}，小于待分配设备数（需要下标 {i}）")


def _parse_cluster_id(device_name: str) -> str:
    cluster = device_name.split("-")[0]
    match = re.match(r"^([A-Za-z]+)(\d+)$", cluster)
    return match.group(2) if match else "1"


def _parse_disk_pool(device_name: str) -> str:
    pool = "1"
    for part in device_name.split("-"):
        if part.startswith("DP"):
            pool_num = "".join(filter(str.isdigit, part))
            if pool_num:
                pool = pool_num
            break
    return pool


def allocate_storage_manage_ips(
    *,
    original_df: pd.DataFrame,
    equipment_info_df: pd.DataFrame,
    switch_network_segment_info: List[SwitchGateway],
    ip_pool: str,
    web_network_type_name: str = WEB_NETWORK_TYPE_NAME,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    按 Leaf 子网分配 IP。
    返回 (普通节点表, OSA800 表)。
    """
    pool_start, pool_end = parse_ip_pool_bounds(ip_pool)
    all_results: List[dict] = []
    a800_results: List[dict] = []

    for switch_info in switch_network_segment_info:
        leaf = switch_info.name
        if is_non_assignable_plan_segment(switch_info.network_segment):
            raise ValueError(f"交换机 {leaf} 网段规划失败: {switch_info.network_segment}")

        try:
            subnet = IPv4Network(switch_info.network_segment, strict=True)
        except Exception as exc:
            raise ValueError("可用IP不足，请检查") from exc

        gateway = IPv4Address(switch_info.gateway)
        vlan = switch_info.vlan
        mask = switch_info.mask

        devices = equipment_info_df[
            (equipment_info_df["目的端设备"] == leaf)
            & (~equipment_info_df["节点名称"].str.contains("OSA800", na=False))
        ].reset_index(drop=True)
        a800_devices = equipment_info_df[
            equipment_info_df["节点名称"].str.contains("OSA800", na=False)
            & (equipment_info_df["目的端设备"] == leaf)
        ].reset_index(drop=True)

        usable_ips = get_usable_ips_str(subnet, gateway, pool_start, pool_end)

        for i, row in a800_devices.iterrows():
            node_name = row["节点名称"]
            device_name = "-".join(node_name.split("-")[:-1])
            port_name = node_name.split("-")[-1]
            a800_results.append(
                {
                    "设备名称": device_name,
                    "本端端口": port_name,
                    f"{web_network_type_name}地址": str(get_usable_ip(usable_ips, i)),
                    f"{web_network_type_name}掩码": f"{mask}",
                    f"{web_network_type_name}网关": f"{gateway}",
                    f"{web_network_type_name}VLAN": vlan,
                    "组网模式": "独立IP",
                }
            )

        assigned_devices: set = set()
        offset = 0
        for i, row in devices.iterrows():
            node_name = row["节点名称"]
            device_name = "-".join(node_name.split("-")[:-1])
            cluster_id = _parse_cluster_id(device_name)
            pool = _parse_disk_pool(device_name)
            is_first_node = device_name not in assigned_devices
            extra_fields: Dict[str, str] = {}
            if is_first_node:
                mgmt1 = (
                    str(get_usable_ip(usable_ips, i + offset + 8))
                    if (i + offset + 8) < len(usable_ips)
                    else ""
                )
                mgmt2 = (
                    str(get_usable_ip(usable_ips, i + offset + 9))
                    if (i + offset + 9) < len(usable_ips)
                    else ""
                )
                extra_fields = {
                    "集群模块管理地址1": mgmt1,
                    "集群模块管理地址2": mgmt2,
                }
                assigned_devices.add(device_name)
                offset += 2

            all_results.append(
                {
                    "集群": cluster_id,
                    "硬盘池": pool,
                    "设备名称": device_name,
                    "节点": node_name,
                    f"{web_network_type_name}地址": str(
                        get_usable_ip(usable_ips, i + offset - 2)
                    ),
                    f"{web_network_type_name}掩码": f"{mask}",
                    f"{web_network_type_name}网关": f"{gateway}",
                    f"{web_network_type_name}VLAN": vlan,
                    **extra_fields,
                }
            )

    result_df = pd.DataFrame(all_results).astype(object).fillna("")
    a800_df = pd.DataFrame(a800_results).astype(object).fillna("")
    return result_df, a800_df
