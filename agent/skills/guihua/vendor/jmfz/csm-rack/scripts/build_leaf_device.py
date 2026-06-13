"""生成 createDevice payload：批量创建 54 台参数面接入 Leaf（CE9866）。

Leaf 数量由 server 数量动态推导：
  block_size = leaf_downlink_pool // ports_per_server_per_rail
            = 64 // 4 = 16（CE9866 128口，contiguous_half 前半 64口为下联；
              A3 双轨每轨 4 口）
  leaves_used = ceil(server_count / block_size) × 2
             = ceil(432 / 16) × 2 = 27 × 2 = 54

设备命名：CSM-LEAF-CE9866-001 .. CSM-LEAF-CE9866-054（3位序号，由 config 可调）
slot_config：CE9866 盒式无可插线卡，留空。
"""

from __future__ import annotations

import math
from typing import Any, Mapping


def leaf_count_from_servers(
    server_count: int,
    *,
    server_uplink_ports: int = 8,
    rail_mode: str = "dual",
    leaf_downlink_pool: int = 64,
) -> int:
    """由 server 数量动态推导 leaf 用量。"""
    rails = 2 if rail_mode.lower() == "dual" else 1
    ports_per_rail = server_uplink_ports // rails
    block_size = leaf_downlink_pool // ports_per_rail if ports_per_rail else 1
    block_count = math.ceil(server_count / block_size) if block_size else 1
    return block_count * rails


def leaf_names(
    count: int,
    *,
    plane_code: str = "CSM",
    leaf_model: str = "CE9866",
    digits: int = 3,
) -> list[str]:
    """生成 leaf 设备名列表，如 ['CSM-LEAF-CE9866-001', ...]。"""
    return [f"{plane_code}-LEAF-{leaf_model}-{i:0{digits}d}" for i in range(1, count + 1)]


def build_create_leaf_payload(
    servers: list[str],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """生成 createDevice 批量请求 payload（1 条）。

    Args:
        servers: 有序 server 名列表（用于推导 leaf 数量）。
        config: skill config.json 内容。

    Returns:
        包含 "payload" 与 "leaf_names" 的字典。
    """
    plane = dict(config.get("plane") or {})
    # leaf 在“参数面”视图创建（leaf_diagram），不是“机房”
    diagram = str(config.get("leaf_diagram") or config.get("diagram") or "参数面")
    plane_code = str(plane.get("plane_code", "CSM"))
    leaf_model = str(plane.get("leaf_model", "CE9866"))
    leaf_role = str(plane.get("leaf_role", "参数面接入交换机"))
    digits = int(plane.get("leaf_name_digits", 3))
    rail_mode = str(plane.get("server_rail_mode", "dual")).lower()
    server_uplink_ports = int(plane.get("server_uplink_ports", 8))
    leaf_panel_groups = int(plane.get("leaf_panel_groups", 4))
    leaf_port_split_policy = str(plane.get("leaf_port_split_policy", "contiguous_half"))

    # 动态推导下联池大小（CE9866 128口，contiguous_half 前半64口）
    # 先用兜底值64，queryPort 实时值在 topo 构建时使用
    leaf_downlink_pool = _estimate_leaf_downlink_pool(
        leaf_model, policy=leaf_port_split_policy, panel_groups=leaf_panel_groups
    )

    count = leaf_count_from_servers(
        len(servers),
        server_uplink_ports=server_uplink_ports,
        rail_mode=rail_mode,
        leaf_downlink_pool=leaf_downlink_pool,
    )

    names = leaf_names(count, plane_code=plane_code, leaf_model=leaf_model, digits=digits)
    first_name = names[0] if names else f"{plane_code}-LEAF-{leaf_model}-{'1':0>{digits}}"

    payload = {
        "diagram": diagram,
        "device_model": leaf_model,
        "device_role": leaf_role,
        "first_device_name": first_name,
        "device_group": 1,
        "per_group_quantity": count,
        "topo_level": 2,
        "slot_config": [],
        "_meta": {
            "role": "leaf",
            "model": leaf_model,
            "quantity": count,
            "server_count": len(servers),
            "leaf_downlink_pool": leaf_downlink_pool,
        },
    }

    return {
        "api": "createDevice",
        "diagram": diagram,
        "leaf_count": count,
        "leaf_names": names,
        "payload": payload,
        "warnings": [],
    }


def _estimate_leaf_downlink_pool(
    leaf_model: str,
    *,
    policy: str = "contiguous_half",
    panel_groups: int = 4,
    fallback_total_ports: int = 128,
) -> int:
    """估算 leaf 下联端口池大小（用于 leaf 数量推导）。

    CE9866 128口，contiguous_half 策略下前半64口为下联。
    panel_split 策略下每面板前半为下联：panel_size=32, half=16, groups=4 → 64口。
    两种策略对 CE9866 均为 64 口。
    """
    import re
    m = re.search(r"(\d+)\s*[口端]", leaf_model)
    total = int(m.group(1)) if m else fallback_total_ports
    if policy == "panel_split" and panel_groups > 0 and total % panel_groups == 0:
        panel_size = total // panel_groups
        return (panel_size // 2) * panel_groups
    return total // 2
