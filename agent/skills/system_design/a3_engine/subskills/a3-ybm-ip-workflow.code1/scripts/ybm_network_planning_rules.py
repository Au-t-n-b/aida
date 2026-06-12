"""YBM 网络规划通用规则与算法（i2/i3 复用）。

包含：
- 地址池解析、按前缀切分子网
- 网关计算（网段起始位/结束位/显式IPv4）
- VLAN 计算（固定或范围递增）
- i3 一机一网段规划
- spine/leaf 混合模式下的“共享网段”规划
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

SEGMENT_COUNT_INSUFFICIENT = "网段个数不足"
SEGMENT_USABLE_IP_INSUFFICIENT = "可用IP不足"
VLAN_INSUFFICIENT = "vlan不足"

GATEWAY_MODE_START_ALIASES = {"网段起始位", "start", "START", "first", "FIRST"}
GATEWAY_MODE_END_ALIASES = {"网段结束位", "end", "END", "last", "LAST"}


@dataclass(frozen=True)
class SwitchGateway:
    name: str
    network_segment: str  # e.g. "11.15.96.0/26" or marker string
    gateway: str  # empty when non-assignable
    vlan: object  # int/str/marker; keep flexible
    mask: int  # prefix bits


def is_non_assignable_plan_segment(network_segment: str) -> bool:
    return str(network_segment).strip() in {
        SEGMENT_COUNT_INSUFFICIENT,
        SEGMENT_USABLE_IP_INSUFFICIENT,
        VLAN_INSUFFICIENT,
    }


_IP_POOL_RE = re.compile(
    r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s*-\s*(\d{1,3}(?:\.\d{1,3}){3})\s*$"
)


def parse_ip_pool_bounds(ip_pool: str) -> Tuple[ipaddress.IPv4Address, ipaddress.IPv4Address]:
    m = _IP_POOL_RE.match(str(ip_pool or ""))
    if not m:
        raise ValueError(f"地址池* 格式不合法: {ip_pool!r}，期望形如 'A.B.C.D - W.X.Y.Z'")
    start_ip = ipaddress.IPv4Address(m.group(1))
    end_ip = ipaddress.IPv4Address(m.group(2))
    if int(end_ip) < int(start_ip):
        raise ValueError(f"地址池* 起止反了: {ip_pool!r}")
    return start_ip, end_ip


def split_ip_range(ip_range_str: str, *, target_prefix: int, max_switch_count: int) -> List[str]:
    """地址池裁剪为连续子网（固定前缀），最多 max_switch_count 个（交换机台数）。"""
    import sys
    from pathlib import Path

    shared = Path(__file__).resolve().parents[2] / "_runtime_shared"
    if str(shared) not in sys.path:
        sys.path.insert(0, str(shared))
    from segment_split import split_ip_range_subnets_str  # noqa: E402

    return split_ip_range_subnets_str(ip_range_str, int(target_prefix), int(max_switch_count))


def determine_gateway(network_segment: str, gateway_mode: str) -> str:
    """网关四段式计算：起始位=network+1；结束位=broadcast-1；或显式IPv4。"""
    network = ipaddress.IPv4Network(network_segment, strict=False)
    g = str(gateway_mode or "").strip()
    if g in GATEWAY_MODE_START_ALIASES:
        return str(ipaddress.IPv4Address(int(network.network_address) + 1))
    if g in GATEWAY_MODE_END_ALIASES:
        bcast = ipaddress.IPv4Address(int(network.network_address) + network.num_addresses - 1)
        return str(ipaddress.IPv4Address(int(bcast) - 1))

    try:
        ip_g = ipaddress.IPv4Address(g)
    except ipaddress.AddressValueError as e:
        raise ValueError(f"网关地址* 不合法: {gateway_mode!r}（期望 网段起始位/网段结束位 或合法 IPv4）") from e
    if ip_g not in network:
        raise ValueError(f"网关 {ip_g} 不在网段 {network} 内")
    if ip_g in (network.network_address, network.broadcast_address):
        raise ValueError(f"网关不能为网络地址或广播地址：{ip_g}")
    return str(ip_g)


def enumerate_usable_ips_in_pool(
    network: ipaddress.IPv4Network,
    gateway_ip: ipaddress.IPv4Address,
    pool_start: ipaddress.IPv4Address,
    pool_end: ipaddress.IPv4Address,
) -> List[ipaddress.IPv4Address]:
    """网段内可用主机地址：落在地址池范围内，且排除网络/广播/网关。"""
    excluded = {network.network_address, network.broadcast_address, gateway_ip}
    out: List[ipaddress.IPv4Address] = []
    for ip in network:
        if ip in excluded:
            continue
        if pool_start <= ip <= pool_end:
            out.append(ipaddress.IPv4Address(ip))
    return out


def _parse_vlan(vlan_raw: str) -> Tuple[str, int, int]:
    s = str(vlan_raw or "").strip()
    if not s:
        return ("insufficient", 0, 0)
    if re.fullmatch(r"\d+", s):
        v = int(s)
        return ("fixed", v, v)
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b < a:
            return ("insufficient", 0, 0)
        return ("range", a, b)
    return ("insufficient", 0, 0)


def _vlan_for_subnet(subnet_idx: int, vlan_raw: str) -> object:
    mode, a, b = _parse_vlan(vlan_raw)
    if mode == "fixed":
        return a
    if mode != "range":
        return VLAN_INSUFFICIENT
    v = a + subnet_idx
    return v if v <= b else VLAN_INSUFFICIENT


def plan_switch_gateways_leaf_i3(
    *,
    switch_list: Sequence[str],
    subnets: Sequence[str],
    mask: int,
    gateway_mode: str,
    vlan_raw: str,
    vlan_subnet_offset: int = 0,
) -> List[SwitchGateway]:
    out: List[SwitchGateway] = []
    for idx, sw in enumerate(switch_list):
        if idx >= len(subnets):
            vlan_val = _vlan_for_subnet(vlan_subnet_offset + idx, vlan_raw)
            out.append(
                SwitchGateway(
                    name=str(sw),
                    network_segment=SEGMENT_COUNT_INSUFFICIENT,
                    gateway="",
                    vlan=vlan_val,
                    mask=int(mask),
                )
            )
            continue
        seg = str(subnets[idx])
        gw = determine_gateway(seg, gateway_mode)
        vlan_val = _vlan_for_subnet(vlan_subnet_offset + idx, vlan_raw)
        out.append(SwitchGateway(name=str(sw), network_segment=seg, gateway=gw, vlan=vlan_val, mask=int(mask)))
    return out


def plan_switch_gateways_with_sharing(
    *,
    switch_list: Sequence[str],
    switch_to_servers: Dict[str, List[str]],
    subnets: Sequence[str],
    mask: int,
    gateway_mode: str,
    vlan_raw: str,
) -> Tuple[List[SwitchGateway], int, int]:
    """
    i2-sharing：允许多个交换机共享同一网段。
    从第一个交换机开始顺次累加节点数量；超出当前网段可用IP容量则切换到下一个网段重新累加。
    """
    if subnets:
        first = ipaddress.IPv4Network(str(subnets[0]), strict=False)
        last = ipaddress.IPv4Network(str(subnets[-1]), strict=False)
        pool_start, pool_end = ipaddress.IPv4Address(first.network_address), ipaddress.IPv4Address(last.broadcast_address)
    else:
        pool_start, pool_end = ipaddress.IPv4Address("0.0.0.0"), ipaddress.IPv4Address("0.0.0.0")

    out: List[SwitchGateway] = []
    subnet_idx = 0
    current_group_count = 0
    current_capacity = 0
    subnets_list = list(subnets)

    def _start_new_group() -> None:
        nonlocal current_group_count, current_capacity
        current_group_count = 0
        if subnet_idx < len(subnets_list):
            net = ipaddress.IPv4Network(str(subnets_list[subnet_idx]), strict=False)
            gw = ipaddress.IPv4Address(determine_gateway(str(net), gateway_mode))
            current_capacity = len(enumerate_usable_ips_in_pool(net, gw, pool_start, pool_end))
        else:
            current_capacity = 0

    _start_new_group()

    def _emit(sw_name: str, seg: str, gw: str, vlan_idx: int) -> None:
        vlan_val = _vlan_for_subnet(vlan_idx, vlan_raw)
        out.append(SwitchGateway(name=sw_name, network_segment=seg, gateway=gw, vlan=vlan_val, mask=int(mask)))

    for sw in switch_list:
        nodes = len(switch_to_servers.get(str(sw), []))

        if subnet_idx >= len(subnets_list):
            _emit(str(sw), SEGMENT_COUNT_INSUFFICIENT, "", subnet_idx)
            continue

        if current_group_count + nodes <= current_capacity:
            seg = str(subnets_list[subnet_idx])
            _emit(str(sw), seg, determine_gateway(seg, gateway_mode), subnet_idx)
            current_group_count += nodes
            continue

        subnet_idx += 1
        _start_new_group()
        if subnet_idx >= len(subnets_list):
            _emit(str(sw), SEGMENT_COUNT_INSUFFICIENT, "", subnet_idx)
            continue

        seg = str(subnets_list[subnet_idx])
        _emit(str(sw), seg, determine_gateway(seg, gateway_mode), subnet_idx)
        current_group_count = nodes

    # 计算消耗网段数：按实际分配到的最大子网序号 + 1
    used_max = 0
    for sg in out:
        if is_non_assignable_plan_segment(sg.network_segment):
            continue
        try:
            i = subnets_list.index(sg.network_segment)
        except ValueError:
            continue
        used_max = max(used_max, i + 1)

    subnets_consumed = min(max(used_max, subnet_idx + 1 if out else 0), len(subnets_list))
    vlan_next_for_leaf = subnets_consumed
    return out, subnets_consumed, vlan_next_for_leaf


def classify_spine_or_leaf(name: str) -> str:
    n = str(name or "").strip().lower()
    if "spine" in n or re.search(r"\bsp\d*\b", n):
        return "spine"
    return "leaf"

