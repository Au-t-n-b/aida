"""生成 batchRackDevices 批量上架 payload（每柜一次，共 18 次）。

跨视图上架：leaf 设备建在“参数面”视图（device_diagram），机柜在“机房”视图
（cabinet_diagram），batchRackDevices 原生支持二者分属不同视图。

落位规则（唯一权威来源 = reference/leaf-cabinet-allocation.md）：
  - 每列（A/B/C/D）仅用 17 柜、18 柜；奇数编号 leaf → 17 柜，偶数 → 18 柜。
  - 每柜固定 3 台 leaf。
  - 401 机房 leaf 001-024（A/B/C/D 四列）；402 机房 leaf 025-048；403 机房 leaf 049-054（仅 A 列）。

  401: A17[001,003,005] A18[002,004,006] B17[007,009,011] B18[008,010,012]
       C17[013,015,017] C18[014,016,018] D17[019,021,023] D18[020,022,024]
  402: A17[025,027,029] A18[026,028,030] B17[031,033,035] B18[032,034,036]
       C17[037,039,041] C18[038,040,042] D17[043,045,047] D18[044,046,048]
  403: A17[049,051,053] A18[050,052,054]

为什么每柜单独调用（不再多机柜均分）：
  多机柜 cabinet_range + 合并 device_range 时，API 不保证把设备按落位表
  精确均分到各机柜，且实测会触发 800385「Insufficient cabinet space」。
  每柜一次（cabinet_range=[单柜]、device_range=[该柜3台]）可确定性地精确落位。

上架参数：startU=41, interval=3, installationDirection=F, allocationDirection=1（由上向下）。
"""

from __future__ import annotations

from typing import Any, Mapping


# ---- 落位表（唯一权威来源，与 leaf-cabinet-allocation.md 完全一致）----
# 每个机柜独立一次调用：(room, cabinet, [leaf_seq_nums])，seq 1 → 001。
_CABINET_ALLOCATION: list[tuple[str, str, list[int]]] = [
    ("401", "A17", [1, 3, 5]),
    ("401", "A18", [2, 4, 6]),
    ("401", "B17", [7, 9, 11]),
    ("401", "B18", [8, 10, 12]),
    ("401", "C17", [13, 15, 17]),
    ("401", "C18", [14, 16, 18]),
    ("401", "D17", [19, 21, 23]),
    ("401", "D18", [20, 22, 24]),
    ("402", "A17", [25, 27, 29]),
    ("402", "A18", [26, 28, 30]),
    ("402", "B17", [31, 33, 35]),
    ("402", "B18", [32, 34, 36]),
    ("402", "C17", [37, 39, 41]),
    ("402", "C18", [38, 40, 42]),
    ("402", "D17", [43, 45, 47]),
    ("402", "D18", [44, 46, 48]),
    ("403", "A17", [49, 51, 53]),
    ("403", "A18", [50, 52, 54]),
]


def _leaf_device_name(seq: int, *, plane_code: str = "CSM", leaf_model: str = "CE9866", digits: int = 3) -> str:
    return f"{plane_code}-LEAF-{leaf_model}-{seq:0{digits}d}"


def build_rack_payloads(
    config: Mapping[str, Any],
    leaf_names: list[str] | None = None,
) -> dict[str, Any]:
    """生成批量上架 payload 列表（每柜一次，共 18 条）。

    Args:
        config: skill config.json 内容。
        leaf_names: 全部 leaf 名（如已生成），可选，仅用于校验序号一致性。

    Returns:
        dict，含 payloads(18条)、call_mode、counts、call_descriptions。
    """
    plane = dict(config.get("plane") or {})
    plane_code = str(plane.get("plane_code", "CSM"))
    leaf_model = str(plane.get("leaf_model", "CE9866"))
    digits = int(plane.get("leaf_name_digits", 3))

    # 跨视图：设备在 leaf_diagram（参数面），机柜在 room_diagram（机房）
    device_diagram = str(config.get("leaf_diagram") or config.get("diagram") or "参数面")
    cabinet_diagram = str(config.get("room_diagram") or config.get("diagram") or "机房")

    rack_cfg = dict(config.get("rack") or {})
    start_u = int(rack_cfg.get("start_u", 41))
    interval = int(rack_cfg.get("interval", 3))
    inst_dir = str(rack_cfg.get("installation_direction", "F"))
    alloc_dir = int(rack_cfg.get("allocation_direction", 1))

    def make_name(seq: int) -> str:
        return _leaf_device_name(seq, plane_code=plane_code, leaf_model=leaf_model, digits=digits)

    payloads: list[dict[str, Any]] = []
    call_descriptions: list[str] = []

    for room, cabinet, seqs in _CABINET_ALLOCATION:
        device_range = [make_name(s) for s in seqs]
        payload = {
            "device_range": device_range,
            "device_diagram": device_diagram,
            "cabinet_range": [cabinet],
            "cabinet_diagram": cabinet_diagram,
            "roomName": room,
            "startU": start_u,
            "interval": interval,
            "installationDirection": inst_dir,
            "allocationDirection": alloc_dir,
            "_meta": {
                "room": room,
                "cabinet": cabinet,
                "leaf_seqs": seqs,
                "mode": "per_cabinet",
            },
        }
        payloads.append(payload)
        call_descriptions.append(f"机房{room} {cabinet}: {device_range}")

    return {
        "api": "batchRackDevices",
        "call_mode": "per_cabinet",
        "device_diagram": device_diagram,
        "cabinet_diagram": cabinet_diagram,
        "counts": {
            "total_calls": len(payloads),
            "total_leaves": sum(len(s) for _, _, s in _CABINET_ALLOCATION),
        },
        "call_descriptions": call_descriptions,
        "payloads": payloads,
    }
