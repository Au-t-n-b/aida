"""Offline L2/L3 resolution from 项目信息收集表 (aligned with execute_three_instruction)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from lld_config import INSTRUCTION_NETWORK_TYPE_CONFIG, WEB_NETWORK_TYPE_CONFIG


def _find_resource_sheet(path: Path) -> pd.DataFrame:
    xls = pd.ExcelFile(path)
    for name in xls.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=name, header=0)
            if "网络平面" in df.columns:
                return df
        except Exception:
            continue
    return pd.read_excel(path, sheet_name=0, header=0)


def load_net_to_gateway(resource_path: Path) -> Dict[str, str]:
    df = _find_resource_sheet(resource_path)
    if "网络平面" not in df.columns:
        return {}
    gateway_col = None
    for col in df.columns:
        if "网关位置" in str(col):
            gateway_col = col
            break
    if gateway_col is None:
        return {}
    selected = df[["网络平面", gateway_col]].dropna(subset=[gateway_col])
    result: Dict[str, str] = {}
    for _, row in selected.iterrows():
        plane = str(row["网络平面"]).strip()
        role = str(row[gateway_col]).strip().upper()
        if plane:
            result[plane] = role
    return result


def resolve_layer_suffix(instruction: str, net_to_gateway: Dict[str, str]) -> Optional[str]:
    gate = INSTRUCTION_NETWORK_TYPE_CONFIG.get(instruction)
    if not gate or gate == "互联":
        return None
    net_name = WEB_NETWORK_TYPE_CONFIG.get(gate)
    if not net_name:
        return None
    gateway = net_to_gateway.get(net_name, "SPINE")
    if str(gateway).upper() == "LEAF":
        return "L3"
    return "L2"


def resolve_instruction_with_layer(
    instruction: str,
    layer_from_resource: bool,
    net_to_gateway: Dict[str, str],
    web_network_key: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    layer = None
    if layer_from_resource:
        layer = resolve_layer_suffix(instruction, net_to_gateway)
        if layer is None and web_network_key:
            gateway = net_to_gateway.get(web_network_key, "SPINE")
            layer = "L3" if str(gateway).upper() == "LEAF" else "L2"
    if layer:
        return f"{instruction}_{layer}", layer
    return instruction, layer
