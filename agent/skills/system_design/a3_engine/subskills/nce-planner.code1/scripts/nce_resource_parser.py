"""Parse NCE resource rows from the project information workbook."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

NCE_PLANE_NAMES = (
    "NCEFB内部通信网络",
    "NCEFB北向网络",
    "NCEFB南向网络",
    "NCEFB BGP南向网络",
    "NCEFI北向网络",
    "NCEFI南向网络",
)


def _norm_col(name: str) -> str:
    return str(name).strip().lower().replace("*", "").replace(" ", "")


def _first_nonempty(row: pd.Series, candidates: List[str]) -> str:
    norm_to_col = {_norm_col(col): col for col in row.index}
    for candidate in candidates:
        wanted = _norm_col(candidate)
        col = norm_to_col.get(wanted)
        if col is None:
            for normed, original in norm_to_col.items():
                if wanted and wanted in normed:
                    col = original
                    break
        if col is None:
            continue
        value = row[col]
        if pd.notna(value) and str(value).strip() not in ("", "nan", "None", "NaN"):
            return str(value).strip()
    return ""


@dataclass(frozen=True)
class NceResourceRow:
    plane_name: str
    ip_pool: str
    mask: str
    vlan_raw: str
    gateway_position: str
    gateway_address: str


def load_resource_dataframe(resource_path: str, sheet_index: int = 0) -> pd.DataFrame:
    df = pd.read_excel(resource_path, sheet_name=sheet_index, header=0)
    if "网络平面" not in df.columns:
        raise ValueError("项目信息收集表缺少列「网络平面」")
    return df


def parse_nce_resources(df: pd.DataFrame) -> Dict[str, NceResourceRow]:
    resources: Dict[str, NceResourceRow] = {}
    for plane_name in NCE_PLANE_NAMES:
        matched = df[df["网络平面"] == plane_name]
        if matched.empty:
            continue
        row = matched.iloc[0]
        ip_pool = _first_nonempty(row, ["地址池*", "地址池", "ip_pool", "network_pool"])
        mask = _first_nonempty(row, ["最小规划掩码*", "最小规划掩码", "掩码"])
        vlan_raw = _first_nonempty(row, ["VLAN*", "VLAN"])
        gateway_position = _first_nonempty(row, ["网关位置*", "网关位置", "gateway_position"])
        gateway_address = _first_nonempty(row, ["网关地址*", "网关地址", "gateway_address"])

        if not ip_pool:
            raise ValueError(f"{plane_name}: 缺少地址池*")
        if not mask:
            raise ValueError(f"{plane_name}: 缺少最小规划掩码")
        if "内部通信网络" not in plane_name:
            if not vlan_raw:
                raise ValueError(f"{plane_name}: 缺少 VLAN*")
            if not gateway_position and not gateway_address:
                raise ValueError(f"{plane_name}: 缺少网关位置* 或 网关地址*")

        resources[plane_name] = NceResourceRow(
            plane_name=plane_name,
            ip_pool=ip_pool,
            mask=mask,
            vlan_raw=vlan_raw,
            gateway_position=gateway_position,
            gateway_address=gateway_address,
        )

    if not resources:
        raise ValueError("未找到网络平面为 NCEFB 或 NCEFI 的记录，请检查项目信息收集表内容")
    return resources
