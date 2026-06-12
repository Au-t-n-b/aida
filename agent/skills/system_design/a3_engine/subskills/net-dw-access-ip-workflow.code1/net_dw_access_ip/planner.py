#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Offline rewrite of a3_net_dw_manage_ip_address.py.

The original project module reads topology/resource data through project DB/EDM
services and asks an LLM to calculate switch network segments. This module keeps
the same data contract but uses local Excel files and deterministic ipaddress
calculation so it can run outside the CPCIA_AGENT project.
"""

from __future__ import annotations

import ipaddress
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import pandas as pd


DEFAULT_SHEET_NAME = "网络带外管理面端口互联"
DEFAULT_RESOURCE_PLANE = "网络带外管理面"
OUTPUT_SHEET_NAME = "网络带外管理地址"
DEFAULT_OUTPUT_FILE = "A3网络带外管理地址规划.xlsx"
DEFAULT_INTERMEDIATE_FILE = "A3带外管理网关地址规划.xlsx"


@dataclass(frozen=True)
class SwitchGateway:
    name: str
    network_segment: str
    gateway: str
    vlan: str
    mask: str


@dataclass(frozen=True)
class ResourceInfo:
    network_plane: str
    ip_pool: str
    mask: int
    gateway_raw: str
    vlan_raw: str


@dataclass(frozen=True)
class PlanningResult:
    address_df: pd.DataFrame
    gateway_df: pd.DataFrame
    output_file: Path
    intermediate_file: Path | None


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _read_raw_sheet(excel_path: str | Path, sheet_name: str) -> pd.DataFrame:
    excel_path = Path(excel_path)
    candidates = [item.strip() for item in str(sheet_name).split("|") if item.strip()]
    xls = pd.ExcelFile(excel_path)
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return pd.read_excel(excel_path, sheet_name=candidate, header=None)
        except ValueError as exc:
            last_error = exc
    raise ValueError(
        f"未在 {excel_path.name} 中找到 sheet：{sheet_name}；可用 sheet：{', '.join(xls.sheet_names)}"
    ) from last_error


def _find_header_row(df: pd.DataFrame, keyword: str = "设备命名") -> int:
    for idx, row in df.iterrows():
        if row.astype(str).str.contains(keyword, case=False, na=False).any():
            return int(idx)
    raise ValueError(f"未找到包含'{keyword}'的行，请检查表格内容")


def _data_after_device_header(topology_file: str | Path, sheet_name: str) -> pd.DataFrame:
    df_all = _read_raw_sheet(topology_file, sheet_name)
    header_row_idx = _find_header_row(df_all, "设备命名")
    df = df_all.iloc[header_row_idx + 1 :].reset_index(drop=True)
    df = df.dropna(how="all")
    if df.empty or len(df.columns) < 2:
        raise ValueError(f"{sheet_name} 中未找到有效连线数据")
    return df


def get_net_device_data(topology_file: str | Path, sheet_name: str) -> dict[str, list[str]]:
    """Return {access_switch: [network_device, ...]} using the first and last columns."""
    df = _data_after_device_header(topology_file, sheet_name)
    result_df = pd.DataFrame(
        {
            "网络设备": df.iloc[:, 0],
            "接入交换机": df.iloc[:, -1],
        }
    )
    result_df = result_df.drop_duplicates()
    return result_df.groupby("接入交换机", sort=False)["网络设备"].apply(list).to_dict()


def get_switch_counts(topology_file: str | Path, sheet_name: str) -> list[tuple[str, int]]:
    """Return ordered (LEAF switch, node count) pairs."""
    df = _data_after_device_header(topology_file, sheet_name)
    switch_series = df.iloc[:, -1]
    switch_series = switch_series[switch_series.astype(str).str.contains("LEAF", case=False, na=False)]
    counts = switch_series.value_counts(sort=False)
    if counts.empty:
        raise ValueError(f"{sheet_name} 中未找到目的端/接入交换机包含 LEAF 的记录")
    return [(str(name), int(count)) for name, count in counts.items()]


def get_leaf_switches(topology_file: str | Path, sheet_name: str) -> list[str]:
    df = _data_after_device_header(topology_file, sheet_name)
    result: list[str] = []
    seen: set[str] = set()
    for value in df.iloc[:, -1].map(_clean_cell):
        if "LEAF" in value.upper() and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _find_column(columns: Iterable[object], pattern: str, *, required: bool = True) -> object | None:
    for col in columns:
        if re.search(pattern, str(col), re.IGNORECASE):
            return col
    if required:
        raise ValueError(f"未找到匹配列：{pattern}")
    return None


def _read_resource_sheet(resource_file: str | Path) -> pd.DataFrame:
    resource_file = Path(resource_file)
    df = pd.read_excel(resource_file, sheet_name=0, header=0)
    df.columns = [_clean_cell(col) for col in df.columns]
    return df


def read_resource_info(resource_file: str | Path, resource_plane: str = DEFAULT_RESOURCE_PLANE) -> ResourceInfo:
    df = _read_resource_sheet(resource_file)
    plane_col = _find_column(df.columns, r"^网络平面$")
    row = df[df[plane_col].map(_clean_cell) == resource_plane]
    if row.empty:
        raise ValueError(f"资源表中未找到网络平面：{resource_plane}")

    ip_pool_col = _find_column(df.columns, r"^地址池\*$")
    mask_col = _find_column(df.columns, r"最小规划掩码|掩码")
    gateway_col = _find_column(df.columns, r"^网关地址\*$")
    vlan_col = _find_column(df.columns, r"^VLAN\*$")

    first = row.iloc[0]
    mask_raw = _clean_cell(first[mask_col])
    mask_match = re.search(r"\d{1,2}", mask_raw)
    if not mask_match:
        raise ValueError(f"最小规划掩码为空或非法：{mask_raw}")
    mask = int(mask_match.group(0))
    if mask < 0 or mask > 32:
        raise ValueError(f"非法掩码位数：{mask}")

    return ResourceInfo(
        network_plane=_clean_cell(first[plane_col]),
        ip_pool=_clean_cell(first[ip_pool_col]),
        mask=mask,
        gateway_raw=_clean_cell(first[gateway_col]),
        vlan_raw=_clean_cell(first[vlan_col]),
    )


def parse_ip_pool(ip_pool: str) -> tuple[ipaddress.IPv4Address, ipaddress.IPv4Address]:
    match = re.match(
        r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s*-\s*(\d{1,3}(?:\.\d{1,3}){3})\s*$",
        str(ip_pool),
    )
    if not match:
        raise ValueError("无效的IP地址范围格式，应为 '起始IP-结束IP'")
    start_ip = ipaddress.IPv4Address(match.group(1))
    end_ip = ipaddress.IPv4Address(match.group(2))
    if start_ip > end_ip:
        raise ValueError(f"地址池起始IP大于结束IP：{ip_pool}")
    return start_ip, end_ip


def _parse_vlan_values(vlan_raw: str, required_count: int) -> list[str]:
    text = _clean_cell(vlan_raw)
    if re.fullmatch(r"\d+", text):
        return [text] * required_count
    match = re.fullmatch(r"(\d+)\s*[-~]\s*(\d+)", text)
    if not match:
        raise ValueError(f"VLAN 不满足分配条件：{vlan_raw}")
    start, end = int(match.group(1)), int(match.group(2))
    if start > end:
        raise ValueError(f"VLAN 范围非法：{vlan_raw}")
    values = [str(vlan) for vlan in range(start, end + 1)]
    if len(values) < required_count:
        raise ValueError(f"VLAN 数量不足，需要 {required_count} 个，实际 {len(values)} 个")
    return values[:required_count]


def _next_network(network: ipaddress.IPv4Network) -> ipaddress.IPv4Network:
    next_network_address = int(network.network_address) + network.num_addresses
    if next_network_address > int(ipaddress.IPv4Address("255.255.255.255")):
        raise ValueError("网段分配超过 IPv4 地址空间")
    return ipaddress.IPv4Network((next_network_address, network.prefixlen))


def _gateway_for_network(
    network: ipaddress.IPv4Network,
    gateway_raw: str,
    first_network: ipaddress.IPv4Network,
) -> ipaddress.IPv4Address:
    text = _clean_cell(gateway_raw)
    if not text or re.search(r"起始|开始|首|start|spine", text, re.IGNORECASE):
        return next(network.hosts())
    if re.search(r"结束|终止|末|end|leaf", text, re.IGNORECASE):
        return ipaddress.IPv4Address(int(network.broadcast_address) - 1)

    try:
        configured_gateway = ipaddress.IPv4Address(text)
    except ValueError:
        raise ValueError(f"网关地址/位置非法：{gateway_raw}") from None

    if configured_gateway in first_network and configured_gateway not in {
        first_network.network_address,
        first_network.broadcast_address,
    }:
        offset = int(configured_gateway) - int(first_network.network_address)
        candidate = ipaddress.IPv4Address(int(network.network_address) + offset)
        if candidate in network and candidate not in {network.network_address, network.broadcast_address}:
            return candidate
    if configured_gateway in network and configured_gateway not in {
        network.network_address,
        network.broadcast_address,
    }:
        return configured_gateway
    raise ValueError(f"网关 {configured_gateway} 不属于网段 {network}")


def get_usable_ips(
    subnet: ipaddress.IPv4Network,
    gateway: ipaddress.IPv4Address,
    start_ip: ipaddress.IPv4Address,
    end_ip: ipaddress.IPv4Address,
) -> list[str]:
    return [
        str(current_ip)
        for current_ip in subnet.hosts()
        if current_ip != gateway and start_ip <= current_ip <= end_ip
    ]


def generate_switch_network_segments(
    switch_counts: list[tuple[str, int]],
    resource: ResourceInfo,
) -> list[SwitchGateway]:
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)
    first_network = ipaddress.IPv4Network(f"{start_ip}/{resource.mask}", strict=False)
    network = first_network
    groups: list[tuple[list[str], ipaddress.IPv4Network, ipaddress.IPv4Address]] = []

    index = 0
    while index < len(switch_counts):
        gateway = _gateway_for_network(network, resource.gateway_raw, first_network)
        capacity = len(get_usable_ips(network, gateway, start_ip, end_ip))
        if capacity <= 0:
            raise ValueError(f"网段 {network} 在地址池 {resource.ip_pool} 内无可用IP")

        group_switches: list[str] = []
        group_count = 0
        while index < len(switch_counts):
            switch_name, node_count = switch_counts[index]
            if node_count > capacity:
                raise ValueError(f"交换机 {switch_name} 节点数量 {node_count} 超过单网段可用IP数 {capacity}")
            if group_switches and group_count + node_count > capacity:
                break
            group_switches.append(switch_name)
            group_count += node_count
            index += 1

        groups.append((group_switches, network, gateway))
        if index < len(switch_counts):
            network = _next_network(network)
            if network.network_address > end_ip:
                raise ValueError(f"地址池 {resource.ip_pool} 不足以继续分配下一个网段")

    vlan_values = _parse_vlan_values(resource.vlan_raw, len(groups))
    result: list[SwitchGateway] = []
    for group_index, (switches, group_network, group_gateway) in enumerate(groups):
        vlan = vlan_values[group_index]
        for switch in switches:
            result.append(
                SwitchGateway(
                    name=switch,
                    network_segment=str(group_network),
                    gateway=str(group_gateway),
                    vlan=vlan,
                    mask=str(resource.mask),
                )
            )
    return result


def get_leaf_spine_mapping(
    topology_file: str | Path,
    sheet_name: str,
    switch_gateways: list[SwitchGateway],
) -> dict[str, list[str]]:
    df = _data_after_device_header(topology_file, sheet_name)
    target_leafs = {switch.name for switch in switch_gateways}
    leaf_to_spines: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        leaf = _clean_cell(row.iloc[0])
        spine = _clean_cell(row.iloc[-1])
        if "LEAF" not in leaf.upper() or leaf not in target_leafs or not spine:
            continue
        leaf_to_spines.setdefault(leaf, [])
        if spine not in leaf_to_spines[leaf]:
            leaf_to_spines[leaf].append(spine)
    return leaf_to_spines


def transfer_gateways_to_spines(
    leaf_spine_mapping: dict[str, list[str]],
    leaf_gateway_list: list[SwitchGateway],
) -> list[SwitchGateway]:
    if not leaf_spine_mapping:
        return [
            SwitchGateway(name="", network_segment=sw.network_segment, gateway=sw.gateway, vlan=sw.vlan, mask=sw.mask)
            for sw in leaf_gateway_list
        ]

    spine_config_map: dict[str, dict[str, tuple[str, str, str]]] = defaultdict(dict)
    for gateway in leaf_gateway_list:
        if not gateway.vlan or not gateway.gateway:
            continue

        for spine_name in leaf_spine_mapping.get(gateway.name, []):
            existing = spine_config_map[spine_name].get(gateway.vlan)
            current = (gateway.network_segment, gateway.gateway, gateway.mask)
            if existing is None:
                spine_config_map[spine_name][gateway.vlan] = current

    result: list[SwitchGateway] = []
    for spine_name, vlan_entries in spine_config_map.items():
        for vlan, (network_segment, gateway, mask) in vlan_entries.items():
            result.append(
                SwitchGateway(
                    name=spine_name,
                    network_segment=network_segment,
                    gateway=gateway,
                    vlan=vlan,
                    mask=mask,
                )
            )
    return result


def _switch_gateways_to_dataframe(switch_gateways: list[SwitchGateway]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": item.name,
                "network_segment": item.network_segment,
                "gateway": item.gateway,
                "vlan": item.vlan,
                "mask": item.mask,
            }
            for item in switch_gateways
        ],
        columns=["name", "network_segment", "gateway", "vlan", "mask"],
    )


def build_address_dataframe(
    topology_file: str | Path,
    sheet_name: str,
    switch_network_segments: list[SwitchGateway],
    resource: ResourceInfo,
    *,
    leaf_scope: Literal["global", "segment"] = "global",
) -> pd.DataFrame:
    switch_to_net_devices = get_net_device_data(topology_file, sheet_name)
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)
    all_leaf_switches = get_leaf_switches(topology_file, sheet_name)

    network_segment_to_switches: dict[str, list[str]] = defaultdict(list)
    switch_name_to_gateway = {item.name: item for item in switch_network_segments}
    for item in switch_network_segments:
        network_segment_to_switches[item.network_segment].append(item.name)

    rows: list[dict[str, object]] = []
    for network_segment, switches in network_segment_to_switches.items():
        all_net_devices: list[str] = []
        for switch in switches:
            all_net_devices.extend(switch_to_net_devices.get(switch, []))

        if not all_net_devices:
            continue

        leaf_devices = all_leaf_switches if leaf_scope == "global" else switches
        all_net_devices.extend(leaf_devices)

        gateway_info = switch_name_to_gateway.get(switches[0])
        if gateway_info is None:
            raise ValueError(f"未找到交换机 {switches[0]} 的网关信息")

        gateway_ip = ipaddress.IPv4Address(gateway_info.gateway)
        vlan = int(float(gateway_info.vlan))
        network = ipaddress.IPv4Network(network_segment, strict=False)
        usable_ips = get_usable_ips(network, gateway_ip, start_ip, end_ip)
        if len(usable_ips) < len(all_net_devices):
            raise ValueError(f"网段 {network_segment} 中可用 IP 不足，请检查！")

        leaf_device_set = set(all_leaf_switches)
        for net_device, ip in zip(all_net_devices, usable_ips):
            rows.append(
                {
                    "设备名称": net_device,
                    "带外管理地址": ip,
                    "带外管理掩码": str(gateway_info.mask),
                    "带外管理网关": str(gateway_ip),
                    "带外管理VLAN": vlan,
                    "接口名称": f"vlanif{vlan}" if net_device in leaf_device_set else "MGMT",
                }
            )

    return pd.DataFrame(
        rows,
        columns=["设备名称", "带外管理地址", "带外管理掩码", "带外管理网关", "带外管理VLAN", "接口名称"],
    )


def run_from_files(
    topology_file: str | Path,
    resource_file: str | Path,
    *,
    sheet_name: str = DEFAULT_SHEET_NAME,
    resource_plane: str = DEFAULT_RESOURCE_PLANE,
    output_file: str | Path = DEFAULT_OUTPUT_FILE,
    intermediate_file: str | Path | None = DEFAULT_INTERMEDIATE_FILE,
    leaf_scope: Literal["global", "segment"] = "global",
) -> PlanningResult:
    resource = read_resource_info(resource_file, resource_plane)
    switch_counts = get_switch_counts(topology_file, sheet_name)
    switch_network_segments = generate_switch_network_segments(switch_counts, resource)
    address_df = build_address_dataframe(
        topology_file,
        sheet_name,
        switch_network_segments,
        resource,
        leaf_scope=leaf_scope,
    )

    leaf_to_spines = get_leaf_spine_mapping(topology_file, sheet_name, switch_network_segments)
    spine_gateways = transfer_gateways_to_spines(leaf_to_spines, switch_network_segments)
    gateway_df = _switch_gateways_to_dataframe(spine_gateways)

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    address_df.to_excel(output_path, sheet_name=OUTPUT_SHEET_NAME, index=False)

    intermediate_path: Path | None = None
    if intermediate_file:
        intermediate_path = Path(intermediate_file)
        intermediate_path.parent.mkdir(parents=True, exist_ok=True)
        if intermediate_path.exists():
            existing_df = pd.read_excel(intermediate_path)
            gateway_df = pd.concat([existing_df, gateway_df], ignore_index=True)
        gateway_df.to_excel(intermediate_path, index=False)

    return PlanningResult(
        address_df=address_df,
        gateway_df=gateway_df,
        output_file=output_path,
        intermediate_file=intermediate_path,
    )
