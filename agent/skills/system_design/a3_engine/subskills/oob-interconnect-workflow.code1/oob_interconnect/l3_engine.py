"""三层互联规划引擎：按 /30 步长（4 个地址）顺序分配点对点 IP。"""
from __future__ import annotations

import ipaddress
import logging
from typing import Optional

import pandas as pd

from oob_interconnect.constants import INTER_LINK_LABEL, P30_MASK, SPINE_TOKEN
from oob_interconnect.l2_engine import OUTPUT_COLUMNS_ORDER
from oob_interconnect.load_007 import get_switch_data_l3
from oob_interconnect.resource import get_gateway_location, get_interconnect_ip_pool

logger = logging.getLogger(__name__)


def validate_network_range(network_range: list[str], required_subnets: int) -> None:
    start_ip = ipaddress.IPv4Address(network_range[0].strip())
    end_ip = ipaddress.IPv4Address(network_range[1].strip())
    if start_ip >= end_ip:
        raise ValueError("网段范围无效: 起始IP必须小于结束IP")
    valid_start_ip = int(start_ip)
    if valid_start_ip % 4 != 0:
        valid_start_ip = (valid_start_ip // 4 + 1) * 4
    adjusted_total = int(end_ip) - valid_start_ip + 1
    if adjusted_total < 4:
        raise ValueError("网段范围无效: 调整后的网段范围太小，无法容纳任何 /30 子网")
    max_subnets = adjusted_total // 4
    if required_subnets > max_subnets:
        raise ValueError(
            f"网段范围无效: 仅可容纳 {max_subnets} 个 /30 子网，但需要分配 {required_subnets} 个"
        )
    logger.info("网段校验通过，可分配 %s 个 /30，需要 %s 个", max_subnets, required_subnets)


def allocate_ips(
    df: pd.DataFrame,
    custom_network: list[str],
    network_type: str,
    gateway_location: str | None = None,
) -> pd.DataFrame:
    start_ip = ipaddress.IPv4Address(custom_network[0].strip())
    end_ip = ipaddress.IPv4Address(custom_network[1].strip())
    start_ip_int = int(start_ip)
    if start_ip_int % 4 != 0:
        start_ip_int = (start_ip_int // 4 + 1) * 4
        start_ip = ipaddress.IPv4Address(start_ip_int)
        logger.info("起始IP已调整为: %s", start_ip)

    df = df.copy()
    df["本端接口"] = (df.iloc[:, 2].fillna("") + df.iloc[:, 1].fillna("")).str.strip()
    df["对端接口"] = (df.iloc[:, 5].fillna("") + df.iloc[:, 7].fillna("")).str.strip()
    result_df = pd.DataFrame(columns=OUTPUT_COLUMNS_ORDER)
    current_ip = start_ip
    for _, row in df.iterrows():
        device1 = row["leaf交换机"]
        device2 = row["spine交换机"]
        if current_ip + 3 > end_ip:
            logger.warning(
                "网络范围 %s 已分配完，无法继续为 %s 与 %s 分配", custom_network, device1, device2
            )
            continue
        ip1 = current_ip + 1
        ip2 = current_ip + 2
        leaf_ip = f"{ip1}" if gateway_location in (None, "leaf") else ""
        leaf_mask = P30_MASK if gateway_location in (None, "leaf") else ""
        spine_ip = f"{ip2}" if gateway_location in (None, "spine") else ""
        spine_mask = P30_MASK if gateway_location in (None, "spine") else ""
        result_df.loc[len(result_df)] = [
            network_type,
            device1,
            row["本端接口"],
            leaf_ip,
            leaf_mask,
            "",
            "",
            device2,
            row["对端接口"],
            spine_ip,
            spine_mask,
            "",
            "",
            "",
            "",
            INTER_LINK_LABEL,
        ]
        current_ip += 4
    out = result_df.dropna(axis=1, how="all")
    out = out.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    return out


def run_l3_core(
    topology_path: str,
    sheet_name: str,
    resource_path: str,
    plane_config: dict[str, dict[str, str]],
    keyword: Optional[str] = None,
    network_type: Optional[str] = None,
) -> pd.DataFrame:
    if sheet_name not in plane_config:
        raise ValueError(f"平面 '{sheet_name}' 不在平面配置中。")
    plane = plane_config[sheet_name]
    actual_sheet_name = plane.get("sheet_name", sheet_name)
    kw = keyword or plane["keyword"]
    peer_kw = plane.get("peer_keyword", SPINE_TOKEN)
    nt = network_type or plane["network_type"]
    switch_data, row_num = get_switch_data_l3(topology_path, actual_sheet_name, kw, peer_kw)
    ip_pool = get_interconnect_ip_pool(resource_path, nt)
    gateway_location = get_gateway_location(resource_path, nt)
    logger.info("%s 互连地址段: %s", nt, ip_pool)
    if gateway_location:
        logger.info("%s 网关位置: %s", nt, gateway_location.upper())
    validate_network_range(ip_pool, row_num)
    return allocate_ips(switch_data, ip_pool, nt, gateway_location)
