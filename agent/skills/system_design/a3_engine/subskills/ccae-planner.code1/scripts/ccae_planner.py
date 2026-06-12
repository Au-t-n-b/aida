"""CCAE 部署规划主流程：校验 → 分配 → 组装输出表。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

from ccae_ip_rules import PLANE_SPECS, AllocatedRow, allocate_plane
from ccae_resource_parser import PlaneResourceRow, load_resource_dataframe, parse_plane_resources
from ccae_topology_parser import DEFAULT_SHEET, load_mlag_peer_names, load_topology_ccae_devices

MODULE1_COLUMNS = [
    "设备名称",
    "网络平面",
    "接口名称",
    "IP地址",
    "掩码",
    "网关",
    "VLAN",
    "Bond模式",
    "目的网段",
    "目的掩码",
]
MODULE2_COLUMNS = [
    "网络用途",
    "网络平面",
    "接口名称",
    "IP地址",
    "子网掩码",
    "网关",
    "VLAN",
    "Bond模式",
    "目的网段",
    "目的掩码",
]
SHEET_NAME = "CCAE部署方案"


@dataclass(frozen=True)
class PlannerInputs:
    topology_path: str
    resource_path: str
    sheet_topology: str = DEFAULT_SHEET
    resource_sheet_index: int = 0
    mlag_list_path: Optional[str] = None


@dataclass(frozen=True)
class PlannerResult:
    module1: pd.DataFrame
    module2: pd.DataFrame
    switch_mlag_flag: bool


def _row_to_module1(r: AllocatedRow) -> dict:
    return {
        "设备名称": r.device_or_usage,
        "网络平面": r.plane_display,
        "接口名称": r.bond,
        "IP地址": r.ip,
        "掩码": r.mask,
        "网关": r.gateway,
        "VLAN": r.vlan,
        "Bond模式": r.bond_mode,
        "目的网段": r.dest_net,
        "目的掩码": r.dest_mask,
    }


def _row_to_module2(r: AllocatedRow) -> dict:
    return {
        "网络用途": r.device_or_usage,
        "网络平面": r.plane_display,
        "接口名称": r.bond,
        "IP地址": r.ip,
        "子网掩码": r.mask,
        "网关": r.gateway,
        "VLAN": r.vlan,
        "Bond模式": r.bond_mode,
        "目的网段": r.dest_net,
        "目的掩码": r.dest_mask,
    }


def run_planner(inputs: PlannerInputs) -> PlannerResult:
    devices = load_topology_ccae_devices(inputs.topology_path, inputs.sheet_topology)
    res_df = load_resource_dataframe(inputs.resource_path, inputs.resource_sheet_index)
    planes = parse_plane_resources(res_df)

    if not planes:
        raise ValueError("资源表中未匹配到任何 CCAE 网络平面行，请检查网络平面命名")

    switch_mlag_flag = False
    if inputs.mlag_list_path:
        mlag_peers = load_mlag_peer_names(inputs.mlag_list_path)
        switch_mlag_flag = any(d in mlag_peers for d in devices)

    mod1_rows: List[dict] = []
    mod2_rows: List[dict] = []

    for spec in PLANE_SPECS:
        res: Optional[PlaneResourceRow] = planes.get(spec.key)
        if res is None:
            continue
        allocated = allocate_plane(
            spec=spec,
            devices=devices,
            ip_pool=res.ip_pool,
            mask=res.mask,
            vlan_raw=res.vlan_raw,
            gateway_position=res.gateway_position,
            gateway_address=res.gateway_address,
            occupied_ips=set(res.occupied_ips),
            reserved_ips=set(res.reserved_ips),
        )
        for row in allocated:
            if row.is_vip:
                mod2_rows.append(_row_to_module2(row))
            else:
                mod1_rows.append(_row_to_module1(row))

    if not mod1_rows:
        raise ValueError("未生成任何节点地址行，请确认资源表至少有一个可用平面")

    return PlannerResult(
        module1=pd.DataFrame(mod1_rows, columns=MODULE1_COLUMNS),
        module2=pd.DataFrame(mod2_rows, columns=MODULE2_COLUMNS),
        switch_mlag_flag=switch_mlag_flag,
    )


def write_ccae_excel(result: PlannerResult, output_path: str) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        start_row = 0
        result.module1.to_excel(
            writer, sheet_name=SHEET_NAME, index=False, startrow=start_row
        )
        start_row += len(result.module1) + 2
        if not result.module2.empty:
            result.module2.to_excel(
                writer, sheet_name=SHEET_NAME, index=False, startrow=start_row
            )
    return out


def validate_inputs(inputs: PlannerInputs) -> None:
    load_topology_ccae_devices(inputs.topology_path, inputs.sheet_topology)
    res_df = load_resource_dataframe(inputs.resource_path, inputs.resource_sheet_index)
    planes = parse_plane_resources(res_df)
    if not planes:
        raise ValueError("资源表未匹配到 CCAE 网络平面")
    if inputs.mlag_list_path and not Path(inputs.mlag_list_path).is_file():
        raise ValueError(f"MLAG 列表文件不存在: {inputs.mlag_list_path}")
