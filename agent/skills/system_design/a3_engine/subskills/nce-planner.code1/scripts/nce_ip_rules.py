"""NCE IP, gateway, VLAN and bond allocation rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import AddressValueError, IPv4Address, IPv4Network
from typing import Callable, List, Optional, Sequence, Tuple

IP_POOL_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*"
    r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
)


def parse_ip_pool_bounds(ip_pool: str) -> Tuple[IPv4Address, IPv4Address]:
    match = IP_POOL_PATTERN.match(str(ip_pool).strip())
    if not match:
        raise ValueError(f"地址池格式错误，应为 '起始IP-结束IP': {ip_pool!r}")
    start_ip = IPv4Address(match.group(1))
    end_ip = IPv4Address(match.group(2))
    if start_ip > end_ip:
        raise ValueError(f"地址池起始 IP 不能大于结束 IP: {ip_pool!r}")
    return start_ip, end_ip


def mask_prefix_int(mask: object) -> int:
    raw = str(mask).strip()
    if not raw:
        raise ValueError("最小规划掩码为空")
    if "." in raw:
        raw = raw.split(".")[0]
    if not raw.isdigit():
        raise ValueError(f"无法解析最小规划掩码: {mask!r}")
    prefix = int(raw)
    if prefix < 0 or prefix > 32:
        raise ValueError(f"CIDR 掩码位数必须在 0-32 之间: {prefix}")
    return prefix


def cidr_to_subnet_mask(cidr: int) -> str:
    return str(IPv4Network(f"0.0.0.0/{cidr}").netmask)


def parse_vlan_bounds(vlan_pool: object, *, allow_empty: bool, plane_hint: str) -> Tuple[Optional[int], Optional[int]]:
    raw = str(vlan_pool or "").strip()
    if not raw or raw.lower() in ("nan", "none"):
        if allow_empty:
            return None, None
        raise ValueError(f"{plane_hint}: VLAN 不能为空")
    if re.fullmatch(r"\d+\.0+", raw):
        raw = str(int(float(raw)))
    if "-" in raw:
        parts = [p.strip() for p in raw.split("-")]
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise ValueError(f"{plane_hint}: VLAN 池格式错误，应为 '起始VLAN-结束VLAN' 或单值 VLAN")
        start_vlan, end_vlan = int(parts[0]), int(parts[1])
    else:
        if not raw.isdigit():
            raise ValueError(f"{plane_hint}: VLAN 池格式错误，应为整数或范围: {vlan_pool!r}")
        start_vlan = end_vlan = int(raw)
    if start_vlan > end_vlan:
        raise ValueError(f"{plane_hint}: VLAN 起始值不能大于结束值")
    return start_vlan, end_vlan


def resolve_gateway(
    network: IPv4Network,
    *,
    plane_name: str,
    gateway_position: str,
    gateway_address: str,
) -> Optional[IPv4Address]:
    if "内部通信网络" in plane_name:
        return None

    hosts = list(network.hosts())
    if not hosts:
        raise ValueError(f"子网 {network} 无可用主机作网关（{plane_name}）")
    first_host, last_host = hosts[0], hosts[-1]

    explicit = str(gateway_address or "").strip()
    if explicit and explicit.upper() not in ("NA", "N/A", "-", "NONE", "NAN"):
        try:
            gw_lit = IPv4Address(explicit)
        except AddressValueError:
            pass
        else:
            if gw_lit in (network.network_address, network.broadcast_address):
                raise ValueError(f"网关地址不能为网络地址或广播地址（{plane_name}）: {gw_lit}")
            if gw_lit in network:
                return gw_lit

    pos = str(gateway_position or "").replace(" ", "").strip()
    if not pos:
        raise ValueError(f"未配置网关位置*（网络平面: {plane_name}）")
    role = pos.upper()
    if "起始" in pos or pos == "网段起始位" or role == "SPINE" or role.startswith("SPINE"):
        return first_host
    if "结束" in pos or pos == "网段结束位" or role == "LEAF" or role.startswith("LEAF"):
        return last_host
    raise ValueError(
        f"网关位置*无法识别（网络平面: {plane_name}），当前为: {gateway_position}"
    )


def enumerate_available_ips(
    ip_pool: str,
    mask_prefix: int,
    gateway_for_network: Callable[[IPv4Network], Optional[IPv4Address]],
) -> List[Tuple[str, str]]:
    start_ip, end_ip = parse_ip_pool_bounds(ip_pool)
    start_int = int(start_ip)
    end_int = int(end_ip)
    current = start_int
    out: List[Tuple[str, str]] = []

    while current <= end_int:
        network = IPv4Network(f"{IPv4Address(current)}/{mask_prefix}", strict=False)
        gateway = gateway_for_network(network)
        for host in network.hosts():
            host_int = int(host)
            if host_int < start_int or host_int > end_int:
                continue
            if gateway is not None and host == gateway:
                continue
            out.append((str(host), "" if gateway is None else str(gateway)))
        current = int(network.broadcast_address) + 1
    return out


@dataclass(frozen=True)
class AllocatedRow:
    device_name: str
    plane_name: str
    bond: str
    ip: str
    mask: str
    gateway: str
    vlan: str
    bond_mode: str
    dest_net: str
    dest_mask: str


def allocate_node_rows(
    *,
    devices: Sequence[str],
    plane_name: str,
    ip_pool: str,
    mask: object,
    vlan_raw: object,
    gateway_position: str,
    gateway_address: str,
    bond_name: str,
    bond_mode: str,
) -> List[AllocatedRow]:
    is_inner = "内部通信网络" in plane_name
    prefix = mask_prefix_int(mask)
    subnet_mask = cidr_to_subnet_mask(prefix)
    start_vlan, end_vlan = parse_vlan_bounds(
        vlan_raw, allow_empty=is_inner, plane_hint=plane_name
    )

    available = enumerate_available_ips(
        ip_pool,
        prefix,
        lambda n: resolve_gateway(
            n,
            plane_name=plane_name,
            gateway_position=gateway_position,
            gateway_address=gateway_address,
        ),
    )
    if len(available) < len(devices) + 1:
        raise ValueError(
            f"{plane_name}: IP范围无效，可用 IP {len(available)} 个，"
            f"至少需要 {len(devices) + 1} 个"
        )

    rows: List[AllocatedRow] = []
    current_vlan = start_vlan
    is_north = "北向" in plane_name
    for index, device in enumerate(devices):
        vlan_out = ""
        if not is_inner:
            if current_vlan is None or end_vlan is None or current_vlan > end_vlan:
                raise ValueError(f"{plane_name}: VLAN范围不足，当前 VLAN 为 {current_vlan}")
            vlan_out = str(current_vlan)
            current_vlan += 1
        ip, gateway = available[index]
        rows.append(
            AllocatedRow(
                device_name=device,
                plane_name=plane_name,
                bond=bond_name,
                ip=ip,
                mask=subnet_mask,
                gateway="" if is_inner else gateway,
                vlan=vlan_out,
                bond_mode=bond_mode,
                dest_net="0.0.0.0" if is_north else "",
                dest_mask="0.0.0.0" if is_north else "",
            )
        )
    return rows


def allocate_floating_row(
    *,
    devices: Sequence[str],
    usage_name: str,
    display_plane_name: str,
    source_plane_name: str,
    ip_pool: str,
    mask: object,
    vlan_raw: object,
    gateway_position: str,
    gateway_address: str,
    bond_name: str,
    bond_mode: str,
) -> AllocatedRow:
    prefix = mask_prefix_int(mask)
    subnet_mask = cidr_to_subnet_mask(prefix)
    start_vlan, _ = parse_vlan_bounds(vlan_raw, allow_empty=False, plane_hint=source_plane_name)
    available = enumerate_available_ips(
        ip_pool,
        prefix,
        lambda n: resolve_gateway(
            n,
            plane_name=source_plane_name,
            gateway_position=gateway_position,
            gateway_address=gateway_address,
        ),
    )
    index = len(devices)
    if index >= len(available):
        raise ValueError(
            f"{source_plane_name}: IP范围无效，浮动 IP 索引为第 {index + 1} 个，"
            f"超出了最大 IP 个数 {len(available)} 个"
        )
    ip, gateway = available[index]
    is_north = "北向" in display_plane_name
    return AllocatedRow(
        device_name=usage_name,
        plane_name=display_plane_name,
        bond=bond_name,
        ip=ip,
        mask=subnet_mask,
        gateway=gateway,
        vlan=str(start_vlan),
        bond_mode=bond_mode,
        dest_net="0.0.0.0" if is_north else "",
        dest_mask="0.0.0.0" if is_north else "",
    )
