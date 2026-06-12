"""解析项目信息收集表 / 网络资源表中 CCAE 各平面行。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from ccae_ip_rules import PLANE_SPECS, PlaneSpec, match_plane_name, parse_ip_set


def _norm_col(name: str) -> str:
    return str(name).strip().lower().replace("*", "").replace(" ", "")


def _first_nonempty(row: pd.Series, candidates: List[str]) -> str:
    norm_to_col = {_norm_col(c): c for c in row.index}

    for cand in candidates:
        n = _norm_col(cand)
        col = norm_to_col.get(n)
        if col is None:
            for nc, orig in norm_to_col.items():
                if n and n in nc:
                    col = orig
                    break
        if col is None:
            continue
        v = row[col]
        if pd.notna(v) and str(v).strip() not in ("", "nan", "None", "NaN"):
            return str(v).strip()
    return ""


@dataclass(frozen=True)
class PlaneResourceRow:
    spec: PlaneSpec
    plane_name: str
    ip_pool: str
    mask: str
    vlan_raw: str
    gateway_position: str
    gateway_address: str
    occupied_ips: frozenset
    reserved_ips: frozenset


def load_resource_dataframe(resource_path: str, sheet_index: int = 0) -> pd.DataFrame:
    df = pd.read_excel(resource_path, sheet_name=sheet_index, header=0)
    if "网络平面" not in df.columns:
        raise ValueError("资源表缺少列「网络平面」")
    return df


def parse_plane_resources(df: pd.DataFrame) -> Dict[str, PlaneResourceRow]:
    """按 PLANE_SPECS 顺序匹配资源行；每个 spec 至多一行。"""
    out: Dict[str, PlaneResourceRow] = {}
    for spec in PLANE_SPECS:
        matched: Optional[pd.Series] = None
        matched_name = ""
        for _, row in df.iterrows():
            plane = str(row.get("网络平面", ""))
            if not plane or plane.strip() in ("网络平面", "nan"):
                continue
            if "CCAE" not in plane.upper() and not any(
                k in plane for k in spec.match_keywords
            ):
                continue
            if match_plane_name(plane, spec):
                matched = row
                matched_name = plane
                break
        if matched is None:
            continue

        ip_pool = _first_nonempty(
            matched,
            ["地址池*", "地址池", "network_pool", "ip_pool"],
        )
        if not ip_pool:
            raise ValueError(f"{spec.display_name}: 缺少地址池")

        mask = _first_nonempty(matched, ["最小规划掩码*", "最小规划掩码", "掩码"])
        if not mask:
            raise ValueError(f"{spec.display_name}: 缺少最小规划掩码")

        vlan_raw = _first_nonempty(matched, ["VLAN*", "VLAN"])
        gw_pos = _first_nonempty(matched, ["网关位置*", "网关位置", "gateway_position"])
        gw_addr = _first_nonempty(matched, ["网关地址*", "网关地址", "gateway_address"])

        if spec.require_gateway_vlan and not gw_pos:
            raise ValueError(f"{spec.display_name}: 缺少网关位置")

        occupied = parse_ip_set(
            _first_nonempty(matched, ["occupied_ip", "占用IP", "已占用IP", "占用地址"])
        )
        reserved = parse_ip_set(
            _first_nonempty(matched, ["reserved_ips", "保留IP", "预留IP"])
        )

        out[spec.key] = PlaneResourceRow(
            spec=spec,
            plane_name=matched_name,
            ip_pool=ip_pool,
            mask=mask,
            vlan_raw=vlan_raw,
            gateway_position=gw_pos,
            gateway_address=gw_addr,
            occupied_ips=frozenset(occupied),
            reserved_ips=frozenset(reserved),
        )
    return out
