"""计算参数面 IP 分配：A2（8×NPU）与 A3（DEVICE ID + 多轨）。"""

from __future__ import annotations

import ipaddress
from ipaddress import IPv4Address
from typing import Dict, List, Set, Tuple

import pandas as pd

from csm_io import extract_pic_channel, extract_sp_and_index, min_device_id_for_port
from csm_segment_rules import SwitchGateway, is_non_assignable_plan_segment
from dw_manage_segment_rules import enumerate_usable_ips_in_pool, parse_ip_pool_bounds


def _ipv4_segment_host_sort_key(ip_str: str) -> Tuple[int, int, int, int]:
    s = str(ip_str).strip().split("/")[0]
    parts = s.split(".")
    if len(parts) != 4:
        return (0, 0, 0, 0)
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
    except ValueError:
        return (0, 0, 0, 0)


def get_usable_ip(usable_ips: List[IPv4Address], index: int) -> IPv4Address:
    if index >= len(usable_ips):
        raise ValueError(f"IP资源不足: 需要第 {index + 1} 个可用主机，仅 {len(usable_ips)} 个。")
    return usable_ips[index]


def allocate_a2_csm_ips(
    *,
    switch_gateways: List[SwitchGateway],
    server_leaf_df: pd.DataFrame,
    ip_pool: str,
) -> pd.DataFrame:
    """对齐 csm_ip_generate 内层循环。"""
    pool_start, pool_end = parse_ip_pool_bounds(ip_pool)
    all_results: List[dict] = []
    by_leaf = {str(sg.name).strip(): sg for sg in switch_gateways}

    for sg in switch_gateways:
        if is_non_assignable_plan_segment(sg.network_segment):
            continue
        leaf = str(sg.name).strip()
        try:
            subnet = ipaddress.ip_network(sg.network_segment, strict=True)
        except Exception as e:
            raise ValueError("可用IP不足，请检查") from e
        gateway = ipaddress.ip_address(str(sg.gateway))
        vlan = sg.vlan
        usable_ips = enumerate_usable_ips_in_pool(subnet, gateway, pool_start, pool_end)
        devices = server_leaf_df[
            server_leaf_df["leaf交换机"].astype(str).str.strip() == leaf
        ].reset_index(drop=True)
        for i, dev_row in devices.iterrows():
            all_results.append(
                {
                    "设备名称": dev_row["计算服务器"],
                    "参数面IP网关": str(gateway),
                    "参数面掩码": str(sg.mask),
                    "参数面NPU0": str(get_usable_ip(usable_ips, i * 8)),
                    "参数面NPU1": str(get_usable_ip(usable_ips, i * 8 + 1)),
                    "参数面NPU2": str(get_usable_ip(usable_ips, i * 8 + 2)),
                    "参数面NPU3": str(get_usable_ip(usable_ips, i * 8 + 3)),
                    "参数面NPU4": str(get_usable_ip(usable_ips, i * 8 + 4)),
                    "参数面NPU5": str(get_usable_ip(usable_ips, i * 8 + 5)),
                    "参数面NPU6": str(get_usable_ip(usable_ips, i * 8 + 6)),
                    "参数面NPU7": str(get_usable_ip(usable_ips, i * 8 + 7)),
                    "参数面VLAN": vlan,
                }
            )
    if not all_results and by_leaf:
        raise ValueError("A2 参数面 IP 分配结果为空，请检查网段规划或端口表。")
    return pd.DataFrame(all_results)


def _device_id_for_port_j(port: str, j: int) -> int:
    return min_device_id_for_port(port) + 8 * j


def _sg_cidr(sg: SwitchGateway) -> str:
    if "/" in sg.network_segment:
        return sg.network_segment
    return f"{sg.network_segment}/{int(sg.mask)}"


def _list_usable_hosts_in_segment(
    sg: SwitchGateway, ip_pool: str
) -> List[ipaddress.IPv4Address]:
    start_ip, end_ip = parse_ip_pool_bounds(ip_pool)
    net = ipaddress.ip_network(_sg_cidr(sg), strict=False)
    gw = ipaddress.ip_address(str(sg.gateway).split("/")[0])
    usable: List[ipaddress.IPv4Address] = []
    for h in net.hosts():
        if h != gw and start_ip <= h <= end_ip:
            usable.append(h)
    return usable


def _usable_hosts_cache_key(sg: SwitchGateway, ip_pool: str) -> Tuple[str, str, str]:
    return (_sg_cidr(sg), str(sg.gateway).split("/")[0].strip(), str(ip_pool).strip())


def _pick_usable_ip_avoid_used(
    sg: SwitchGateway,
    preferred_step: int,
    ip_pool: str,
    used_ips: Set[str],
    cache: Dict[Tuple[str, str, str], List[ipaddress.IPv4Address]],
) -> str:
    key = _usable_hosts_cache_key(sg, ip_pool)
    if key not in cache:
        cache[key] = _list_usable_hosts_in_segment(sg, ip_pool)
    usable = cache[key]
    if not usable:
        raise ValueError(f"IP资源不足: 交换机 {sg.name} 网段 {_sg_cidr(sg)} 无可用主机。")
    pref = max(int(preferred_step), 0)
    if pref >= len(usable):
        raise ValueError(
            f"IP资源不足: 交换机 {sg.name} 网段 {_sg_cidr(sg)} 需要第 {pref + 1} 个可用主机，仅 {len(usable)} 个。"
        )
    for idx in range(pref, len(usable)):
        cand = str(usable[idx])
        if cand not in used_ips:
            return cand
    for idx in range(0, pref):
        cand = str(usable[idx])
        if cand not in used_ips:
            return cand
    raise ValueError(
        f"IP资源不足: 交换机 {sg.name} 网段 {_sg_cidr(sg)} 可用地址均已被占用。"
    )


def generate_a3_ip_assignment_table(
    switch_list: List[SwitchGateway],
    switch_to_servers: Dict[str, List[Tuple[str, str]]],
    ip_pool: str,
    leaf_order: List[str],
    rail_mode: int,
) -> pd.DataFrame:
    """对齐 a3_csm_ip_address.generate_ip_assignment_table。"""
    by_leaf: Dict[str, SwitchGateway] = {str(sg.name).strip(): sg for sg in switch_list}
    used_ips: Set[str] = set()
    usable_cache: Dict[Tuple[str, str, str], List[ipaddress.IPv4Address]] = {}

    triples: List[Tuple[str, str, str]] = []
    for leaf, pairs in switch_to_servers.items():
        lf = str(leaf).strip()
        for server, port in pairs:
            triples.append((str(server).strip(), str(port).strip(), lf))

    servers_set = sorted({t[0] for t in triples}, key=lambda s: extract_sp_and_index(s))
    table_data: List[dict] = []

    for server in servers_set:
        server_leaves = {t[2] for t in triples if t[0] == server}
        segments_ordered = [
            by_leaf[lf] for lf in leaf_order if lf in server_leaves and lf in by_leaf
        ]
        if not segments_ordered:
            continue
        r_use = len(segments_ordered)

        rows: List[Tuple[str, str, str, int]] = []
        for srv, port, leaf in triples:
            if srv != server:
                continue
            for j in (0, 1):
                rows.append((srv, port, leaf, _device_id_for_port_j(port, j)))
        rows.sort(key=lambda x: (x[3], extract_pic_channel(x[1]), x[2]))

        for _srv, port, topo_leaf, device_id in rows:
            rail_idx = int(device_id) % r_use
            host_step = int(device_id) // r_use
            sg = segments_ordered[rail_idx]
            try:
                ip_str = _pick_usable_ip_avoid_used(sg, host_step, ip_pool, used_ips, usable_cache)
            except ValueError:
                raise
            used_ips.add(ip_str)
            table_data.append(
                {
                    "设备名称": server,
                    "DEVICE ID": device_id,
                    "参数面地址": ip_str,
                    "参数面掩码": sg.mask,
                    "参数面网关": str(sg.gateway).split("/")[0],
                    "参数面VLAN": sg.vlan,
                }
            )

    df = pd.DataFrame(
        table_data,
        columns=["设备名称", "DEVICE ID", "参数面地址", "参数面掩码", "参数面网关", "参数面VLAN"],
    )
    return df


def sort_a3_result_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["sort_key"] = out["设备名称"].apply(extract_sp_and_index)
    out["_device_id_int"] = pd.to_numeric(out["DEVICE ID"], errors="coerce").fillna(999)
    out["_seg_host_key"] = out["参数面地址"].apply(_ipv4_segment_host_sort_key)
    out = out.sort_values(by=["sort_key", "_device_id_int", "_seg_host_key"]).drop(
        columns=["sort_key", "_device_id_int", "_seg_host_key"]
    )
    return out.reset_index(drop=True)

