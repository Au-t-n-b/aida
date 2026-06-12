"""存储样本面 IP 分配（对齐 a3_cc_ybm_ip_address.py）。"""

from __future__ import annotations

import re
from ipaddress import IPv4Address, IPv4Network, ip_address
from typing import List, Optional

import pandas as pd

from cc_ybm_io import WEB_NETWORK_TYPE_NAME
from cc_ybm_segment_rules import SwitchGateway, is_non_assignable_plan_segment
from dw_manage_segment_rules import parse_ip_pool_bounds


def calculate_control_start_ip(switch_info: SwitchGateway) -> str:
    """对齐 calculate_control_start_ip：/(mask+1) 后第 2 子网首个主机。"""
    net = IPv4Network(switch_info.network_segment, strict=True)
    subnets = list(net.subnets(new_prefix=int(switch_info.mask) + 1))
    control_subnet = subnets[1]
    return str(list(control_subnet.hosts())[0])


def determine_gateway(
    start_ip: IPv4Address, network: IPv4Network, gateway_config: str
) -> IPv4Address:
    first_ip = network.network_address + 1
    last_ip = network.broadcast_address - 1
    mode = gateway_config.strip()
    if mode == "网段起始位":
        return IPv4Address(first_ip)
    if mode == "网段结束位":
        return IPv4Address(last_ip)
    try:
        return IPv4Address(mode)
    except Exception as exc:
        raise ValueError(
            f"网关配置不合法：{gateway_config}，应为「网段起始位」「网段结束位」或合法 IP"
        ) from exc


def allocate_osa800_independent_ips(
    osa800_df: pd.DataFrame,
    ip_pool: str,
    gateway_config: str,
    vlan_raw: str,
    web_network_type_name: str = WEB_NETWORK_TYPE_NAME,
) -> pd.DataFrame:
    """对齐 allocate_ips_and_generate_df（OSA800 独立 IP）。"""
    start_ip, end_ip = parse_ip_pool_bounds(ip_pool)
    num_nodes = len(osa800_df)
    if num_nodes == 0:
        return pd.DataFrame()

    required_hosts = num_nodes + 3
    mask: Optional[int] = None
    for prefix in range(32, 0, -1):
        if 2 ** (32 - prefix) >= required_hosts:
            mask = prefix
            break
    if mask is None:
        raise ValueError("无法找到合适的子网来容纳所有节点")

    network = IPv4Network(f"{start_ip}/{mask}", strict=False)
    gateway_ip = determine_gateway(start_ip, network, gateway_config)
    excluded = {network.network_address, network.broadcast_address, gateway_ip}
    available_ips: List[str] = []
    for current_ip in network.hosts():
        if current_ip in excluded:
            continue
        if current_ip < start_ip or current_ip > end_ip:
            continue
        available_ips.append(str(current_ip))

    if len(available_ips) < num_nodes:
        raise ValueError(
            f"地址池中可用 IP 数量 {len(available_ips)} 不足于分配给 {num_nodes} 个节点，"
            f"网段自动计算的掩码为 {mask}"
        )

    vlan = str(vlan_raw).split("-")[0].strip()
    rows: List[dict] = []
    for idx, row in enumerate(osa800_df.itertuples()):
        node_name = row.节点名称
        parts = str(node_name).rsplit("-", 1)
        device_name = parts[0]
        interface_name = parts[1] if len(parts) > 1 else ""
        rows.append(
            {
                "设备名称": device_name,
                "本端端口": interface_name,
                "IP": available_ips[idx],
                "掩码": str(mask),
                "网关": str(gateway_ip),
                "VLAN": vlan,
                "组网模式": "独立IP",
            }
        )
    return pd.DataFrame(rows)


def _get_usable_ips_str(
    subnet: IPv4Network,
    gateway: IPv4Address,
    pool_start: IPv4Address,
    pool_end: IPv4Address,
) -> List[str]:
    usable: List[str] = []
    for current_ip in subnet.hosts():
        ip = IPv4Address(current_ip)
        if ip == gateway:
            continue
        if ip < pool_start or ip > pool_end:
            continue
        usable.append(str(ip))
    return usable


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


def allocate_osp_ybm_ips(
    *,
    original_df: pd.DataFrame,
    switch_network_segment_info: List[SwitchGateway],
    ip_pool: str,
    web_network_type_name: str = WEB_NETWORK_TYPE_NAME,
) -> pd.DataFrame:
    """对齐 a3_cc_ybm OSP 分支：双样本面接口 + 控制接口，样本面须在控制段之前。"""
    equipment_info_df = original_df.drop_duplicates(subset=["节点名称"], keep="first")
    pool_start, pool_end = parse_ip_pool_bounds(ip_pool)
    all_results: List[dict] = []

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
        leaf_devices_df = equipment_info_df[
            equipment_info_df["目的端设备"] == leaf
        ].reset_index(drop=True)

        usable_ips = _get_usable_ips_str(subnet, gateway, pool_start, pool_end)
        if len(usable_ips) < len(leaf_devices_df) * 2 + 1:
            raise ValueError("可用IP不足，请检查")

        control_start_ip = IPv4Address(calculate_control_start_ip(switch_info))
        sample_start_ip = IPv4Address(usable_ips[0])
        sample_end_ip = IPv4Address(usable_ips[-1])

        sample_interface_ips: List[tuple] = []
        sample_ip_cursor = sample_start_ip
        for _ in range(len(leaf_devices_df)):
            ip1 = sample_ip_cursor
            ip2 = ip1 + 1
            if ip2 > sample_end_ip:
                raise ValueError("可用IP不足，请检查")
            if ip2 >= control_start_ip:
                raise ValueError("可用IP不足，需要预留部分IP用于控制接口，请检查")
            sample_interface_ips.append((str(ip1), str(ip2)))
            sample_ip_cursor = ip2 + 1

        control_ips: List[str] = []
        control_ip_cursor = control_start_ip
        for _ in range(len(leaf_devices_df)):
            control_ips.append(str(control_ip_cursor))
            control_ip_cursor += 1

        for i, row in leaf_devices_df.iterrows():
            node_name = row["节点名称"]
            device_name = "-".join(str(node_name).split("-")[:-1])
            all_results.append(
                {
                    "集群": _parse_cluster_id(device_name),
                    "硬盘池": _parse_disk_pool(device_name),
                    "设备名称": device_name,
                    "节点": node_name,
                    f"{web_network_type_name}接口1": sample_interface_ips[i][0],
                    f"{web_network_type_name}接口2": sample_interface_ips[i][1],
                    "控制接口": control_ips[i],
                    f"{web_network_type_name}掩码": str(mask),
                    f"{web_network_type_name}网关": str(gateway),
                    f"{web_network_type_name}VLAN": vlan,
                }
            )

    return pd.DataFrame(all_results)


def parse_ip_vlan_pool(ip_pool: str, vlan_pool: str) -> dict:
    ip_parts = ip_pool.split("-")
    if len(ip_parts) != 2:
        raise ValueError("IP 地址池格式错误，应为 '起始IP-结束IP'")
    vlan_parts = vlan_pool.split("-")
    if len(vlan_parts) != 2 or not all(p.isdigit() for p in vlan_parts):
        raise ValueError("VLAN 池格式错误，应为 '起始VLAN-结束VLAN'，且为整数")
    return {
        "start_ip": ip_parts[0].strip(),
        "end_ip": ip_parts[1].strip(),
        "start_vlan": int(vlan_parts[0].strip()),
        "end_vlan": int(vlan_parts[1].strip()),
    }


def allocate_od1600t_ips(
    equipment_info_df: pd.DataFrame,
    ip_pool: str,
    mask: str,
    vlan_pool: str,
) -> pd.DataFrame:
    """对齐 od1600t_ip_address_generate。"""
    ip_vlan_dict = parse_ip_vlan_pool(ip_pool, vlan_pool)
    start_vlan = int(ip_vlan_dict["start_vlan"])
    end_vlan = int(ip_vlan_dict["end_vlan"])
    pool_start, pool_end = parse_ip_pool_bounds(ip_pool)
    raw_mask = str(mask).strip()
    mask_int = int(raw_mask.split(".")[0] if "." in raw_mask else raw_mask)

    start = int(pool_start)
    end = int(pool_end)
    available_ips: List[tuple] = []
    current = start
    while current <= end:
        network = IPv4Network(f"{ip_address(current)}/{mask_int}", strict=False)
        for ip in network.hosts():
            ip_int = int(ip)
            if start <= ip_int <= end:
                gateway = network.network_address
                available_ips.append((str(ip), str(gateway)))
        current = int(network.broadcast_address) + 1

    if len(available_ips) < len(equipment_info_df):
        raise ValueError(
            f"网段范围只能容纳 {len(available_ips)} 个/{mask_int}子网，"
            f"但需要分配 {len(equipment_info_df)} 条链路"
        )

    data: List[dict] = []
    equipment_info_rest_df = equipment_info_df.reset_index(drop=True)
    device_group = equipment_info_rest_df.groupby("本端设备名称", sort=False)
    available_ip_index = 0
    for _device_name, device_data in device_group:
        current_vlan = start_vlan
        for _, row in device_data.iterrows():
            if current_vlan > end_vlan:
                raise ValueError(
                    f"VLAN范围无效：当前分配VLAN={current_vlan}，超出最大VLAN={end_vlan}"
                )
            if available_ip_index + 2 > len(available_ips):
                raise ValueError(
                    f"IP范围无效：将要分配第 {available_ip_index + 2} 个IP，"
                    f"超出最大 {len(available_ips)} 个"
                )
            data.append(
                {
                    "本端设备名称": row["本端设备名称"],
                    "本端接口名称": row["本端接口名称"],
                    "本端地址": f"{available_ips[available_ip_index][0]}/{mask_int}",
                    "对端地址": f"{available_ips[available_ip_index + 1][0]}/{mask_int}",
                    "VLAN ID": current_vlan,
                    "对端接口名称": row["对端接口名称"],
                    "对端设备名称": row["对端设备名称"],
                }
            )
            available_ip_index += 2
            current_vlan += 1

    return pd.DataFrame(data)
