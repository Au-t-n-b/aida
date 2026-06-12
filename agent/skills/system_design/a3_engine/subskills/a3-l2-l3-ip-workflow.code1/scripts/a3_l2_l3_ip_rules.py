"""A3 L2/L3 gateway IP planning rules.

Business sources:
  - a3_l2_ip_address.py
  - a3_ywm_ip_address.py

The functions in this module are deterministic and do not call LLM, EDM, DB, or
front-end display APIs.
"""

from __future__ import annotations

import ipaddress
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

_SHARED_DIR = Path(__file__).resolve().parents[2] / "_runtime_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
from segment_split import (  # noqa: E402
    compute_gateway_safe,
    enumerate_usable_ips_in_pool_bounded,
    network_safe_for_host_enum,
    pool_fits_in_network,
)


def mask_prefix_int(mask: object) -> int:
    raw = str(mask).strip()
    if not raw:
        raise ValueError("最小规划掩码为空")
    if "." in raw:
        raw = raw.split(".")[0]
    prefix = int(raw)
    if prefix < 0 or prefix > 32:
        raise ValueError(f"CIDR 掩码位数必须在 0-32 之间: {prefix}")
    return prefix


SERVER_NAME_KEYWORD = (
    "AT900A3|AT900|AT800TA3|AT800IA3|AT800TA2|AT800IA2|"
    "CCAE|NCEFI|NCEFB|DME|K8SM|K8SW|MINDIE"
)

WEB_NETWORK_TYPE_CONFIG = {
    "存储面端口互联 | 样本面端口互联": "计算样本面",
    "计算管理面端口互联": "计算管理面",
    "计算业务面端口互联": "计算业务面",
    "计算管存面端口互联": "计算管存面",
    "参数面端口互联": "计算参数面",
    "样本面端口互联 | 数据面端口互联": "存储样本面",
    "存储业务面端口互联": "存储业务面",
    "存储管理面端口互联": "存储管理面",
}

FILE_NETWORK_TYPE_CONFIG = WEB_NETWORK_TYPE_CONFIG.copy()


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
    parts = [p.strip() for p in str(ip_pool).split("-")]
    if len(parts) != 2:
        raise ValueError(f"地址池格式错误，应为 起始IP-结束IP: {ip_pool}")
    start_ip = ipaddress.IPv4Address(parts[0])
    end_ip = ipaddress.IPv4Address(parts[1])
    if start_ip > end_ip:
        raise ValueError("起始 IP 不应大于终止 IP")
    return start_ip, end_ip


def determine_gateway(
    network: ipaddress.IPv4Network,
    gateway_config: str,
) -> ipaddress.IPv4Address:
    """Match a3_l2_ip_address.determine_gateway and L3 prompt rules."""
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
    """Return host IPs in subnet and input pool, excluding gateway."""
    ips = enumerate_usable_ips_in_pool_bounded(network, gateway, start_ip, end_ip, max_ips=None)
    return [str(ip) for ip in ips]


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
    network_type: str,
) -> NetworkResource:
    from pathlib import Path as _Path
    import sys as _sys

    _root = _Path(__file__).resolve().parents[2]
    if str(_root) not in _sys.path:
        _sys.path.insert(0, str(_root))
    from _runtime_shared.sheet007_resolver import resolve_resource_sheet

    resolved_sheet = resolve_resource_sheet(_Path(resource_path), sheet_name)
    df = pd.read_excel(resource_path, sheet_name=resolved_sheet, header=0)
    if "网络平面" not in df.columns:
        raise ValueError("资源表缺少 '网络平面' 列")
    file_plane = FILE_NETWORK_TYPE_CONFIG.get(network_type, network_type)
    rows = df[df["网络平面"].astype(str) == file_plane]
    if rows.empty:
        raise ValueError(f"未找到网络平面为 {file_plane!r} 的记录")
    row = rows.iloc[0]
    return NetworkResource(
        network_plane=str(row["网络平面"]),
        ip_pool=str(row["地址池*"]),
        mask=str(mask_prefix_int(fuzzy_column_value(df, row, "最小规划掩码"))),
        gateway_location=str(fuzzy_column_value(df, row, "网关位置")).strip(),
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


def read_server_links(excel_path: str, sheet_name: object) -> pd.DataFrame:
    """Read server-to-leaf links as 起始端设备/目的端设备."""
    df_all = read_sheet_raw(excel_path, sheet_name)
    header_idx = find_header_row(df_all, "设备命名")
    df = df_all.iloc[header_idx + 1 :].reset_index(drop=True)
    if df.shape[1] < 2:
        raise ValueError("端口连线表至少需要 2 列")
    equip_df = df.iloc[:, [0, df.shape[1] - 1]].copy()
    equip_df.columns = ["起始端设备", "目的端设备"]
    equip_df = equip_df[
        equip_df["起始端设备"].astype(str).str.contains(SERVER_NAME_KEYWORD, case=False, regex=True, na=False)
    ].copy()
    return equip_df.reset_index(drop=True)


def read_endpoint_pairs(excel_path: str, sheet_name: object) -> pd.DataFrame:
    """Read first/last columns without server filtering, for leaf-spine matching."""
    df_all = read_sheet_raw(excel_path, sheet_name)
    if df_all.shape[1] < 2:
        raise ValueError("端口连线表至少需要 2 列")
    out = df_all.iloc[:, [0, df_all.shape[1] - 1]].copy()
    out.columns = ["起始端设备", "目的端设备"]
    return out


def allocate_l2_server_ips(
    equipment_info_df: pd.DataFrame,
    resource: NetworkResource,
    web_network_type_name: str,
) -> Tuple[pd.DataFrame, ipaddress.IPv4Network]:
    """Match a3_l2_ip_address.allocate_ips_and_generate_df."""
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)
    num_nodes = len(equipment_info_df)
    total_available_ips = int(end_ip) - int(start_ip) + 1
    if num_nodes > total_available_ips:
        raise ValueError(f"节点数量 {num_nodes} 大于地址池可用 IP 数量 {total_available_ips}")

    required_hosts = num_nodes + 2
    configured_mask = mask_prefix_int(resource.mask)
    auto_mask = configured_mask
    for prefix in range(configured_mask, 0, -1):
        block_size = 2 ** (32 - prefix)
        if block_size >= required_hosts:
            network = ipaddress.IPv4Network(f"{start_ip}/{prefix}", strict=False)
            if pool_fits_in_network(network, start_ip, end_ip) and network_safe_for_host_enum(network):
                auto_mask = prefix
                break
        if prefix == 1:
            raise ValueError("无法找到合适的子网掩码，使得地址池中的IP能够容纳所有节点")

    mask = str(min(auto_mask, configured_mask))
    network = ipaddress.IPv4Network(f"{start_ip}/{mask}", strict=False)
    gateway_ip = compute_gateway_safe(network, resource.gateway)
    available_ips = [
        str(ip)
        for ip in enumerate_usable_ips_in_pool_bounded(
            network, gateway_ip, start_ip, end_ip, max_ips=num_nodes
        )
    ]
    if len(available_ips) < num_nodes:
        raise ValueError(f"地址池中可用 IP 数量 {len(available_ips)} 不足于分配给 {num_nodes} 个节点")

    rows = []
    for idx, row in enumerate(equipment_info_df.itertuples(index=False)):
        node_name = getattr(row, "起始端设备")
        rows.append(
            {
                "设备名称": node_name,
                f"{web_network_type_name}地址": available_ips[idx],
                f"{web_network_type_name}掩码": mask,
                f"{web_network_type_name}网关": str(gateway_ip),
                f"{web_network_type_name}VLAN": resource.vlan,
            }
        )
    return pd.DataFrame(rows), network


def l2_spine_gateways(
    endpoint_pairs: pd.DataFrame,
    equipment_info_df: pd.DataFrame,
    network: ipaddress.IPv4Network,
    result_df: pd.DataFrame,
    resource: NetworkResource,
    web_network_type_name: str,
) -> pd.DataFrame:
    leaf_names = equipment_info_df[["目的端设备"]].drop_duplicates()["目的端设备"].astype(str).tolist()
    filtered = endpoint_pairs[endpoint_pairs["起始端设备"].astype(str).isin(leaf_names)].drop_duplicates()
    filtered = filtered[
        filtered["目的端设备"].astype(str).str.contains("spine|HXHJ-CSW", case=False, regex=True, na=False)
    ]
    spine_names = filtered[["目的端设备"]].drop_duplicates()["目的端设备"].astype(str).tolist()

    if not result_df.empty:
        gateway = str(result_df.iloc[0].get(f"{web_network_type_name}网关", "")).strip() or resource.gateway
        mask = str(result_df.iloc[0].get(f"{web_network_type_name}掩码", "")).strip() or resource.mask
        vlan = str(result_df.iloc[0].get(f"{web_network_type_name}VLAN", "")).strip() or resource.vlan
    else:
        gateway, mask, vlan = resource.gateway, resource.mask, resource.vlan

    rows = [
        {
            "交换机": spine,
            "网段": str(network),
            "网关": gateway,
            "VLAN": vlan,
            "掩码位数": mask,
        }
        for spine in spine_names[:2]
    ]
    if not rows:
        rows.append({"交换机": "未匹配到SPINE", "网段": "", "网关": "", "VLAN": "", "掩码位数": ""})
    return pd.DataFrame(rows)


def vlan_for_index(vlan_config: str, index: int) -> str:
    vlan_config = str(vlan_config).strip()
    if re.fullmatch(r"\d+", vlan_config):
        return vlan_config
    m = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", vlan_config)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        vlan = start + index
        return str(vlan) if vlan <= end else "vlan不足"
    return "vlan不足"


def generate_l3_leaf_segments(
    leaf_counts: pd.DataFrame,
    resource: NetworkResource,
) -> List[SwitchGateway]:
    """Deterministic replacement for a3_ywm_ip_address.network_segment_generate.

    It follows the i3 prompt contract used by the original script: one leaf owns
    one subnet, subnets are assigned continuously from the address pool start,
    and each subnet uses the resource-table mask/gateway/VLAN rule.
    """
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)
    mask = str(mask_prefix_int(resource.mask))
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
                vlan=vlan_for_index(resource.vlan, idx),
                mask=mask,
            )
        )
    return out


def switch_gateways_to_dataframe(items: Sequence[SwitchGateway], first_col: str = "leaf交换机") -> pd.DataFrame:
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


def count_servers_by_leaf(equipment_info_df: pd.DataFrame) -> pd.DataFrame:
    dedup = equipment_info_df.drop_duplicates(subset=["起始端设备"], keep="first")
    counts = dedup["目的端设备"].value_counts(sort=False).reset_index()
    counts.columns = ["leaf交换机", "节点数量"]
    return counts


def infer_bond4_devices(server_links_all: pd.DataFrame) -> set:
    """Offline deterministic substitute for _get_switch_mlag_data bond judgment.

    The original code marks bond4 when the server appears in access rows whose
    ETH-TRUNK is not NA. Without DB trunk allocation, infer bond4 when one server
    connects to more than one distinct leaf in the same plane.
    """
    tmp = server_links_all.copy()
    tmp = tmp[
        tmp["起始端设备"].astype(str).str.contains(SERVER_NAME_KEYWORD, case=False, regex=True, na=False)
    ]
    by_server = tmp.groupby("起始端设备")["目的端设备"].nunique()
    return set(by_server[by_server > 1].index.astype(str))


def allocate_l3_server_ips(
    equipment_info_df: pd.DataFrame,
    leaf_gateways: Sequence[SwitchGateway],
    resource: NetworkResource,
    web_network_type_name: str,
    bond4_devices: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)
    bond4_set = set(bond4_devices or [])
    rows: List[dict] = []
    equipment_unique = equipment_info_df.drop_duplicates(subset=["起始端设备"], keep="first")

    for leaf_gateway in leaf_gateways:
        if leaf_gateway.network_segment == "网段个数不足":
            raise ValueError("网段个数不足")
        subnet = ipaddress.ip_network(leaf_gateway.network_segment, strict=True)
        gateway = ipaddress.ip_address(leaf_gateway.gateway)
        devices = equipment_unique[equipment_unique["目的端设备"].astype(str) == leaf_gateway.name].reset_index(drop=True)
        usable = usable_ips_in_network(subnet, gateway, start_ip, end_ip)
        if len(usable) < len(devices):
            raise ValueError(f"网段中可用IP数：{len(usable)}，小于待分配设备数")

        for i, dev_row in devices.iterrows():
            device_name = str(dev_row["起始端设备"])
            rows.append(
                {
                    "设备名称": device_name,
                    f"{web_network_type_name}地址": usable[i],
                    f"{web_network_type_name}掩码": leaf_gateway.mask,
                    f"{web_network_type_name}网关": str(gateway),
                    f"{web_network_type_name}VLAN": leaf_gateway.vlan,
                    "绑定模式": "bond4" if device_name in bond4_set else "bond1",
                }
            )
    return pd.DataFrame(rows)


def build_access_plan(
    endpoint_pairs: pd.DataFrame,
    result_df: pd.DataFrame,
    web_network_type_name: str,
    vlan_column: str,
    pvid_from_vlan: bool,
) -> pd.DataFrame:
    """Build the same visible columns as A3网络设备接入规划."""
    device_vlan_map = dict(zip(result_df["设备名称"].astype(str), result_df[vlan_column].astype(str)))
    access = endpoint_pairs.copy()
    access = access[
        access["起始端设备"].astype(str).str.contains(SERVER_NAME_KEYWORD, case=False, regex=True, na=False)
    ].copy()
    access["网络平面"] = web_network_type_name
    access["本端设备"] = access["目的端设备"]
    access["本端接口"] = ""
    access["对端设备"] = access["起始端设备"]
    access["对端接口"] = ""
    access["ETH-TRUNK"] = "NA"
    access["绑定模式"] = access["对端设备"].map(
        dict(zip(result_df["设备名称"].astype(str), result_df.get("绑定模式", pd.Series(["单独IP"] * len(result_df))).astype(str)))
    ).fillna("单独IP")
    access["vlan"] = access["对端设备"].map(device_vlan_map)
    access["pvid"] = access["vlan"] if pvid_from_vlan else ""
    access["端口类型"] = "Access"
    access["标签"] = "SERVER_LINK"
    return access[
        ["网络平面", "本端设备", "本端接口", "对端设备", "对端接口", "ETH-TRUNK", "绑定模式", "vlan", "pvid", "端口类型", "标签"]
    ].drop_duplicates()
