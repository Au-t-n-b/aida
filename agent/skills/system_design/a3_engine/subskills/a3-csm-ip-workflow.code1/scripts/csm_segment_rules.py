"""计算参数面网段规划（I3：一 Leaf 一网段，对齐 a3_i3 / switch_network_segment_info prompt）。"""

from __future__ import annotations

from typing import List

import pandas as pd

from dw_manage_segment_rules import (  # noqa: F401
    SEGMENT_COUNT_INSUFFICIENT,
    SwitchGateway,
    is_non_assignable_plan_segment,
    plan_switch_gateways_leaf_i3,
    split_ip_range,
)

__all__ = [
    "SEGMENT_COUNT_INSUFFICIENT",
    "SwitchGateway",
    "is_non_assignable_plan_segment",
    "plan_switch_gateways_leaf_i3",
    "split_ip_range",
    "switch_gateways_to_markdown",
    "switch_gateways_to_dataframe",
]


def switch_gateways_to_markdown(rows: List[SwitchGateway], header_switch: str = "leaf交换机") -> str:
    lines = [
        f"|{header_switch}|网段|网关|VLAN|掩码位数|",
        "|---|---|---|---|---|",
    ]
    for sg in rows:
        lines.append(f"|{sg.name}|{sg.network_segment}|{sg.gateway}|{sg.vlan}|{sg.mask}|")
    return "\n".join(lines)


def switch_gateways_to_dataframe(
    rows: List[SwitchGateway],
    switch_col: str = "leaf交换机",
) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[switch_col, "网段", "网关", "VLAN", "掩码位数"])
    return pd.DataFrame(
        [
            {
                switch_col: sg.name,
                "网段": sg.network_segment,
                "网关": sg.gateway,
                "VLAN": sg.vlan,
                "掩码位数": sg.mask,
            }
            for sg in rows
        ]
    )
