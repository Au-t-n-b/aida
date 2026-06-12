"""BGP AS 分配（严格对齐 a3_switch_loopback_ip_address.a3_switch_loopback_ip_generate）。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from switch_asn_io import (
    LOOPBACK_CONFIG,
    InMemoryGatewayStore,
    PlanePlan,
    get_leaf_spine_data,
)


def allocate_bgp_as_for_plane(
    *,
    connect_path: Path,
    resource_path: Path,
    plan: PlanePlan,
    gateway_store: InMemoryGatewayStore,
    sheet_res_index: int = 0,
) -> pd.DataFrame:
    """
    对齐 a3_switch_loopback_ip_generate：
    Leaf 按 as_start+idx 递增并避让用户库中其它平面已占用 AS；
    Spine 默认 max(leaf_as)+1，若库中该 SPINE 已有 AS 则复用。
    """
    sheet_name = plan.config_key
    if sheet_name not in LOOPBACK_CONFIG:
        raise ValueError(f"sheet_name '{sheet_name}' 没有对应的配置项。")

    keyword = plan.keyword
    web_network_type_name = plan.web_network_type_name

    leafs, spines = get_leaf_spine_data(connect_path, plan.sheet_connect, keyword)
    as_range_str = plan.as_range_str

    as_start = None
    unique_as_list: List = []
    spine_as_dict: Dict[str, str] = {}

    if "-" in as_range_str:
        as_start, _as_end = map(int, as_range_str.split("-", 1))
        gateway_info = gateway_store.query_all()
        filtered_records = [record for record in gateway_info if record[3] != web_network_type_name]
        as_list = [tpl[6] for tpl in filtered_records]
        set_as_list = list(set(as_list))
        unique_as_list = [x for x in set_as_list if x != "NA" and x != ""]
        # 与线上一致（含原脚本空列表分支写法）
        if not unique_as_list:
            unique_as_list = [int(item) for item in unique_as_list]
        for item in filtered_records:
            name = item[4]
            as_value = item[6]
            if "SPINE" in name and as_value != "NA" and as_value != "":
                spine_as_dict[name] = as_value

    results: List[Dict[str, str]] = []
    max_leaf_as = as_start

    for idx, leaf in enumerate(leafs):
        as_number = ""
        if as_start:
            as_number = as_start + idx
            while as_number in unique_as_list:
                as_number += 1
                as_start += 1
        results.append(
            {
                "设备名称": leaf,
                "Loopback接口名称": "loopback0",
                "BGP AS": as_number,
            }
        )
        max_leaf_as = as_number

    spine_as = ""
    if max_leaf_as:
        spine_as = max_leaf_as + 1
        while spine_as in unique_as_list:
            spine_as += 1

    for spine in spines:
        spine_as_last = spine_as_dict.get(spine, spine_as)
        results.append(
            {
                "设备名称": spine,
                "Loopback接口名称": "loopback0",
                "BGP AS": spine_as_last,
            }
        )

    result_df = pd.DataFrame(results)
    gateway_store.upsert_scope_from_allocation(web_network_type_name, results)
    return result_df


def allocate_all_planes(
    *,
    connect_path: Path,
    resource_path: Path,
    plans: List[PlanePlan],
    gateway_store: InMemoryGatewayStore,
    sheet_res_index: int = 0,
) -> Dict[str, pd.DataFrame]:
    per_plane: Dict[str, pd.DataFrame] = {}
    for plan in plans:
        per_plane[plan.web_network_type_name] = allocate_bgp_as_for_plane(
            connect_path=connect_path,
            resource_path=resource_path,
            plan=plan,
            gateway_store=gateway_store,
            sheet_res_index=sheet_res_index,
        )
    return per_plane
