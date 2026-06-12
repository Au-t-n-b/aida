"""A3 存储带外管理地址规划确定性规则。

业务来源：
  - L2：src/manage_agent/sub_agents/LLD_IP/a3_storage_dw_manage_ip_address.py
  - L3：src/manage_agent/sub_agents/LLD_IP/a3_l3_storage_dw_manage_ip_address.py
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

NET_PLANE_RESOURCE = "存储带外管理面"
SHEET_DEFAULT = "存储带外管理面端口互联"


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


def determine_gateway(network: ipaddress.IPv4Network, gateway_config: str) -> ipaddress.IPv4Address:
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
    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", vlan_config)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
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
        raise ValueError(f"未找到网络平面等于 {plane_name!r} 的记录")

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
    """对齐 utils.process_excel_or_db_data：用设备命名行与上一行分组表头合并列名。"""
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


def get_storage_data(excel_path: str, sheet_name: object) -> Dict[str, List[str]]:
    """对齐 get_storage_data：首列存储设备，末列接入交换机，去重后分组。"""
    df_all = read_sheet_raw(excel_path, sheet_name)
    header_idx = find_header_row(df_all)
    df = df_all.iloc[header_idx + 1 :].reset_index(drop=True)
    df = df.rename(columns={df.columns[0]: "存储设备", df.columns[-1]: "接入交换机"})
    result_df = df[["存储设备", "接入交换机"]].drop_duplicates()
    return result_df.groupby("接入交换机", sort=False)["存储设备"].apply(list).to_dict()


def count_storage_ips_by_leaf(excel_path: str, sheet_name: object) -> pd.DataFrame:
    """对齐 get_switch_info：过滤 leaf/spine 后，按存储设备端口数计算每台接入交换机 IP 数量。"""
    df_all = read_sheet_raw(excel_path, sheet_name)
    header_idx = find_header_row(df_all)
    df = df_all.iloc[header_idx + 1 :].reset_index(drop=True)
    df = df.rename(columns={df.columns[0]: "存储设备", df.columns[1]: "接口信息", df.columns[-1]: "接入交换机"})
    df = df[~df["存储设备"].astype(str).str.contains("leaf|spine", case=False, na=False)]
    result_df = df[["存储设备", "接入交换机"]].drop_duplicates()

    structured = read_structured_007(excel_path, sheet_name)
    port_count_dict = structured["起始端信息-设备命名"].value_counts(sort=False).to_dict()

    def count_ips(storage_name: str) -> int:
        if "9950" in str(storage_name):
            return 8
        return int(port_count_dict.get(storage_name, 0))

    rows = []
    for switch, devices in result_df.groupby("接入交换机", sort=False)["存储设备"]:
        rows.append({"leaf交换机": switch, "IP数量": sum(count_ips(dev) for dev in devices)})
    return pd.DataFrame(rows, columns=["leaf交换机", "IP数量"])


def storage_port_maps(structured_df: pd.DataFrame) -> Tuple[Dict[str, int], Dict[str, object]]:
    port_df = structured_df[["起始端信息-设备命名", "起始端信息-接口信息"]].drop_duplicates()
    port_count = structured_df["起始端信息-设备命名"].value_counts(sort=False)
    port_count_dict = {str(k): int(v) for k, v in port_count.to_dict().items()}
    port_dict = port_df.set_index("起始端信息-设备命名")["起始端信息-接口信息"].to_dict()
    return port_count_dict, port_dict


def generate_l2_leaf_segments(leaf_counts: pd.DataFrame, resource: NetworkResource) -> List[SwitchGateway]:
    leaves = leaf_counts["leaf交换机"].astype(str).tolist()
    ip_counts = leaf_counts["IP数量"].astype(int).tolist()
    mask = str(int(str(resource.mask)))
    subnets = split_ip_range_subnets(resource.ip_pool, int(mask), len(leaves))
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)

    def usable_count_for_subnet(subnet_str: str) -> int:
        network = ipaddress.IPv4Network(subnet_str, strict=False)
        gateway = determine_gateway(network, resource.gateway)
        return len(usable_ips_in_network(network, gateway, start_ip, end_ip))

    groups: List[List[Tuple[str, int]]] = []
    current: List[Tuple[str, int]] = []
    current_ips = 0
    subnet_idx = 0
    for leaf, ip_count in zip(leaves, ip_counts):
        if not current:
            current = [(leaf, ip_count)]
            current_ips = ip_count
            continue
        if subnet_idx >= len(subnets):
            groups.append(current)
            current = [(leaf, ip_count)]
            current_ips = ip_count
            continue
        if current_ips + ip_count <= usable_count_for_subnet(subnets[subnet_idx]):
            current.append((leaf, ip_count))
            current_ips += ip_count
        else:
            groups.append(current)
            subnet_idx += 1
            current = [(leaf, ip_count)]
            current_ips = ip_count
    if current:
        groups.append(current)

    out: List[SwitchGateway] = []
    vlan_idx = 0
    for group_idx, group in enumerate(groups):
        if group_idx >= len(subnets):
            for leaf, _ in group:
                out.append(SwitchGateway(leaf, "网段个数不足", "", "", mask))
            continue
        network = ipaddress.IPv4Network(subnets[group_idx], strict=False)
        gateway = determine_gateway(network, resource.gateway)
        vlan = vlan_for_segment(resource.vlan, vlan_idx)
        for leaf, _ in group:
            out.append(SwitchGateway(leaf, str(network), str(gateway), vlan, mask))
        vlan_idx += 1
    return out


def generate_l3_leaf_segments(leaf_counts: pd.DataFrame, resource: NetworkResource) -> List[SwitchGateway]:
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
        out.append(SwitchGateway(leaf, str(network), str(gateway), vlan_for_segment(resource.vlan, idx), mask))
    return out


def allocate_storage_dw_addresses(
    switch_gateways: Sequence[SwitchGateway],
    switch_to_storages: Dict[str, List[str]],
    port_count_dict: Dict[str, int],
    port_dict: Dict[str, object],
    ip_pool: str,
) -> pd.DataFrame:
    start_ip, end_ip = parse_ip_pool(ip_pool)
    network_segment_to_switches: Dict[str, List[str]] = defaultdict(list)
    for sg in switch_gateways:
        if sg.network_segment == "网段个数不足":
            raise ValueError("网段个数不足")
        network_segment_to_switches[sg.network_segment].append(sg.name)

    switch_name_to_gateway = {sg.name: sg for sg in switch_gateways}
    rows: List[dict] = []
    for net_seg, switches in network_segment_to_switches.items():
        all_storages: List[str] = []
        for switch in switches:
            all_storages.extend(switch_to_storages.get(switch, []))
        if not all_storages:
            continue

        gateway_info = switch_name_to_gateway.get(switches[0])
        if not gateway_info:
            raise ValueError(f"未找到交换机 {switches[0]} 的网关信息")
        gateway_ip = ipaddress.IPv4Address(gateway_info.gateway)
        network = ipaddress.IPv4Network(net_seg, strict=False)
        usable_ips = usable_ips_in_network(network, gateway_ip, start_ip, end_ip)

        expanded_all_storages: List[str] = []
        for storage in all_storages:
            if "9950" in str(storage):
                expanded_all_storages.extend([storage] * 8)
            else:
                expanded_all_storages.extend([storage] * int(port_count_dict.get(str(storage), 0)))

        if len(usable_ips) < len(expanded_all_storages):
            raise ValueError(f"网段 {net_seg} 中可用 IP 不足，请检查！")

        ip_iter = iter(usable_ips)
        for storage in expanded_all_storages:
            try:
                ip = next(ip_iter)
            except StopIteration as exc:
                raise ValueError(f"IP 地址不足，无法为设备 {storage} 分配足够的 IP！") from exc
            rows.append(
                {
                    "设备名称": storage,
                    "带外管理地址": str(ip),
                    "带外管理掩码": f"{gateway_info.mask}",
                    "带外管理网关": f"{gateway_ip}",
                    "带外管理VLAN": gateway_info.vlan,
                    "接口名称": port_dict.get(storage, None),
                }
            )
    return pd.DataFrame(rows)
