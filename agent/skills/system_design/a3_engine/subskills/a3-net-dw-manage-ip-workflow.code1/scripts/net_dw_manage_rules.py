"""A3 网络带外管理地址规划确定性规则。

业务来源（严格对齐）：
  - L2：src/manage_agent/sub_agents/LLD_IP/a3_net_dw_manage_ip_address.py
  - L3：src/manage_agent/sub_agents/LLD_IP/a3_l3_net_dw_manage_ip_address.py

网段划分替代原 LLM + split_ip_range 工具：
  - L2：a3_i2_network_segment_tools_prompt.py / a3_i2_dw_manage_network_segment_prompt.py
  - L3：a3_i3_network_segment_tools_prompt.py
"""

from __future__ import annotations

import ipaddress
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

_SHARED_DIR = Path(__file__).resolve().parents[2] / "_runtime_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
from segment_split import split_ip_range_subnets_str  # noqa: E402

NET_PLANE_RESOURCE = "网络带外管理面"
SHEET_DEFAULT = "网络带外管理面端口互联"
SP_DEVICE_PATTERN = re.compile(r"-sp\d+-", re.IGNORECASE)


def normalize_mask_prefix(mask: object) -> str:
    raw = str(mask).strip()
    if not raw:
        raise ValueError("最小规划掩码为空")
    if "." in raw:
        raw = raw.split(".")[0]
    prefix = int(raw)
    if prefix < 0 or prefix > 32:
        raise ValueError(f"CIDR 掩码位数必须在 0-32 之间: {prefix}")
    return str(prefix)


@dataclass(frozen=True)
class NetworkResource:
    network_plane: str
    ip_pool: str
    mask: str
    gateway_location: str
    gateway: str
    vlan: str


@dataclass(frozen=True)
class SwitchGateway:
    name: str
    network_segment: str
    gateway: str
    vlan: str
    mask: str


def parse_ip_pool(ip_pool: str) -> Tuple[ipaddress.IPv4Address, ipaddress.IPv4Address]:
    pattern = r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
    match = re.match(pattern, str(ip_pool).strip())
    if not match:
        raise ValueError(f"地址池格式错误，应为 起始IP-结束IP: {ip_pool!r}")
    start_ip = ipaddress.IPv4Address(match.group(1))
    end_ip = ipaddress.IPv4Address(match.group(2))
    if start_ip > end_ip:
        raise ValueError("起始 IP 不应大于终止 IP")
    return start_ip, end_ip


def determine_gateway(
    network: ipaddress.IPv4Network,
    gateway_config: str,
) -> ipaddress.IPv4Address:
    gateway_config = str(gateway_config).strip()
    if gateway_config == "网段起始位":
        return network.network_address + 1
    if gateway_config == "网段结束位":
        return network.broadcast_address - 1
    try:
        return ipaddress.IPv4Address(gateway_config)
    except ipaddress.AddressValueError as exc:
        raise ValueError(
            f"网关配置不合法：{gateway_config}，应为 '网段起始位'、'网段结束位' 或合法 IP 地址"
        ) from exc


def usable_ips_in_network(
    network: ipaddress.IPv4Network,
    gateway: ipaddress.IPv4Address,
    start_ip: ipaddress.IPv4Address,
    end_ip: ipaddress.IPv4Address,
) -> List[str]:
    """对齐 utils._get_usable_ips：排除网关，限制在地址池内。"""
    usable: List[str] = []
    for current_ip in network.hosts():
        if current_ip != gateway and start_ip <= current_ip <= end_ip:
            usable.append(str(current_ip))
    return usable


def split_ip_range_subnets(
    ip_range_str: str,
    target_prefix: int,
    max_switch_count: Optional[int] = None,
) -> List[str]:
    """最多返回 max_switch_count 个子网（通常为 Leaf 交换机台数）。"""
    if max_switch_count is None or str(max_switch_count).strip() == "":
        raise ValueError("split_ip_range_subnets 需要 max_switch_count（交换机数量）")
    limit = int(max_switch_count)
    if limit <= 0:
        return []
    return split_ip_range_subnets_str(ip_range_str, int(target_prefix), limit)


def vlan_for_segment(vlan_config: str, segment_index: int) -> str:
    vlan_config = str(vlan_config).strip()
    if re.fullmatch(r"\d+", vlan_config):
        return vlan_config
    m = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", vlan_config)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        vlan = start + segment_index
        return str(vlan) if vlan <= end else "vlan不足"
    return "vlan不足"


def fuzzy_column_value(df: pd.DataFrame, row: pd.Series, needle: str) -> object:
    if needle in row.index:
        return row[needle]
    matches = [c for c in df.columns if needle in str(c)]
    if not matches:
        raise KeyError(f"未找到包含 {needle!r} 的列")
    return row[matches[0]]


def read_network_resource(
    resource_path: str,
    sheet_name: object,
    plane_name: str = NET_PLANE_RESOURCE,
) -> NetworkResource:
    df = pd.read_excel(resource_path, sheet_name=sheet_name, header=0)
    if "网络平面" not in df.columns:
        raise ValueError("资源表缺少 '网络平面' 列")

    plane_series = df["网络平面"].astype(str).str.strip()
    rows = df[plane_series == plane_name]
    if rows.empty:
        fallback_rows = df[plane_series.str.contains("带外管理", na=False)]
        if len(fallback_rows) == 1:
            rows = fallback_rows
        elif fallback_rows.empty:
            raise ValueError(f"未找到网络平面等于 {plane_name!r} 的记录")
        else:
            candidates = fallback_rows["网络平面"].astype(str).tolist()
            raise ValueError(
                f"资源表存在多个带外管理面候选 {candidates}，请通过 --net-plane 指定精确网络平面"
            )

    row = rows.iloc[0]
    return NetworkResource(
        network_plane=str(row["网络平面"]),
        ip_pool=str(row["地址池*"]).strip(),
        mask=normalize_mask_prefix(fuzzy_column_value(df, row, "最小规划掩码")),
        gateway_location=str(fuzzy_column_value(df, row, "网关位置")).strip().upper(),
        gateway=str(row["网关地址*"]).strip(),
        vlan=str(row["VLAN*"]).strip(),
    )


def find_header_row(df: pd.DataFrame, needle: str = "设备命名") -> int:
    for idx, row in df.iterrows():
        if row.astype(str).str.contains(needle, case=False, na=False).any():
            return int(idx)
    raise ValueError(f"未找到包含 {needle!r} 的行，请检查表格内容")


def read_sheet_raw(excel_path: str, sheet_name: object) -> pd.DataFrame:
    return pd.read_excel(excel_path, sheet_name=sheet_name, header=None, dtype=str).fillna("")


def read_structured_007(excel_path: str, sheet_name: object) -> pd.DataFrame:
    """对齐 utils.process_excel_or_db_data 的列合并逻辑。"""
    df = read_sheet_raw(excel_path, sheet_name)
    if df.iloc[0].astype(str).str.contains("起始端信息-设备命名", case=False, na=False).any():
        return df.iloc[1:].reset_index(drop=True)

    header_idx = find_header_row(df)
    group_idx = max(header_idx - 1, 0)
    row0 = df.iloc[group_idx].values
    row1 = df.iloc[header_idx].values
    new_columns: List[str] = []
    j = 0
    for i in range(len(row0)):
        if row0[i] == "起始端信息":
            new_columns.append(f"起始端信息-{row1[i]}")
            j = i
        elif row0[i] == "目的端信息":
            new_columns.append(f"目的端信息-{row1[i]}")
            j = i
        elif row0[i] == "线缆信息":
            new_columns.append(f"线缆信息-{row1[i]}")
            j = i
        else:
            new_columns.append(f"{row0[j]}-{row1[i]}")
    data_rows = df.iloc[header_idx + 1 :].values.tolist()
    return pd.DataFrame(data_rows, columns=new_columns)


def get_net_device_data(
    excel_path: str,
    sheet_name: object,
    *,
    filter_sp_devices: bool,
) -> Dict[str, List[str]]:
    """接入交换机 -> 网络设备列表。L2 不过滤 -sp；L3 过滤。"""
    df_all = read_sheet_raw(excel_path, sheet_name)
    header_idx = find_header_row(df_all)
    df = df_all.iloc[header_idx + 1 :].reset_index(drop=True)
    df = df.rename(columns={df.columns[0]: "网络设备", df.columns[-1]: "接入交换机"})
    result_df = df[["网络设备", "接入交换机"]].copy()
    if filter_sp_devices:
        result_df = result_df[
            ~result_df["网络设备"].astype(str).str.contains(SP_DEVICE_PATTERN, na=False)
        ]
    result_df = result_df.drop_duplicates()
    return (
        result_df.groupby("接入交换机", sort=False)["网络设备"]
        .apply(list)
        .to_dict()
    )


def count_leaf_switches(
    excel_path: str,
    sheet_name: object,
    *,
    filter_sp_devices: bool,
) -> pd.DataFrame:
    """对齐 get_switch_info：统计 LEAF 接入交换机及其下挂节点数。"""
    df_all = read_sheet_raw(excel_path, sheet_name)
    header_idx = find_header_row(df_all)
    df = df_all.iloc[header_idx + 1 :].reset_index(drop=True)
    df = df.rename(columns={df.columns[0]: "网络设备", df.columns[-1]: "接入交换机"})
    if filter_sp_devices:
        df = df[~df["网络设备"].astype(str).str.contains(SP_DEVICE_PATTERN, na=False)]
    df = df[df["接入交换机"].astype(str).str.contains("LEAF", case=False, na=False)]
    counts = df["接入交换机"].value_counts(sort=False).reset_index()
    counts.columns = ["leaf交换机", "节点数量"]
    return counts


def get_wldw_leaf_list(structured_df: pd.DataFrame) -> List[str]:
    """目的端信息-设备命名 含 LEAF 的去重列表。"""
    col = "目的端信息-设备命名"
    if col not in structured_df.columns:
        return []
    series = structured_df[col].astype(str)
    leaf_df = structured_df[series.str.contains("LEAF", case=False, na=False)]
    return leaf_df[col].drop_duplicates().tolist()


def generate_l2_leaf_segments(
    leaf_counts: pd.DataFrame,
    resource: NetworkResource,
) -> List[SwitchGateway]:
    """确定性替代 L2 network_segment_generate（i2 提示词 + split_ip_range）。"""
    leaves = leaf_counts["leaf交换机"].astype(str).tolist()
    node_counts = leaf_counts["节点数量"].astype(int).tolist()
    mask = str(int(str(resource.mask)))
    subnets = split_ip_range_subnets(resource.ip_pool, int(mask), len(leaves))
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)

    groups: List[List[Tuple[str, int]]] = []
    current: List[Tuple[str, int]] = []
    current_nodes = 0
    subnet_idx = 0

    def usable_count_for_subnet(subnet_str: str) -> int:
        network = ipaddress.IPv4Network(subnet_str, strict=False)
        gateway = determine_gateway(network, resource.gateway)
        return len(usable_ips_in_network(network, gateway, start_ip, end_ip))

    for leaf, nodes in zip(leaves, node_counts):
        if not current:
            current = [(leaf, nodes)]
            current_nodes = nodes
            continue
        if subnet_idx >= len(subnets):
            groups.append(current)
            current = [(leaf, nodes)]
            current_nodes = nodes
            continue
        if current_nodes + nodes <= usable_count_for_subnet(subnets[subnet_idx]):
            current.append((leaf, nodes))
            current_nodes += nodes
        else:
            groups.append(current)
            subnet_idx += 1
            current = [(leaf, nodes)]
            current_nodes = nodes

    if current:
        groups.append(current)

    out: List[SwitchGateway] = []
    vlan_segment_index = 0
    for group_idx, group in enumerate(groups):
        if group_idx >= len(subnets):
            for leaf, _ in group:
                out.append(SwitchGateway(leaf, "网段个数不足", "", "", mask))
            continue
        subnet_str = subnets[group_idx]
        network = ipaddress.IPv4Network(subnet_str, strict=False)
        gateway = determine_gateway(network, resource.gateway)
        vlan = vlan_for_segment(resource.vlan, vlan_segment_index)
        for leaf, _ in group:
            out.append(
                SwitchGateway(
                    name=leaf,
                    network_segment=str(network),
                    gateway=str(gateway),
                    vlan=vlan,
                    mask=mask,
                )
            )
        vlan_segment_index += 1
    return out


def generate_l3_leaf_segments(
    leaf_counts: pd.DataFrame,
    resource: NetworkResource,
) -> List[SwitchGateway]:
    """确定性替代 L3 network_segment_generate（i3 提示词）。"""
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)
    mask = str(int(str(resource.mask)))
    first_network = ipaddress.IPv4Network(f"{start_ip}/{mask}", strict=False)
    block_size = first_network.num_addresses

    out: List[SwitchGateway] = []
    for idx, row in leaf_counts.reset_index(drop=True).iterrows():
        leaf = str(row["leaf交换机"]).strip()
        network_address = ipaddress.IPv4Address(int(first_network.network_address) + idx * block_size)
        network = ipaddress.IPv4Network(f"{network_address}/{mask}", strict=True)
        if network.network_address > end_ip:
            out.append(SwitchGateway(leaf, "网段个数不足", "", "", mask))
            continue
        gateway = determine_gateway(network, resource.gateway)
        out.append(
            SwitchGateway(
                name=leaf,
                network_segment=str(network),
                gateway=str(gateway),
                vlan=vlan_for_segment(resource.vlan, idx),
                mask=mask,
            )
        )
    return out


def get_leaf_spine_mapping(
    excel_path: str,
    sheet_name: object,
    leaf_gateways: Sequence[SwitchGateway],
) -> Dict[str, List[str]]:
    """对齐 ip_address_models.get_leaf_spine_info。"""
    df_all = read_sheet_raw(excel_path, sheet_name)
    header_idx = find_header_row(df_all)
    df = df_all.iloc[header_idx + 1 :].reset_index(drop=True)
    df = df.rename(columns={df.columns[0]: "leaf交换机", df.columns[-1]: "spine交换机"})

    target_leafs = {sw.name for sw in leaf_gateways}
    leaf_to_spines: Dict[str, List[str]] = {}
    for _, row in df.iterrows():
        leaf = str(row["leaf交换机"]).strip()
        spine = str(row["spine交换机"]).strip()
        if "LEAF" not in leaf.upper() or leaf not in target_leafs:
            continue
        if not spine:
            continue
        leaf_to_spines.setdefault(leaf, [])
        if spine not in leaf_to_spines[leaf]:
            leaf_to_spines[leaf].append(spine)
    return leaf_to_spines


def transfer_gateways_to_spines(
    leaf_spine_mapping: Dict[str, List[str]],
    leaf_gateway_list: Sequence[SwitchGateway],
) -> List[SwitchGateway]:
    """对齐 ip_address_models.transfer_gateways_to_spines。"""
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

    spine_config_map: Dict[str, Dict[str, Tuple[str, str, str]]] = defaultdict(dict)
    for gw in leaf_gateway_list:
        if not gw.vlan or not gw.gateway:
            continue
        for spine_name in leaf_spine_mapping.get(gw.name, []):
            if gw.vlan not in spine_config_map[spine_name]:
                spine_config_map[spine_name][gw.vlan] = (
                    gw.network_segment,
                    gw.gateway,
                    gw.mask,
                )

    result: List[SwitchGateway] = []
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


def allocate_dw_manage_addresses(
    switch_gateways: Sequence[SwitchGateway],
    switch_to_net_devices: Dict[str, List[str]],
    wldw_leaf_list: Sequence[str],
    ip_pool: str,
    *,
    l3_mode: bool,
) -> pd.DataFrame:
    """对齐 a3_net_device_dw_manage_ip_address_generate 的 IP 分配主循环。"""
    start_ip, end_ip = parse_ip_pool(ip_pool)
    wldw_set = set(wldw_leaf_list)

    network_segment_to_switches: Dict[str, List[str]] = defaultdict(list)
    for sg in switch_gateways:
        if sg.network_segment == "网段个数不足":
            raise ValueError("网段个数不足")
        network_segment_to_switches[sg.network_segment].append(sg.name)

    switch_name_to_gateway = {sg.name: sg for sg in switch_gateways}
    rows: List[dict] = []

    for net_seg, switches in network_segment_to_switches.items():
        all_net_device: List[str] = []
        for switch in switches:
            all_net_device.extend(switch_to_net_devices.get(switch, []))
        if not all_net_device:
            continue

        example_switch = switches[0]
        gateway_info = switch_name_to_gateway.get(example_switch)
        if not gateway_info:
            raise ValueError(f"未找到交换机 {example_switch} 的网关信息")

        gateway_ip = ipaddress.IPv4Address(gateway_info.gateway)
        mask = gateway_info.mask
        vlan = int(gateway_info.vlan)
        network = ipaddress.IPv4Network(net_seg, strict=False)
        usable_ips = usable_ips_in_network(network, gateway_ip, start_ip, end_ip)

        alloc_list = all_net_device + list(wldw_leaf_list)
        if len(usable_ips) < len(alloc_list):
            raise ValueError(f"网段 {net_seg} 中可用 IP 不足，请检查！")

        for net_device, ip in zip(alloc_list, usable_ips):
            if net_device in wldw_set:
                interface_name = f"vlanif{vlan}"
                net_ip = str(gateway_ip) if l3_mode else ip
            else:
                interface_name = "MGMT"
                net_ip = ip
            rows.append(
                {
                    "设备名称": net_device,
                    "带外管理地址": net_ip,
                    "带外管理掩码": f"{mask}",
                    "带外管理网关": f"{gateway_ip}",
                    "带外管理VLAN": vlan,
                    "接口名称": interface_name,
                }
            )

    return pd.DataFrame(rows)


def switch_gateways_to_dataframe(
    items: Sequence[SwitchGateway],
    first_col: str = "leaf交换机",
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                first_col: item.name,
                "网段": item.network_segment,
                "网关": item.gateway,
                "VLAN": item.vlan,
                "掩码位数": item.mask,
            }
            for item in items
        ],
        columns=[first_col, "网段", "网关", "VLAN", "掩码位数"],
    )


def gateways_to_intermediate_df(items: Sequence[SwitchGateway]) -> pd.DataFrame:
    return pd.DataFrame([item.__dict__ for item in items])
