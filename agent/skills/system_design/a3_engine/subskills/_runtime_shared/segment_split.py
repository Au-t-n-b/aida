"""网段划分共享逻辑：先确定交换机数量上限，只切分/返回至多该数量的子网。

避免对大地址池使用 summarize_address_range 或 list(network.hosts()) 导致 MemoryError。
"""

from __future__ import annotations

import re
import sys
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import List, Optional, Tuple

IP_POOL_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
)

GATEWAY_MODE_START_ALIASES = frozenset(
    {"网段起始位", "首", "起", "start", "Start", "START"}
)
GATEWAY_MODE_END_ALIASES = frozenset(
    {"网段末位", "网段结束位", "末", "end", "last", "End", "LAST"}
)

# 超过该规模的子网禁止 hosts() 式全量枚举（避免大地址池 + 宽掩码 MemoryError）
MAX_HOST_ENUM_NETWORK_SIZE = 65536


def parse_ip_pool_bounds(ip_pool: str) -> Tuple[IPv4Address, IPv4Address]:
    m = IP_POOL_PATTERN.match(str(ip_pool).strip())
    if not m:
        raise ValueError(f"invalid 地址池*: {ip_pool!r} (expected 'A.B.C.D-E.F.G.H')")
    start_ip, end_ip = IPv4Address(m.group(1)), IPv4Address(m.group(2))
    if start_ip > end_ip:
        raise ValueError(f"invalid 地址池* order: {ip_pool!r}")
    return start_ip, end_ip


def split_ip_range_capped(
    ip_range_str: str,
    target_prefix: int,
    max_switch_count: int,
) -> List[IPv4Network]:
    """按 /target_prefix 从地址池起始顺序切分子网，最多返回 max_switch_count 个（交换机台数）。"""
    limit = int(max_switch_count)
    if limit <= 0:
        return []

    prefix = int(target_prefix)
    if prefix <= 0 or prefix > 32:
        raise ValueError(f"invalid CIDR prefix: /{prefix}")

    start_ip, end_ip = parse_ip_pool_bounds(ip_range_str)
    start_int = int(start_ip)
    end_int = int(end_ip)
    block = 2 ** (32 - prefix)

    out: List[IPv4Network] = []
    cur = (start_int // block) * block
    while cur <= end_int and len(out) < limit:
        net = IPv4Network((cur, prefix))
        if int(net.network_address) >= start_int and int(net.broadcast_address) <= end_int:
            out.append(net)
        cur += block
    return out


def split_ip_range_subnets_str(
    ip_range_str: str,
    target_prefix: int,
    max_switch_count: int,
) -> List[str]:
    """与 split_ip_range_capped 相同，返回 CIDR 字符串列表。"""
    return [str(n) for n in split_ip_range_capped(ip_range_str, target_prefix, max_switch_count)]


def first_host_last_host(network: IPv4Network) -> Tuple[IPv4Address, IPv4Address]:
    return (
        IPv4Address(int(network.network_address) + 1),
        IPv4Address(int(network.broadcast_address) - 1),
    )


def pool_fits_in_network(
    network: IPv4Network,
    start_ip: IPv4Address,
    end_ip: IPv4Address,
) -> bool:
    """地址池 [start_ip, end_ip] 是否落在 network 的可用主机范围内。"""
    first_h, last_h = first_host_last_host(network)
    return first_h <= start_ip <= end_ip <= last_h


def network_safe_for_host_enum(network: IPv4Network) -> bool:
    return int(network.num_addresses) <= MAX_HOST_ENUM_NETWORK_SIZE


def compute_gateway_safe(network: IPv4Network, gateway_mode_raw: object) -> IPv4Address:
    mode = str(gateway_mode_raw).strip()
    first_h, last_h = first_host_last_host(network)
    if mode in GATEWAY_MODE_START_ALIASES:
        return first_h
    if mode in GATEWAY_MODE_END_ALIASES:
        return last_h
    ip = IPv4Address(mode)
    if ip not in network:
        raise ValueError(f"gateway {ip} not in network {network}")
    if ip == network.network_address or ip == network.broadcast_address:
        raise ValueError(f"gateway {ip} cannot be network/broadcast address of {network}")
    return ip


def enumerate_usable_ips_in_pool_bounded(
    subnet: IPv4Network,
    gateway: IPv4Address,
    pool_start: IPv4Address,
    pool_end: IPv4Address,
    max_ips: Optional[int] = None,
) -> List[IPv4Address]:
    """在子网与地址池交集中枚举可用主机 IP（排除网关），不调用 subnet.hosts() 全量展开。"""
    first_h, last_h = first_host_last_host(subnet)
    lo = max(int(pool_start), int(first_h))
    hi = min(int(pool_end), int(last_h))
    gw = int(gateway)
    out: List[IPv4Address] = []
    for ip_int in range(lo, hi + 1):
        if ip_int == gw:
            continue
        out.append(IPv4Address(ip_int))
        if max_ips is not None and len(out) >= max_ips:
            break
    return out


def ensure_runtime_shared_on_path() -> Path:
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root
