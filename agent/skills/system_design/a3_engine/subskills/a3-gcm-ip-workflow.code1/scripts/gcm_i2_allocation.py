"""i2（二层聚合）语义：整网单一子网内，按地址池裁剪可用主机地址并顺序分配给全部节点（管存面 GCM）。"""

from __future__ import annotations

import ipaddress
import sys
from pathlib import Path
from typing import List, Tuple, Union

import pandas as pd

from dw_manage_segment_rules import parse_ip_pool_bounds  # type: ignore

_SHARED_DIR = Path(__file__).resolve().parents[2] / "_runtime_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
from segment_split import (  # noqa: E402
    compute_gateway_safe,
    network_safe_for_host_enum,
    pool_fits_in_network,
)


def determine_gateway(network: ipaddress.IPv4Network, gateway_config: str) -> ipaddress.IPv4Address:
    return compute_gateway_safe(network, gateway_config)


def allocate_flat_gcm_ips(
    equipment_names_ordered: List[str],
    *,
    ip_pool: str,
    gateway_config: str,
    vlan_raw: str,
    min_mask_bits: Union[int, str],
    plane_label: str,
) -> Tuple[pd.DataFrame, ipaddress.IPv4Network]:
    start_ip, end_ip = parse_ip_pool_bounds(ip_pool)
    raw_mask = str(min_mask_bits).strip()
    mask_int = int(raw_mask.split(".")[0] if "." in raw_mask else raw_mask)
    num_nodes = len(equipment_names_ordered)
    if num_nodes == 0:
        return pd.DataFrame(), ipaddress.IPv4Network(f"{start_ip}/{mask_int}", strict=False)

    total_available_ips = int(end_ip) - int(start_ip) + 1
    if num_nodes > total_available_ips:
        raise ValueError(f"节点数量 {num_nodes} 大于地址池内 IP 数 {total_available_ips}")

    required_hosts = num_nodes + 2
    chosen_prefix = mask_int
    for prefix in range(mask_int, 0, -1):
        block_size = 2 ** (32 - prefix)
        if block_size < required_hosts:
            continue
        network = ipaddress.IPv4Network(f"{start_ip}/{prefix}", strict=False)
        if pool_fits_in_network(network, start_ip, end_ip) and network_safe_for_host_enum(network):
            chosen_prefix = prefix
            break
    else:
        raise ValueError("无法找到合适子网掩码，使地址池能容纳所有节点")

    network = ipaddress.IPv4Network(f"{start_ip}/{chosen_prefix}", strict=False)
    gateway_ip = determine_gateway(network, gateway_config)

    excluded = {network.network_address, network.broadcast_address, gateway_ip}
    available_ips: List[str] = []
    for ip in network:
        if ip in excluded:
            continue
        if start_ip <= ip <= end_ip:
            available_ips.append(str(ip))
            if len(available_ips) >= num_nodes:
                break

    if len(available_ips) < num_nodes:
        raise ValueError(f"地址池内可用 IP {len(available_ips)}，不足以分配给 {num_nodes} 个节点")

    rows = []
    for idx, node_name in enumerate(equipment_names_ordered):
        rows.append(
            {
                "设备名称": node_name,
                f"{plane_label}地址": available_ips[idx],
                f"{plane_label}掩码": str(chosen_prefix),
                f"{plane_label}网关": str(gateway_ip),
                f"{plane_label}VLAN": str(vlan_raw).strip(),
                "绑定模式": "bond1",
            }
        )
    return pd.DataFrame(rows), network
