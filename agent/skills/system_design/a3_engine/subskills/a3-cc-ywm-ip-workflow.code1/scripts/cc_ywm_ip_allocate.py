"""存储业务面 IP 分配（对齐 a3_l2_cc_ywm / a3_cc_ywm）。"""

from __future__ import annotations

import re
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
from typing import Dict, List, Optional

import pandas as pd

from cc_ywm_io import WEB_NETWORK_TYPE_NAME
from cc_ywm_segment_rules import (
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


def find_available_ip_vlan_range(
    ip_pool: str,
    vlan_pool: str,
    switch_network_segment_info: List[SwitchGateway],
) -> Dict[str, str]:
    """对齐 a3_cc_ywm_ip_address.find_available_ip_vlan_range（OSP+OSA800 混合场景）。"""
    start_ip = ip_address(ip_pool.split("-")[0].strip())
    end_ip = ip_address(ip_pool.split("-")[1].strip())
    start_vlan, end_vlan = map(int, vlan_pool.strip().split("-"))
    if not (1 <= start_vlan <= end_vlan <= 4094):
        raise ValueError("VLAN 必须在 1~4094 范围内")

    used_networks = []
    used_vlans = set()
    for sg in switch_network_segment_info:
        try:
            used_networks.append(ip_network(sg.network_segment, strict=False))
        except ValueError:
            pass
        try:
            vlan = int(str(sg.vlan).strip())
            if 1 <= vlan <= 4094:
                used_vlans.add(vlan)
        except ValueError:
            continue

    current_ip = start_ip
    available_ip_start = None
    available_ip_end = None
    while current_ip <= end_ip:
        is_used = any(current_ip in net for net in used_networks)
        if not is_used:
            if available_ip_start is None:
                available_ip_start = current_ip
            available_ip_end = current_ip
        elif available_ip_start is not None:
            break
        current_ip += 1

    if available_ip_start is None:
        raise ValueError("IP已分配完，IP池中没有可用地址，请重试尝试分配或增大IP池")

    for vlan in range(start_vlan, end_vlan + 1):
        if vlan not in used_vlans:
            return {
                "start_ip": str(available_ip_start),
                "end_ip": str(available_ip_end),
                "start_vlan": str(vlan),
                "end_vlan": str(end_vlan),
            }

    raise ValueError("VLAN 池中没有足够的连续 VLAN")


def allocate_osp_ips(
    *,
    osp_original_df: pd.DataFrame,
    switch_network_segment_info: List[SwitchGateway],
    ip_pool: str,
    web_network_type_name: str = WEB_NETWORK_TYPE_NAME,
) -> pd.DataFrame:
    """对齐 handle_osp9950_case / 混合场景 OSP 循环。"""
    equipment_info_df = osp_original_df.drop_duplicates(subset=["节点名称"], keep="first")
    pool_start, pool_end = parse_ip_pool_bounds(ip_pool)
    osp_all_results: List[dict] = []

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
        devices = equipment_info_df[
            equipment_info_df["目的端设备"] == leaf
        ].reset_index(drop=True)
        usable_ips = get_usable_ips_str(subnet, gateway, pool_start, pool_end)

        for i, row in devices.iterrows():
            node_name = row["节点名称"]
            device_name = "-".join(node_name.split("-")[:-1])
            osp_all_results.append(
                {
                    "集群": _parse_cluster_id(device_name),
                    "硬盘池": _parse_disk_pool(device_name),
                    "设备名称": device_name,
                    "节点": node_name,
                    f"{web_network_type_name}地址": str(get_usable_ip(usable_ips, i)),
                    f"{web_network_type_name}掩码": f"{switch_info.mask}",
                    f"{web_network_type_name}网关": f"{gateway}",
                    f"{web_network_type_name}VLAN": vlan,
                }
            )

    return pd.DataFrame(osp_all_results)


def _get_next_network(network: IPv4Network) -> IPv4Network:
    prefix = network.prefixlen
    next_network_address = IPv4Address(
        int(network.network_address) + (1 << (32 - prefix))
    )
    return IPv4Network(f"{next_network_address}/{prefix}", strict=False)


def _get_gateway(network: IPv4Network, position: str) -> str:
    hosts = list(network.hosts())
    if position == "网段起始位":
        return str(hosts[0])
    if position == "网段结束位":
        return str(hosts[-1])
    raise ValueError(f"不支持的网关位置描述: {position}")


def generate_osa800_ywm_ip_address(
    osa800_original_df: pd.DataFrame,
    new_ip_vlan_dict: dict,
    mask: str,
    gateway_info: str,
) -> pd.DataFrame:
    """bond4（负载均衡）：对齐 generate_osa800_ywm_ip_address。"""
    start_ip = IPv4Address(new_ip_vlan_dict["start_ip"])
    vlan1 = int(new_ip_vlan_dict["start_vlan"])
    vlan2 = vlan1 + 1

    network1 = IPv4Network(f"{start_ip}/{mask}", strict=False)
    network2 = _get_next_network(network1)
    gw1 = _get_gateway(network1, gateway_info)
    gw2 = _get_gateway(network2, gateway_info)

    def _ip_gen(network: IPv4Network, gateway_ip: str):
        for ip in network.hosts():
            if str(ip) != gateway_ip:
                yield ip

    ip_gen1 = _ip_gen(network1, gw1)
    ip_gen2 = _ip_gen(network2, gw2)
    device_ip_map: Dict[str, Dict[str, tuple]] = {}
    result_list: List[dict] = []

    for _, row in osa800_original_df.iterrows():
        device = row["起始端设备"]
        physical_intf = row["起始端接口名称"]
        if physical_intf.startswith("L0.") or physical_intf.startswith("R0."):
            logical_intf = "bond0" if physical_intf.startswith("L0.") else "bond1"
        else:
            continue
        if device not in device_ip_map:
            try:
                device_ip_map[device] = {
                    "bond0": (str(next(ip_gen1)), str(next(ip_gen2))),
                    "bond1": (str(next(ip_gen1)), str(next(ip_gen2))),
                }
            except StopIteration as exc:
                raise ValueError("IP 地址不足，无法继续分配") from exc
        ip1_val, ip2_val = device_ip_map[device][logical_intf]
        result_list.append(
            {
                "设备名称": device,
                "本端端口": physical_intf,
                "IP1": ip1_val,
                "VLAN1": str(vlan1),
                "网关1": gw1,
                "IP2": ip2_val,
                "VLAN2": str(vlan2),
                "网关2": gw2,
                "掩码": mask,
                "组网模式": "bond4（负载均衡）",
            }
        )

    return pd.DataFrame(
        result_list,
        columns=[
            "设备名称",
            "本端端口",
            "IP1",
            "VLAN1",
            "网关1",
            "IP2",
            "VLAN2",
            "网关2",
            "掩码",
            "组网模式",
        ],
    )


def generate_osa800_ips_ywm_ip_address(
    osa800_original_df: pd.DataFrame,
    new_ip_vlan_dict: dict,
    mask: str,
    gateway_info: str,
) -> pd.DataFrame:
    """多 IP 模式（L2 且组网场景不含 bond）：对齐 generate_osa800_ips_ywm_ip_address。"""
    start_ip = IPv4Address(new_ip_vlan_dict["start_ip"])
    vlan1 = int(new_ip_vlan_dict["start_vlan"])
    vlan2 = vlan1 + 1

    network1 = IPv4Network(f"{start_ip}/{mask}", strict=False)
    network2 = _get_next_network(network1)
    gw1 = _get_gateway(network1, gateway_info)
    gw2 = _get_gateway(network2, gateway_info)

    def _ip_gen(network: IPv4Network, gateway_ip: str):
        for ip in network.hosts():
            if str(ip) != gateway_ip:
                yield ip

    ip_gen1 = _ip_gen(network1, gw1)
    ip_gen2 = _ip_gen(network2, gw2)
    result_list: List[dict] = []

    def _interface_number(physical_intf: str) -> int:
        return int(physical_intf.split("P")[-1])

    for _, row in osa800_original_df.iterrows():
        device = row["起始端设备"]
        physical_intf = row["起始端接口名称"]
        interface_num = _interface_number(physical_intf)
        try:
            if interface_num % 2 == 0:
                ip = next(ip_gen1)
                vlan = vlan1
                gw = gw1
            else:
                ip = next(ip_gen2)
                vlan = vlan2
                gw = gw2
        except StopIteration as exc:
            raise ValueError("IP 地址不足，无法继续分配") from exc
        result_list.append(
            {
                "设备名称": device,
                "本端端口": physical_intf,
                "IP": str(ip),
                "VLAN": str(vlan),
                "网关": gw,
                "掩码": mask,
                "组网模式": "多IP",
            }
        )

    return pd.DataFrame(
        result_list,
        columns=["设备名称", "本端端口", "IP", "VLAN", "网关", "掩码", "组网模式"],
    )


def allocate_osa800_ips(
    *,
    osa800_original_df: pd.DataFrame,
    ip_vlan_dict: dict,
    mask: str,
    gateway_info: str,
    layer: str,
    net_mode: str,
    mixed_with_osp: bool,
) -> pd.DataFrame:
    """
    - L3 / 混合：固定 bond4（generate_osa800_ywm_ip_address）
    - L2 仅 OSA800：bond 在 net_mode 中 → bond4，否则多 IP
    """
    if mixed_with_osp or layer.upper() == "L3":
        return generate_osa800_ywm_ip_address(
            osa800_original_df, ip_vlan_dict, mask, gateway_info
        )
    if "bond" in net_mode.lower():
        return generate_osa800_ywm_ip_address(
            osa800_original_df, ip_vlan_dict, mask, gateway_info
        )
    return generate_osa800_ips_ywm_ip_address(
        osa800_original_df, ip_vlan_dict, mask, gateway_info
    )
