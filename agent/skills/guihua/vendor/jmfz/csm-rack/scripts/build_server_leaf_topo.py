"""生成 server→leaf 服务器上行拓扑 payload（双轨，共 2 条）。

连线时机与视图：上架完成后 leaf 已进入“机房”视图，server 也在“机房”（嵌套在
组合模型内），因此连线统一在“机房”视图（room_diagram）进行。编排层 POST 到
``batchCreateLink``（递归查找所有层级 type_group=7 设备），而非 ``createTopoLink``
（仅查直接子节点），以命中嵌套在机柜/组合模型内的 server 与 leaf。payload 结构
两者一致。

规则（来自 reference/server-leaf-interconnect.md）：
  - A3 系列双轨：单台服务器 8×400GE，奇口(1/3/5/7)→奇编号 Leaf，偶口(2/4/6/8)→偶编号 Leaf。
  - Leaf 下联端口池：CE9866 128口，contiguous_half 策略取前半 64 口(1/0/1..1/0/64)。
  - 奇轨 payload：source=全部 server，target=全部奇编号 leaf，src_port=PIC8 奇口，tgt_port=下联全量。
  - 偶轨 payload：source=全部 server，target=全部偶编号 leaf，src_port=PIC8 偶口，tgt_port=下联全量。
  - 端口优先 queryPort 实时取，不可用时静态兜底并告警。

容量守卫：server_count × src_ports_per_rail == leaf_count_per_rail × downlink_pool_size
  432 × 4 = 1728 == 27 × 64 = 1728 ✓
"""

from __future__ import annotations

import math
from typing import Any, Callable, Mapping

PortQuerier = Callable[[str], "tuple[int, list[dict[str, Any]]]"]

_OOB_MARKERS = ("ETH", "PS1", "PS2", "PS3", "PS4", "MGMT")


# ---- 端口目录工具 ----

def _pick_business_row(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    for row in rows or []:
        csv = str(row.get("port_name") or "").strip()
        if not csv:
            continue
        first = csv.split(",")[0].strip().upper()
        if any(first.startswith(m) for m in _OOB_MARKERS):
            continue
        return row
    return None


def _port_catalog(rows: list[dict[str, Any]] | None) -> tuple[str, list[str], str]:
    """返回 (slot_name, [port_name...], standard)。无 query 返回空。"""
    row = _pick_business_row(rows)
    if not row:
        return "", [], ""
    ports = [p.strip() for p in str(row.get("port_name") or "").split(",") if p.strip()]
    slot = str(row.get("slot_name") or "").strip()
    std = str(row.get("default_port_standard") or row.get("actual_port_standard") or "400GE")
    return slot, ports, std


def _query_ports(querier: PortQuerier | None, model: str) -> list[dict[str, Any]] | None:
    if querier is None:
        return None
    try:
        status, rows = querier(model)
    except Exception:
        return None
    if status == 200 and isinstance(rows, list) and rows:
        return [r for r in rows if isinstance(r, dict)]
    return None


# ---- Leaf 端口分池 ----

def split_leaf_ports(
    ports: list[str],
    side: str,
    *,
    policy: str = "contiguous_half",
    panel_groups: int = 4,
) -> list[str]:
    """将 leaf 全部数据口按策略分为下联(down)或上联(up)端口池。

    contiguous_half：连续半区，前半→下联，后半→上联。
    panel_split：面板分区，每面板前半→下联，后半→上联。
    """
    n = len(ports)
    if n == 0:
        return []
    if policy == "panel_split" and panel_groups > 0 and n % panel_groups == 0:
        panel_size = n // panel_groups
        half = panel_size // 2
        out: list[str] = []
        for g in range(panel_groups):
            panel = ports[g * panel_size: (g + 1) * panel_size]
            out += panel[:half] if side == "down" else panel[half:]
        return out
    half = n // 2
    return ports[:half] if side == "down" else ports[half:]


# ---- 主入口 ----

def build_server_leaf_payloads(
    servers: list[str],
    leaf_names_all: list[str],
    config: Mapping[str, Any],
    *,
    querier: PortQuerier | None = None,
) -> dict[str, Any]:
    """生成 server→leaf 双轨拓扑 payload。

    Args:
        servers: 有序 server 设备名列表（432 个）。
        leaf_names_all: 全部 leaf 名列表（54 个，奇偶各 27）。
        config: skill config。
        querier: queryPort 函数，可选。

    Returns:
        dict，含 payloads(2条)、warnings、rule_c、counts。
    """
    plane = dict(config.get("plane") or {})
    topo_cfg = dict(config.get("topo") or {})
    # 连线在“机房”视图内进行（上架后 leaf 已进入机房）。
    diagram = str(topo_cfg.get("diagram") or config.get("room_diagram") or config.get("diagram") or "机房")
    link_type = str(plane.get("link_type", ""))
    rail_mode = str(plane.get("server_rail_mode", "dual")).lower()
    server_uplink_ports = int(plane.get("server_uplink_ports", 8))
    split_policy = str(plane.get("leaf_port_split_policy", "contiguous_half"))
    panel_groups = int(plane.get("leaf_panel_groups", 4))
    leaf_model = str(plane.get("leaf_model", "CE9866"))
    port_standard = str(plane.get("port_standard", "400GE"))

    warnings: list[str] = []
    rule_c: list[str] = []

    if not servers or not leaf_names_all:
        return {"payloads": [], "warnings": ["缺少 server 或 leaf 设备名"], "rule_c": [], "counts": {"total_calls": 0}}

    # ---- 服务器端口（queryPort 优先，兜底 PIC8/1..8） ----
    # 对 server 我们不 query（服务器已预建，端口由已知 PIC8 提供）
    srv_slot = "PIC8"
    srv_ports = [str(i) for i in range(1, server_uplink_ports + 1)]
    srv_std = port_standard

    # ---- Leaf 端口（queryPort 优先，兜底 1/0/1..128） ----
    leaf_rows = _query_ports(querier, leaf_model)
    leaf_slot, leaf_ports_all, leaf_std = _port_catalog(leaf_rows)
    if not leaf_ports_all:
        leaf_slot = ""
        leaf_ports_all = [f"1/0/{i}" for i in range(1, 129)]
        leaf_std = port_standard
        warnings.append(f"{leaf_model}: queryPort 不可用，Leaf 端口按 1/0/1..128 合成")

    # 下联端口池
    leaf_downlink = split_leaf_ports(
        leaf_ports_all, "down", policy=split_policy, panel_groups=panel_groups
    )
    leaf_downlink_count = len(leaf_downlink)

    # ---- 计算双轨分组 ----
    if rail_mode == "dual":
        ports_per_rail = server_uplink_ports // 2
        # 奇口：索引 0,2,4,6 → 端口 1,3,5,7
        odd_ports = srv_ports[0:server_uplink_ports:2]
        # 偶口：索引 1,3,5,7 → 端口 2,4,6,8
        even_ports = srv_ports[1:server_uplink_ports:2]
    else:
        ports_per_rail = server_uplink_ports
        odd_ports = srv_ports[:]
        even_ports = srv_ports[:]

    # 计算实际使用的 leaf 数
    block_size = leaf_downlink_count // ports_per_rail if ports_per_rail else 1
    if block_size <= 0:
        rule_c.append("Leaf 下联端口池不足，触发规则C")
        block_size = max(len(servers), 1)
    block_count = math.ceil(len(servers) / block_size)
    leaves_per_block = 2 if rail_mode == "dual" else 1
    leaves_used = block_count * leaves_per_block
    active_leaves = leaf_names_all[:leaves_used]

    if rail_mode == "dual":
        odd_leaves = active_leaves[0::2]
        even_leaves = active_leaves[1::2]
        rail_groups = [
            ("odd", odd_ports, odd_leaves),
            ("even", even_ports, even_leaves),
        ]
    else:
        rail_groups = [("single", srv_ports[:server_uplink_ports], active_leaves)]

    payloads: list[dict[str, Any]] = []
    for rail, rail_port_list, tgt_leaves in rail_groups:
        src_per_srv = len(rail_port_list)
        src_instances = len(servers) * src_per_srv
        leaf_instances = len(tgt_leaves) * leaf_downlink_count
        if src_instances != leaf_instances:
            rule_c.append(
                f"{rail}: 端口实例不平衡 server({len(servers)})×ports({src_per_srv})="
                f"{src_instances} ≠ leaf({len(tgt_leaves)})×downlink({leaf_downlink_count})="
                f"{leaf_instances}，触发规则C"
            )
        payloads.append({
            "diagram": diagram,
            "connection_type": "服务器上行",
            "link_type": link_type,
            "source_device_range": list(servers),
            "target_device_range": list(tgt_leaves),
            "source_port_range": [
                {"slot_name": srv_slot, "port_name": ",".join(rail_port_list), "actual_port_standard": srv_std}
            ],
            "target_port_range": [
                {"slot_name": leaf_slot, "port_name": ",".join(leaf_downlink), "actual_port_standard": leaf_std}
            ],
            "source_start_port": [
                {"slot_name": srv_slot, "port_name": rail_port_list[0] if rail_port_list else "", "actual_port_standard": srv_std}
            ],
            "target_start_port": [
                {"slot_name": leaf_slot, "port_name": leaf_downlink[0] if leaf_downlink else "", "actual_port_standard": leaf_std}
            ],
            "_meta": {
                "rail": rail,
                "server_count": len(servers),
                "src_ports_per_server": src_per_srv,
                "leaf_count": len(tgt_leaves),
                "leaf_downlink_pool": leaf_downlink_count,
                "src_port_instances": src_instances,
                "leaf_port_instances": leaf_instances,
            },
        })

    return {
        "api": "createTopoLink",
        "diagram": diagram,
        "connection_type": "服务器上行",
        "rail_mode": rail_mode,
        "block_size": block_size,
        "block_count": block_count,
        "active_leaves": list(active_leaves),
        "warnings": warnings,
        "rule_c": rule_c,
        "counts": {
            "total_calls": len(payloads),
            "server_count": len(servers),
            "leaf_count_used": len(active_leaves),
        },
        "payloads": payloads,
    }
