"""SPINE 可共用网段 / LEAF 一机一网段；网关与可用 IP 语义见 compute_gateway / enumerate_*。"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SHARED_DIR = Path(__file__).resolve().parents[2] / "_runtime_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
from segment_split import (  # noqa: E402
    compute_gateway_safe,
    enumerate_usable_ips_in_pool_bounded,
    parse_ip_pool_bounds,
    split_ip_range_capped,
)

SEGMENT_COUNT_INSUFFICIENT = "网段个数不足"
SEGMENT_USABLE_IP_INSUFFICIENT = "可用IP不足"
VLAN_INSUFFICIENT = "vlan不足"

NON_ASSIGNABLE_PLAN_SEGMENTS = frozenset(
    {SEGMENT_COUNT_INSUFFICIENT, SEGMENT_USABLE_IP_INSUFFICIENT}
)


def is_non_assignable_plan_segment(network_segment: str) -> bool:
    return network_segment in NON_ASSIGNABLE_PLAN_SEGMENTS

GATEWAY_MODE_START_ALIASES = frozenset(
    {"网段起始位", "首", "起", "start", "Start", "START"}
)
GATEWAY_MODE_END_ALIASES = frozenset(
    {"网段末位", "网段结束位", "末", "end", "last", "End", "LAST"}
)

IP_POOL_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
)


@dataclass(frozen=True)
class SwitchGateway:
    name: str
    network_segment: str
    gateway: str
    mask: int
    vlan: str


def split_ip_range(ip_range_str: str, target_prefix: int, max_switch_count: int) -> List[IPv4Network]:
    """按交换机数量上限切分地址池（见 _runtime_shared.segment_split）。"""
    return split_ip_range_capped(ip_range_str, target_prefix, max_switch_count)


def compute_gateway(network: IPv4Network, gateway_mode_raw: object) -> IPv4Address:
    return compute_gateway_safe(network, gateway_mode_raw)


def usable_ip_capacity_excluding_gateway(network: IPv4Network, _gateway: IPv4Address) -> int:
    total_hosts = max(network.num_addresses - 2, 0)
    if total_hosts <= 0:
        return 0
    return max(total_hosts - 1, 0)


def parse_vlan(vlan_raw: object, idx0: int) -> str:
    s = str(vlan_raw).strip()
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", s)
    if m:
        start = int(m.group(1))
        end = int(m.group(2))
        v = start + idx0
        if v > end:
            raise ValueError(f"VLAN range exhausted: vlan_raw={s!r}, idx={idx0}")
        return str(v)
    if re.match(r"^\d+$", s):
        return s
    raise ValueError(f"invalid VLAN*: {s!r} (expected '100' or '100-199')")


def parse_vlan_or_insufficient(vlan_raw: object, idx0: int) -> str:
    try:
        return parse_vlan(vlan_raw, idx0)
    except ValueError:
        return VLAN_INSUFFICIENT


def classify_spine_or_leaf(switch_name: str) -> str:
    return "spine" if "SPINE" in str(switch_name).upper() else "leaf"


def plan_switch_gateways_with_sharing(
    *,
    switch_list: List[str],
    switch_to_servers: Dict[str, List[str]],
    subnets: List[IPv4Network],
    mask: int,
    gateway_mode: object,
    vlan_raw: object,
) -> Tuple[List[SwitchGateway], int, int]:
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
    acc_nodes = 0
    acc_switches = 0

    def _start_new_group() -> bool:
        nonlocal subnet_idx, group_idx, current_capacity, current_network, current_gateway, current_vlan, acc_nodes, acc_switches
        if subnet_idx >= len(subnets):
            return False
        current_network = subnets[subnet_idx]
        current_gateway = compute_gateway(current_network, gateway_mode)
        current_capacity = usable_ip_capacity_excluding_gateway(current_network, current_gateway)
        if vlan_is_range:
            current_vlan = parse_vlan_or_insufficient(vlan_raw, group_idx)
        else:
            current_vlan = parse_vlan_or_insufficient(vlan_raw, 0)
        acc_nodes = 0
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
        nodes = len(list(switch_to_servers.get(sw, [])))
        if current_capacity is None or current_network is None or current_gateway is None or current_vlan is None:
            raise RuntimeError("internal planning state not initialized")

        if acc_nodes + nodes > current_capacity:
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
            if nodes > current_capacity:
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

        acc_nodes += nodes
        acc_switches += 1

        if acc_switches > current_capacity:
            acc_nodes -= nodes
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


def enumerate_usable_ips_in_pool(
    subnet: IPv4Network,
    gateway: IPv4Address,
    pool_start: IPv4Address,
    pool_end: IPv4Address,
) -> List[IPv4Address]:
    return enumerate_usable_ips_in_pool_bounded(subnet, gateway, pool_start, pool_end)


def plan_switch_gateways_leaf_i3(
    *,
    switch_list: List[str],
    subnets: List[IPv4Network],
    mask: int,
    gateway_mode: object,
    vlan_raw: object,
    vlan_subnet_offset: int = 0,
) -> List[SwitchGateway]:
    out: List[SwitchGateway] = []
    vlan_s = str(vlan_raw).strip()
    vlan_is_range = bool(re.match(r"^\d+\s*-\s*\d+$", vlan_s))
    for i, sw in enumerate(switch_list):
        if i >= len(subnets):
            out.append(
                SwitchGateway(
                    name=sw,
                    network_segment=SEGMENT_COUNT_INSUFFICIENT,
                    gateway="",
                    mask=mask,
                    vlan="",
                )
            )
            continue
        net = subnets[i]
        gw = compute_gateway(net, gateway_mode)
        vidx = vlan_subnet_offset + i
        vlan = parse_vlan_or_insufficient(vlan_raw, vidx if vlan_is_range else 0)
        out.append(
            SwitchGateway(
                name=sw,
                network_segment=str(net),
                gateway=str(gw),
                mask=mask,
                vlan=str(vlan),
            )
        )
    return out
