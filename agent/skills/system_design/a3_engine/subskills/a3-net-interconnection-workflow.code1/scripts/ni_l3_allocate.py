"""L3 LEAF-SPINE /30 互联 IP 分配（对齐 a3_ni_ip_address.allocate_ips / validate_network_range）。"""

from __future__ import annotations

import ipaddress
from typing import List, Sequence

import pandas as pd

OUTPUT_COLUMNS = [
    "网络平面",
    "本端设备",
    "本端接口",
    "本端接口IP地址",
    "本端接口掩码",
    "本端ETH-TRUNK",
    "本端VLAN",
    "对端设备",
    "对端接口",
    "对端接口IP地址",
    "对端接口掩码",
    "对端ETH-TRUNK",
    "对端VLAN",
    "PVID",
    "端口类型",
    "标签",
]


def validate_network_range(network_range: Sequence[str], required_subnets: int) -> int:
    start_ip = ipaddress.IPv4Address(network_range[0].strip())
    end_ip = ipaddress.IPv4Address(network_range[1].strip())
    if start_ip >= end_ip:
        raise ValueError("错误: 网段范围无效 - 起始IP必须小于结束IP")
    valid_start_ip = int(start_ip)
    if valid_start_ip % 4 != 0:
        valid_start_ip = (valid_start_ip // 4 + 1) * 4
    adjusted_total = int(end_ip) - valid_start_ip + 1
    if adjusted_total < 4:
        raise ValueError("错误: 网段范围无效 - 调整后的网段范围太小，无法容纳任何/30子网")
    max_subnets = adjusted_total // 4
    if required_subnets > max_subnets:
        raise ValueError(
            f"错误: 网段范围无效 - 网段范围只能容纳 {max_subnets} 个/30子网，"
            f"但需要分配 {required_subnets} 个"
        )
    return max_subnets


def allocate_ips_l3(
    df: pd.DataFrame, custom_network: Sequence[str], network_type: str
) -> pd.DataFrame:
    start_ip = ipaddress.IPv4Address(custom_network[0].strip())
    end_ip = ipaddress.IPv4Address(custom_network[1].strip())
    start_ip_int = int(start_ip)
    if start_ip_int % 4 != 0:
        start_ip_int = (start_ip_int // 4 + 1) * 4
        start_ip = ipaddress.IPv4Address(start_ip_int)
    current_ip = start_ip

    work = df.copy()
    work["本端接口"] = work.iloc[:, 2].fillna("").astype(str) + work.iloc[:, 1].fillna("").astype(str)
    work["本端接口"] = work["本端接口"].str.strip()
    work["对端接口"] = work.iloc[:, 5].fillna("").astype(str) + work.iloc[:, 7].fillna("").astype(str)
    work["对端接口"] = work["对端接口"].str.strip()

    result_df = pd.DataFrame(columns=OUTPUT_COLUMNS)
    skipped = 0

    for _, row in work.iterrows():
        device1 = row["leaf交换机"]
        device2 = row["spine交换机"]
        if current_ip + 3 > end_ip:
            skipped += 1
            continue
        ip1 = current_ip + 1
        ip2 = current_ip + 2
        result_df.loc[len(result_df)] = [
            network_type,
            device1,
            row["本端接口"],
            f"{ip1}",
            30,
            "",
            "",
            device2,
            row["对端接口"],
            f"{ip2}",
            30,
            "",
            "",
            "",
            "",
            "INTER_LINK",
        ]
        current_ip += 4

    if skipped:
        print(
            f"WARN: {skipped} 条链路因地址池耗尽未分配（对齐线上 warning+continue）",
            flush=True,
        )

    out = result_df.dropna(axis=1, how="all")
    for col in out.select_dtypes(include=["object"]).columns:
        out[col] = out[col].astype(str).str.strip()
    return out
