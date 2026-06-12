"""超平面 L1/L2 LoopBack 规划规则（与 a3_cpm_L1/L2 提示词、a3_cpm_lq_ip_address.py 对齐）。

约定：
  - L1：每台 7 个连续 LoopBack；每台 1 个 BGP AS，按 start-end 范围递增；灵衢L1/L2平面=1
  - L2：每台 2 个连续 LoopBack；全部共享 1 个 BGP AS；灵衢L1/L2平面=2
  - 连续 IP：用 IPv4Address 整数加法（与原 python 脚本一致；不跳过 .0/.255）
  - 模板复用：以"设备数最多的 sp"的 L1/L2 数量作为模板长度
    其它 sp 的 L1/L2 按其 sp 内序号映射到模板，IP/AS 由模板给定
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import List, Optional, Tuple

IP_POOL_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
)
IP_POOL_OR_SINGLE_PATTERN = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*(?:-\s*\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})?$")
AS_RANGE_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
AS_SINGLE_PATTERN = re.compile(r"^\s*(\d+)\s*$")
SP_PATTERN = re.compile(r"(?i)SP\s*(\d+)")
SP_DEVICE_PATTERN = re.compile(r"(?i)-SP(\d+)-")

L1_IP_PER_DEVICE = 7
L2_IP_PER_DEVICE = 2
PLANE_L1 = 1
PLANE_L2 = 2
MAX_L1_PER_SP_INCLUSIVE = 104


@dataclass(frozen=True)
class LoopbackAssignment:
    """单台交换机的 LoopBack + BGP AS 规划结果。"""
    device_name: str
    loopback_start: str
    loopback_end: str
    bgp_as: int
    plane: int  # 1 或 2


def parse_ip_pool_start(ip_pool: str) -> IPv4Address:
    """从 '地址池*' 字段解析起始 IP。支持 'A.B.C.D-E.F.G.H' 与单个 'A.B.C.D'。"""
    s = str(ip_pool).strip()
    m = IP_POOL_PATTERN.match(s)
    if m:
        return IPv4Address(m.group(1))
    m2 = IP_POOL_OR_SINGLE_PATTERN.match(s)
    if m2:
        return IPv4Address(m2.group(1))
    raise ValueError(f"invalid 地址池*: {ip_pool!r} (expected 'A.B.C.D' or 'A.B.C.D-E.F.G.H')")


def parse_ip_pool_end_optional(ip_pool: str) -> Optional[IPv4Address]:
    """若 ip_pool 为 'A.B.C.D-E.F.G.H' 形式，返回结束 IP，否则返回 None。"""
    s = str(ip_pool).strip()
    m = IP_POOL_PATTERN.match(s)
    if not m:
        return None
    return IPv4Address(m.group(2))


def parse_as_range_l1(as_raw: object) -> Tuple[int, int]:
    """L1 EBGP AS 规划：'start-end' 范围。"""
    s = str(as_raw).strip()
    m = AS_RANGE_PATTERN.match(s)
    if not m:
        raise ValueError(
            f"invalid L1 EBGP AS 规划: {as_raw!r} (expected 'start-end', e.g. '65001-65100')"
        )
    start = int(m.group(1))
    end = int(m.group(2))
    if start > end:
        raise ValueError(f"L1 EBGP AS 规划 start > end: {as_raw!r}")
    return start, end


def parse_as_single_l2(as_raw: object) -> int:
    """L2 EBGP AS 规划：单个数字。"""
    s = str(as_raw).strip()
    m = AS_SINGLE_PATTERN.match(s)
    if not m:
        raise ValueError(
            f"invalid L2 EBGP AS 规划: {as_raw!r} (expected single integer, e.g. '65500')"
        )
    return int(m.group(1))


def extract_sp_id_from_switch_name(switch_name: str) -> Optional[int]:
    """从交换机名中提取 sp 编号（匹配 -spN-，不区分大小写）。"""
    m = SP_DEVICE_PATTERN.search(str(switch_name))
    if not m:
        return None
    return int(m.group(1))


def extract_sp_id_from_sp_key(sp_key: str) -> Optional[int]:
    """从形如 'sp1' / 'SP12' 的键中提取数字 ID。"""
    m = SP_PATTERN.search(str(sp_key))
    if not m:
        return None
    return int(m.group(1))


def build_l1_template(
    *,
    max_l1_per_sp: int,
    pool_start: IPv4Address,
    as_start: int,
    as_end: int,
) -> List[LoopbackAssignment]:
    """生成 max_l1_per_sp 个 L1 模板槽位（顺次递增 IP 与 AS）。

    模板设备名置为占位串 ``__SLOT_{i}__``；调用方在每个 sp 内按序号映射到实际设备名。
    """
    if max_l1_per_sp <= 0:
        return []
    if max_l1_per_sp > MAX_L1_PER_SP_INCLUSIVE:
        raise ValueError(
            f"单超节点最大节点数 {max_l1_per_sp}，超过最大规格 {MAX_L1_PER_SP_INCLUSIVE}，请检查原始数据"
        )

    base_ip = pool_start + 1
    current_as = as_start
    out: List[LoopbackAssignment] = []
    for i in range(max_l1_per_sp):
        start_ip = base_ip + i * L1_IP_PER_DEVICE
        end_ip = base_ip + i * L1_IP_PER_DEVICE + (L1_IP_PER_DEVICE - 1)
        if current_as > as_end:
            raise ValueError(
                f"ebgp as 数量不足无法分配（已用至 {current_as}，范围上限 {as_end}），请检查重试"
            )
        out.append(
            LoopbackAssignment(
                device_name=f"__SLOT_{i}__",
                loopback_start=str(start_ip),
                loopback_end=str(end_ip),
                bgp_as=current_as,
                plane=PLANE_L1,
            )
        )
        current_as += 1
    return out


def build_l2_template(
    *,
    max_l2_per_sp: int,
    pool_start: IPv4Address,
    shared_as: int,
) -> List[LoopbackAssignment]:
    """生成 max_l2_per_sp 个 L2 模板槽位（顺次递增 IP，所有共享 1 个 AS）。"""
    if max_l2_per_sp <= 0:
        return []
    base_ip = pool_start + 1
    out: List[LoopbackAssignment] = []
    for i in range(max_l2_per_sp):
        start_ip = base_ip + i * L2_IP_PER_DEVICE
        end_ip = base_ip + i * L2_IP_PER_DEVICE + (L2_IP_PER_DEVICE - 1)
        out.append(
            LoopbackAssignment(
                device_name=f"__SLOT_{i}__",
                loopback_start=str(start_ip),
                loopback_end=str(end_ip),
                bgp_as=shared_as,
                plane=PLANE_L2,
            )
        )
    return out


def map_template_to_sp_devices(
    *,
    template: List[LoopbackAssignment],
    sp_devices: List[str],
) -> List[LoopbackAssignment]:
    """把模板按 sp 内 0~N-1 序号映射到该 sp 实际设备名。

    长度规则：取 min(len(template), len(sp_devices))。
    模板长度不足时，超出部分的设备会被忽略（调用方需保证模板按"最大 sp 设备数"构建）。
    """
    n = min(len(template), len(sp_devices))
    out: List[LoopbackAssignment] = []
    for i in range(n):
        t = template[i]
        out.append(
            LoopbackAssignment(
                device_name=sp_devices[i],
                loopback_start=t.loopback_start,
                loopback_end=t.loopback_end,
                bgp_as=t.bgp_as,
                plane=t.plane,
            )
        )
    return out
