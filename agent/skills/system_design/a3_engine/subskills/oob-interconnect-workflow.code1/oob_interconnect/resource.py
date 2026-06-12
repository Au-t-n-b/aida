"""项目信息收集表解析：按「网络平面」行取 VLAN 与互连地址段。"""
from __future__ import annotations

import pandas as pd

from oob_interconnect.constants import (
    RESOURCE_GATEWAY_LOCATION_COLUMN,
    RESOURCE_IP_POOL_COLUMN,
    RESOURCE_PLANE_COLUMN,
    RESOURCE_SHEET,
    RESOURCE_VLAN_COLUMN,
)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _has_resource_columns(df: pd.DataFrame) -> bool:
    return RESOURCE_PLANE_COLUMN in df.columns


def read_resource_table(path: str, sheet_name: str = RESOURCE_SHEET) -> pd.DataFrame:
    """读取资源信息。

    优先读取传统 ``资源表`` sheet；若项目使用「项目信息收集表」且 sheet 名不同，
    自动扫描首个包含「网络平面」列的 sheet。
    """
    try:
        df = _normalize_columns(pd.read_excel(path, sheet_name=sheet_name, header=0))
        if _has_resource_columns(df):
            return df
    except ValueError:
        pass

    sheets = pd.read_excel(path, sheet_name=None, header=0)
    for candidate_sheet, candidate_df in sheets.items():
        candidate_df = _normalize_columns(candidate_df)
        if _has_resource_columns(candidate_df):
            return candidate_df
    available = ", ".join(str(name) for name in sheets.keys())
    raise ValueError(
        f"项目信息收集表中未找到包含列 '{RESOURCE_PLANE_COLUMN}' 的资源 sheet。"
        f" 已检查: {available}"
    )


def _pick_row(df: pd.DataFrame, network_type: str) -> pd.DataFrame:
    if RESOURCE_PLANE_COLUMN not in df.columns:
        raise ValueError(f"资源表中未找到列 '{RESOURCE_PLANE_COLUMN}'。")
    row = df[df[RESOURCE_PLANE_COLUMN].astype(str).str.strip() == network_type.strip()]
    if row.empty:
        raise ValueError(f"资源表中未找到 {RESOURCE_PLANE_COLUMN} == '{network_type}' 的行。")
    return row


def get_vlan_for_plane(
    resource_path: str,
    network_type: str,
    sheet_name: str = RESOURCE_SHEET,
    vlan_column: str = RESOURCE_VLAN_COLUMN,
):
    df = read_resource_table(resource_path, sheet_name)
    row = _pick_row(df, network_type)
    col = vlan_column if vlan_column in df.columns else None
    if col is None:
        for c in df.columns:
            if str(c).strip().upper().startswith(vlan_column.upper()):
                col = c
                break
    if col is None:
        raise ValueError(f"资源表中未找到 VLAN 列（期望含 '{vlan_column}'）。")
    vlan = row[col].values[0]
    if pd.isna(vlan):
        raise ValueError(f"{network_type} 的 VLAN 为空。")
    return vlan


def get_interconnect_ip_pool(
    resource_path: str,
    network_type: str,
    sheet_name: str = RESOURCE_SHEET,
    ip_pool_column: str = RESOURCE_IP_POOL_COLUMN,
) -> list[str]:
    df = read_resource_table(resource_path, sheet_name)
    row = _pick_row(df, network_type)
    col = ip_pool_column
    if col not in df.columns:
        col = _find_first_existing_column(
            df,
            [
                "内部网络设备互连地址段",
                "内部网络设备互联地址段",
                "网络设备互连地址段",
            ],
        )
    if col is None:
        col = _find_ip_pool_column(row)
    if col is None:
        raise ValueError(f"资源表中未找到列 '{ip_pool_column}'，也未找到可用的 IPv4 起止地址段。")
    ip_pool = row[col].values[0]
    if pd.isna(ip_pool) or not str(ip_pool).strip():
        raise ValueError(f"{network_type} 的互连地址段为空。")
    parts = str(ip_pool).split("-")
    if len(parts) != 2:
        raise ValueError(f"互连地址段格式应为 '起始IP-结束IP'，当前: {ip_pool!r}")
    return [parts[0].strip(), parts[1].strip()]


def _find_first_existing_column(df: pd.DataFrame, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def _find_ip_pool_column(row: pd.DataFrame) -> str | None:
    for col, value in row.iloc[0].items():
        text = "" if pd.isna(value) else str(value).strip()
        parts = text.split("-")
        if len(parts) == 2 and _is_ipv4(parts[0].strip()) and _is_ipv4(parts[1].strip()):
            return str(col)
    return None


def _is_ipv4(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False


def get_gateway_location(
    resource_path: str,
    network_type: str,
    sheet_name: str = RESOURCE_SHEET,
    gateway_location_column: str = RESOURCE_GATEWAY_LOCATION_COLUMN,
) -> str | None:
    """读取网关位置，返回 ``leaf`` / ``spine``；未配置时返回 ``None`` 保持旧行为。"""
    df = read_resource_table(resource_path, sheet_name)
    row = _pick_row(df, network_type)
    col = gateway_location_column if gateway_location_column in df.columns else None
    if col is None:
        for c in df.columns:
            if str(c).strip().startswith(gateway_location_column):
                col = c
                break
    if col is None:
        return None

    raw = row[col].values[0]
    if pd.isna(raw) or not str(raw).strip():
        return None
    normalized = str(raw).strip().lower()
    has_leaf = "leaf" in normalized
    has_spine = "spine" in normalized
    if has_leaf == has_spine:
        raise ValueError(f"{network_type} 的网关位置应明确为 LEAF 或 SPINE，当前: {raw!r}")
    return "leaf" if has_leaf else "spine"
