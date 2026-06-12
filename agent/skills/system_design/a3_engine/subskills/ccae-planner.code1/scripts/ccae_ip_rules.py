"""CCAE 四平面 IP / 网关 / VIP 确定性分配（对齐 CCAE_new_plan.md）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import AddressValueError, IPv4Address, IPv4Network
from typing import Iterable, List, Optional, Sequence, Set, Tuple

IP_POOL_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
)

GATEWAY_MODE_START = frozenset(
    {"网段起始位", "起始", "起", "start", "Start", "START", "SPINE"}
)
GATEWAY_MODE_END = frozenset(
    {"网段末位", "网段结束位", "结束", "末", "end", "last", "End", "LAST", "LEAF"}
)


def parse_ip_pool_bounds(ip_pool: str) -> Tuple[IPv4Address, IPv4Address]:
    m = IP_POOL_PATTERN.match(str(ip_pool).strip())
    if not m:
        raise ValueError(f"invalid 地址池: {ip_pool!r} (expected 'A.B.C.D-E.F.G.H')")
    start_ip, end_ip = IPv4Address(m.group(1)), IPv4Address(m.group(2))
    if start_ip > end_ip:
        raise ValueError(f"invalid 地址池 order: {ip_pool!r}")
    return start_ip, end_ip


def mask_prefix_to_dotted(mask: str) -> str:
    s = str(mask).strip()
    if not s:
        raise ValueError("最小规划掩码为空")
    if re.fullmatch(r"\d{1,2}", s):
        prefix = int(s)
        if prefix < 0 or prefix > 32:
            raise ValueError(f"非法掩码位数: {s}")
        return str(IPv4Network(f"0.0.0.0/{prefix}").netmask)
    if re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", s):
        return s
    parts = s.split(".")
    if len(parts) == 1 and parts[0].isdigit():
        return mask_prefix_to_dotted(parts[0])
    raise ValueError(f"无法解析掩码: {mask!r}")


def mask_prefix_int(mask: str) -> int:
    dotted = mask_prefix_to_dotted(mask)
    return IPv4Network(f"0.0.0.0/{dotted}", strict=False).prefixlen


def parse_ip_set(raw: object) -> Set[IPv4Address]:
    if raw is None:
        return set()
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", ""):
        return set()
    out: Set[IPv4Address] = set()
    for part in re.split(r"[,;\s|/]+", s):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(IPv4Address(part))
        except Exception as exc:
            raise ValueError(f"invalid IP in list {raw!r}: {part!r}") from exc
    return out


def resolve_gateway(
    network: IPv4Network,
    *,
    gateway_position: str,
    gateway_address: str,
    allow_empty: bool,
    plane_hint: str,
) -> Optional[IPv4Address]:
    hosts = list(network.hosts())
    if not hosts:
        raise ValueError(f"子网 {network} 无可用主机（{plane_hint}）")
    first_h, last_h = hosts[0], hosts[-1]

    if gateway_address:
        ap = gateway_address.strip()
        if ap.upper() not in ("NA", "N/A", "-", "NONE", ""):
            try:
                gw = IPv4Address(ap)
            except AddressValueError:
                pass
            else:
                if gw in (network.network_address, network.broadcast_address):
                    raise ValueError(f"网关不能为网络/广播地址（{plane_hint}）: {gw}")
                if gw not in network:
                    raise ValueError(f"网关不在子网内（{plane_hint}）: {gw}")
                return gw

    pos = str(gateway_position or "").replace(" ", "").strip()
    if not pos:
        if allow_empty:
            return None
        raise ValueError(f"缺少网关位置（{plane_hint}）")

    if pos in GATEWAY_MODE_START or "起始" in pos or pos.upper().startswith("SPINE"):
        return first_h
    if pos in GATEWAY_MODE_END or "结束" in pos or pos.upper().startswith("LEAF"):
        return last_h
    raise ValueError(f"网关位置无法识别（{plane_hint}）: {gateway_position!r}")


def enumerate_usable_ips(
    ip_pool: str,
    mask_prefix: int,
    gateway_for_network,
    reserved: Set[IPv4Address],
) -> List[IPv4Address]:
    """gateway_for_network: Callable[[IPv4Network], Optional[IPv4Address]]"""
    start_ip, end_ip = parse_ip_pool_bounds(ip_pool)
    start_int, end_int = int(start_ip), int(end_ip)
    out: List[IPv4Address] = []
    current = start_int
    while current <= end_int:
        network = IPv4Network(f"{IPv4Address(current)}/{mask_prefix}", strict=False)
        gateway = gateway_for_network(network)
        for host in network.hosts():
            ip = IPv4Address(host)
            ip_int = int(ip)
            if ip_int < start_int or ip_int > end_int:
                continue
            if gateway is not None and ip == gateway:
                continue
            if ip in reserved:
                continue
            out.append(ip)
        current = int(network.broadcast_address) + 1
    return out


def parse_vlan_bounds(
    vlan_raw: object, *, allow_empty: bool, plane_hint: str
) -> Tuple[Optional[int], Optional[int]]:
    if vlan_raw is not None and vlan_raw != "":
        try:
            if float(vlan_raw) == int(float(vlan_raw)):
                v = int(float(vlan_raw))
                return v, v
        except (TypeError, ValueError):
            pass
    s = str(vlan_raw or "").strip()
    if not s or s.lower() in ("nan", "none"):
        if allow_empty:
            return None, None
        raise ValueError(f"{plane_hint}: VLAN 不能为空")
    if re.match(r"^\d+\.0+$", s):
        v = int(float(s))
        return v, v
    if re.match(r"^\d+$", s):
        return int(s), int(s)
    if "-" in s:
        parts = [p.strip() for p in s.split("-")]
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            start_vlan, end_vlan = int(parts[0]), int(parts[1])
            if start_vlan > end_vlan:
                raise ValueError(f"{plane_hint}: VLAN 起始值不能大于结束值")
            return start_vlan, end_vlan
    raise ValueError(f"invalid VLAN（{plane_hint}）: {vlan_raw!r}")


def parse_vlan_single(vlan_raw: object, *, plane_hint: str) -> str:
    if vlan_raw is not None and vlan_raw != "":
        try:
            if float(vlan_raw) == int(float(vlan_raw)):
                return str(int(float(vlan_raw)))
        except (TypeError, ValueError):
            pass
    s = str(vlan_raw or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return ""
    if re.match(r"^\d+$", s):
        return s
    if re.match(r"^\d+\.0+$", s):
        return str(int(float(s)))
    if re.match(r"^\d+\s*-\s*\d+$", s):
        start_vlan, _ = parse_vlan_bounds(s, allow_empty=False, plane_hint=plane_hint)
        return str(start_vlan)
    raise ValueError(f"invalid VLAN（{plane_hint}）: {vlan_raw!r}")


@dataclass(frozen=True)
class AllocatedRow:
    device_or_usage: str
    plane_display: str
    bond: str
    ip: str
    mask: str
    gateway: str
    vlan: str
    bond_mode: str
    dest_net: str
    dest_mask: str
    is_vip: bool = False


@dataclass(frozen=True)
class PlaneSpec:
    key: str
    match_keywords: Tuple[str, ...]
    exclude_keywords: Tuple[str, ...]
    display_name: str
    bond: str
    bond_mode: str
    vip_count: int
    vip_labels: Tuple[str, ...]
    is_container: bool = False
    is_north: bool = False
    require_gateway_vlan: bool = True


PLANE_SPECS: Tuple[PlaneSpec, ...] = (
    PlaneSpec(
        key="ccae_container_internal",
        match_keywords=("容器内部", "内部通信"),
        exclude_keywords=(),
        display_name="容器内部通信网络(IPv4)",
        bond="bond0",
        bond_mode="mode1",
        vip_count=2,
        vip_labels=("CaaS内部浮动IP(DIP)", "CaaS外部浮动IP(DIP)"),
        is_container=True,
        require_gateway_vlan=False,
    ),
    PlaneSpec(
        key="ccae_northbound",
        match_keywords=("北向",),
        exclude_keywords=("带外", "带内", "南向", "BGP"),
        display_name="北向网络(IPv4)",
        bond="bond1",
        bond_mode="mode1",
        vip_count=1,
        vip_labels=("北向网络浮动IP",),
        is_north=True,
    ),
    PlaneSpec(
        key="ccae_southbound_oob",
        match_keywords=("南向带外", "带外"),
        exclude_keywords=("带内",),
        display_name="南向带外网络(IPv4)",
        bond="bond2",
        bond_mode="mode1",
        vip_count=1,
        vip_labels=("南向带外网络浮动IP",),
    ),
    PlaneSpec(
        key="ccae_southbound_ib",
        match_keywords=("南向带内", "带内"),
        exclude_keywords=("带外",),
        display_name="南向带内网络(IPv4)",
        bond="bond3",
        bond_mode="mode4(lacp)",
        vip_count=1,
        vip_labels=("南向带内网络浮动IP",),
    ),
)


def container_dest_network(node_count: int) -> str:
    if node_count <= 3:
        return "Container-Internal (容器间通信 FULL-MESH)"
    return "Container-Internal (容器间通信 SPINE-LEAF)"


def match_plane_name(plane_name: str, spec: PlaneSpec) -> bool:
    name = str(plane_name)
    if not any(kw in name for kw in spec.match_keywords):
        return False
    return not any(ex in name for ex in spec.exclude_keywords)


def allocate_plane(
    *,
    spec: PlaneSpec,
    devices: Sequence[str],
    ip_pool: str,
    mask: str,
    vlan_raw: object,
    gateway_position: str,
    gateway_address: str,
    occupied_ips: Set[IPv4Address],
    reserved_ips: Set[IPv4Address],
) -> List[AllocatedRow]:
    hint = spec.display_name
    prefix = mask_prefix_int(mask)
    subnet_mask = mask_prefix_to_dotted(mask)

    reserved: Set[IPv4Address] = set(occupied_ips) | set(reserved_ips)
    # 不把 available_ips 当作占用（修正南向带外语义）

    gateways_seen: Set[IPv4Address] = set()

    def _gw_for_network(network: IPv4Network) -> Optional[IPv4Address]:
        gw = resolve_gateway(
            network,
            gateway_position=gateway_position,
            gateway_address=gateway_address,
            allow_empty=spec.is_container,
            plane_hint=hint,
        )
        if gw is not None:
            gateways_seen.add(gw)
        return gw

    usable = enumerate_usable_ips(ip_pool, prefix, _gw_for_network, reserved)
    gw = next(iter(gateways_seen), None) if gateways_seen else None
    need = len(devices) + spec.vip_count
    if len(usable) < need:
        raise ValueError(
            f"{hint}: 可用 IP 不足，需要 {need} 个（节点 {len(devices)} + VIP {spec.vip_count}），"
            f"实际 {len(usable)} 个"
        )

    start_vlan: Optional[int] = None
    end_vlan: Optional[int] = None
    current_vlan: Optional[int] = None
    if not spec.is_container:
        start_vlan, end_vlan = parse_vlan_bounds(
            vlan_raw, allow_empty=False, plane_hint=hint
        )
        if spec.require_gateway_vlan and start_vlan is None:
            raise ValueError(f"{hint}: VLAN 不能为空")
        current_vlan = start_vlan

    gw_str = "" if spec.is_container or gw is None else str(gw)
    dest_net = ""
    dest_mask = ""
    if spec.is_north:
        dest_net = "0.0.0.0"
        dest_mask = "0.0.0.0"

    rows: List[AllocatedRow] = []
    idx = 0
    for dev in devices:
        vlan_out = ""
        if not spec.is_container:
            if current_vlan is None or end_vlan is None or current_vlan > end_vlan:
                raise ValueError(f"{hint}: VLAN范围不足，当前 VLAN 为 {current_vlan}")
            vlan_out = str(current_vlan)
            current_vlan += 1
        rows.append(
            AllocatedRow(
                device_or_usage=dev,
                plane_display=spec.display_name,
                bond=spec.bond,
                ip=str(usable[idx]),
                mask=subnet_mask,
                gateway=gw_str,
                vlan=vlan_out,
                bond_mode=spec.bond_mode,
                dest_net=dest_net,
                dest_mask=dest_mask,
            )
        )
        idx += 1

    vip_vlan = "" if start_vlan is None else str(start_vlan)
    for label in spec.vip_labels:
        rows.append(
            AllocatedRow(
                device_or_usage=label,
                plane_display=spec.display_name,
                bond=spec.bond,
                ip=str(usable[idx]),
                mask=subnet_mask,
                gateway=gw_str,
                vlan=vip_vlan,
                bond_mode=spec.bond_mode,
                dest_net=dest_net,
                dest_mask=dest_mask,
                is_vip=True,
            )
        )
        idx += 1

    return rows
