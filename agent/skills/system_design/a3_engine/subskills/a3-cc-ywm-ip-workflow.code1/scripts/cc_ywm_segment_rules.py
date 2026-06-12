"""存储业务面网段规划（对齐 a3_i2 / a3_i3 prompt，IP 需求 = 起始端设备数 × 8）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Dict, List, Optional, Tuple

from dw_manage_segment_rules import (
    SEGMENT_COUNT_INSUFFICIENT,
    SEGMENT_USABLE_IP_INSUFFICIENT,
    VLAN_INSUFFICIENT,
    SwitchGateway,
    compute_gateway,
    enumerate_usable_ips_in_pool,
    is_non_assignable_plan_segment,
    parse_ip_pool_bounds,
    parse_vlan_or_insufficient,
    plan_switch_gateways_leaf_i3,
    split_ip_range,
    usable_ip_capacity_excluding_gateway,
)

IP_DEMAND_PER_NODE = 8

__all__ = [
    "IP_DEMAND_PER_NODE",
    "SEGMENT_COUNT_INSUFFICIENT",
    "SEGMENT_USABLE_IP_INSUFFICIENT",
    "SwitchGateway",
    "compute_gateway",
    "enumerate_usable_ips_in_pool",
    "ip_demand_for_nodes",
    "is_non_assignable_plan_segment",
    "parse_ip_pool_bounds",
    "plan_switch_gateways_glm_i2",
    "plan_switch_gateways_leaf_i3",
    "split_ip_range",
    "switch_gateways_to_dataframe",
    "switch_gateways_to_markdown",
    "transfer_gateways_to_spines",
]


def ip_demand_for_nodes(node_count: int) -> int:
    return max(int(node_count), 0) * IP_DEMAND_PER_NODE


def plan_switch_gateways_glm_i2(
    *,
    switch_list: List[str],
    switch_to_nodes: Dict[str, List[str]],
    subnets: List[IPv4Network],
    mask: int,
    gateway_mode: object,
    vlan_raw: object,
) -> Tuple[List[SwitchGateway], int, int]:
    """I2：多 Leaf 可共用网段；累加维度为 IP 数量（起始端设备数×8）。"""
    if not switch_list:
        return [], 0, 0

    vlan_s = str(vlan_raw).strip()
    vlan_is_range = bool(re.match(r"^\d+\s*-\s*\d+$", vlan_s))

    out: List[SwitchGateway] = []
    subnet_idx = 0
    group_idx = 0
    current_capacity: Optional[int] = None
    current_network: Optional[IPv4Network] = None
    current_gateway: Optional[IPv4Address] = None
    current_vlan: Optional[str] = None
    acc_ips = 0
    acc_switches = 0

    def _start_new_group() -> bool:
        nonlocal subnet_idx, group_idx, current_capacity, current_network
        nonlocal current_gateway, current_vlan, acc_ips, acc_switches
        if subnet_idx >= len(subnets):
            return False
        current_network = subnets[subnet_idx]
        current_gateway = compute_gateway(current_network, gateway_mode)
        current_capacity = usable_ip_capacity_excluding_gateway(current_network, current_gateway)
        if vlan_is_range:
            current_vlan = parse_vlan_or_insufficient(vlan_raw, group_idx)
        else:
            current_vlan = parse_vlan_or_insufficient(vlan_raw, 0)
        acc_ips = 0
        acc_switches = 0
        subnet_idx += 1
        group_idx += 1
        return True

    if not _start_new_group():
        return (
            [
                SwitchGateway(
                    name=sw,
                    network_segment=SEGMENT_COUNT_INSUFFICIENT,
                    gateway="",
                    mask=mask,
                    vlan="",
                )
                for sw in switch_list
            ],
            subnet_idx,
            group_idx,
        )

    for idx, sw in enumerate(switch_list):
        demand = ip_demand_for_nodes(len(switch_to_nodes.get(sw, [])))
        if (
            current_capacity is None
            or current_network is None
            or current_gateway is None
            or current_vlan is None
        ):
            raise RuntimeError("internal planning state not initialized")

        if acc_ips + demand > current_capacity:
            if not _start_new_group():
                for sw2 in switch_list[idx:]:
                    out.append(
                        SwitchGateway(
                            name=sw2,
                            network_segment=SEGMENT_COUNT_INSUFFICIENT,
                            gateway="",
                            mask=mask,
                            vlan="",
                        )
                    )
                return out, subnet_idx, group_idx
            if current_capacity is None or current_capacity <= 0:
                out.append(
                    SwitchGateway(
                        name=sw,
                        network_segment=SEGMENT_USABLE_IP_INSUFFICIENT,
                        gateway="",
                        mask=mask,
                        vlan="",
                    )
                )
                continue
            if demand > current_capacity:
                out.append(
                    SwitchGateway(
                        name=sw,
                        network_segment=SEGMENT_USABLE_IP_INSUFFICIENT,
                        gateway="",
                        mask=mask,
                        vlan="",
                    )
                )
                continue

        acc_ips += demand
        acc_switches += 1

        if acc_switches > current_capacity:
            acc_ips -= demand
            acc_switches -= 1
            out.append(
                SwitchGateway(
                    name=sw,
                    network_segment=SEGMENT_USABLE_IP_INSUFFICIENT,
                    gateway="",
                    mask=mask,
                    vlan="",
                )
            )
            continue

        out.append(
            SwitchGateway(
                name=sw,
                network_segment=str(current_network),
                gateway=str(current_gateway),
                mask=mask,
                vlan=str(current_vlan),
            )
        )

    return out, subnet_idx, group_idx


def transfer_gateways_to_spines(
    leaf_spine_mapping: Dict[str, List[str]],
    leaf_gateway_list: List[SwitchGateway],
) -> List[SwitchGateway]:
    if not leaf_spine_mapping:
        return [
            SwitchGateway(
                name="",
                network_segment=sw.network_segment,
                gateway=sw.gateway,
                vlan=sw.vlan,
                mask=sw.mask,
            )
            for sw in leaf_gateway_list
        ]

    spine_config: Dict[str, Dict[str, Tuple[str, str, int]]] = {}
    for gw in leaf_gateway_list:
        if not gw.vlan or not gw.gateway:
            continue
        for spine_name in leaf_spine_mapping.get(gw.name, []):
            spine_config.setdefault(spine_name, {})
            spine_config[spine_name][gw.vlan] = (gw.network_segment, gw.gateway, gw.mask)

    result: List[SwitchGateway] = []
    for spine_name, vlan_entries in spine_config.items():
        for vlan, (network_segment, gateway, mask) in vlan_entries.items():
            result.append(
                SwitchGateway(
                    name=spine_name,
                    network_segment=network_segment,
                    gateway=gateway,
                    mask=mask,
                    vlan=vlan,
                )
            )
    return result


def switch_gateways_to_markdown(rows: List[SwitchGateway], header_switch: str = "leaf交换机") -> str:
    lines = [
        f"|{header_switch}|网段|网关|VLAN|掩码位数|",
        "|---|---|---|---|---|",
    ]
    for sg in rows:
        lines.append(f"|{sg.name}|{sg.network_segment}|{sg.gateway}|{sg.vlan}|{sg.mask}|")
    return "\n".join(lines)


def switch_gateways_to_dataframe(rows: List[SwitchGateway], switch_col: str = "leaf交换机"):
    import pandas as pd

    if not rows:
        return pd.DataFrame(columns=[switch_col, "网段", "网关", "VLAN", "掩码位数"])
    return pd.DataFrame(
        [
            {
                switch_col: sg.name,
                "网段": sg.network_segment,
                "网关": sg.gateway,
                "VLAN": sg.vlan,
                "掩码位数": sg.mask,
            }
            for sg in rows
        ]
    )
