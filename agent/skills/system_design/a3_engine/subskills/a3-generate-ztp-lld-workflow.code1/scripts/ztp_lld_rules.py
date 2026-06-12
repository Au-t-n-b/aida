"""Deterministic ZTP LLD merge rules — aligned with generate_ztp_lld.py."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

import pandas as pd

LOCATION_REQUIRED_COLS = ["设备名称", "所属机房", "所属机柜", "安装起始U位"]
LOOPBACK_REQUIRED_COLS = ["LoopBack起始IP", "LoopBack结束IP"]
COLS_TO_REMOVE = ["用户名", "密码", "设备SN"]

RENAME_MAP = {
    "设备名称": "交换机名称",
    "灵衢L1/L2平面": "L1/L2平面",
    "设备ESN": "ESN",
    "带外管理地址": "管理面IP",
    "带外管理VLAN": "VLAN ID",
}

OUTPUT_COLUMNS_BASE = [
    "交换机名称",
    "机房名称",
    "机柜编号",
    "柜内位置",
    "超节点ID",
    "超节点规模",
    "交换机ID",
    "L1/L2平面",
    "ESN",
    "LoopBack起始IP",
    "LoopBack结束IP",
    "BGP AS号",
    "loopBack0",
    "loopBack1",
    "loopBack2",
    "loopBack3",
    "loopBack4",
    "loopBack5",
    "loopBack6",
    "管理面IP",
    "VLAN ID",
    "网关",
]

OUTPUT_SHEET = "网络IP规划"
OUTPUT_FILENAME = "ZTP_LLD.xlsx"


def ip_range_to_list(start_ip_str: str, end_ip_str: str) -> list[str]:
    try:
        start_ip = ipaddress.IPv4Address(start_ip_str)
        end_ip = ipaddress.IPv4Address(end_ip_str)
    except Exception as exc:
        raise ValueError(f"IP地址格式错误：{exc}") from exc

    if end_ip < start_ip:
        raise ValueError(f"结束IP小于起始IP：{start_ip} -> {end_ip}")

    return [
        str(ipaddress.IPv4Address(int(start_ip) + i))
        for i in range(int(end_ip) - int(start_ip) + 1)
    ]


def read_inputs(
    location_path: Path,
    cpm_path: Path,
    manage_path: Path,
    location_sheet: str = "设备位置信息",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    try:
        df_loopback = pd.read_excel(cpm_path)
        df_manage = pd.read_excel(manage_path)
        df_location = pd.read_excel(location_path, sheet_name=location_sheet)
    except Exception as exc:
        raise RuntimeError("读取Excel文件时发生错误，请确认文件格式是否正确") from exc

    if "设备名称" not in df_loopback.columns:
        raise KeyError(f"超平面网络规划文件缺少'设备名称'列，请检查文件：{cpm_path}")
    if "设备名称" not in df_manage.columns:
        raise KeyError(f"灵衢带外管理地址规划文件缺少'设备名称'列，请检查文件：{manage_path}")

    return df_location, df_loopback, df_manage


def generate_ztp_lld_dataframe(
    df_location: pd.DataFrame,
    df_loopback: pd.DataFrame,
    df_manage: pd.DataFrame,
) -> pd.DataFrame:
    for col in LOCATION_REQUIRED_COLS:
        if col not in df_location.columns:
            raise KeyError(f"设备位置信息文件缺少必要列：{col}")

    location_map = df_location.set_index("设备名称")[["所属机房", "所属机柜", "安装起始U位"]]
    location_dict = {
        idx: [row["所属机房"], row["所属机柜"], str(row["安装起始U位"]) + "U"]
        for idx, row in location_map.iterrows()
    }

    def lookup(name: Any) -> list[Any]:
        if pd.isna(name):
            return [None, None, None]
        return location_dict.get(str(name).strip(), [None, None, None])

    merged_df = pd.merge(df_manage, df_loopback, on="设备名称", how="left")

    rack_df = pd.DataFrame(
        merged_df["设备名称"].map(lookup).tolist(),
        index=merged_df.index,
        columns=["机房名称", "机柜编号", "柜内位置"],
    )
    merged_df[["机房名称", "机柜编号", "柜内位置"]] = rack_df[["机房名称", "机柜编号", "柜内位置"]]

    for col in COLS_TO_REMOVE:
        if col in merged_df.columns:
            merged_df.drop(columns=[col], inplace=True)

    for col in LOOPBACK_REQUIRED_COLS:
        if col not in merged_df.columns:
            raise KeyError(f"缺少必要列：{col}")

    loopback_cols: list[str] = []
    max_loopbacks = 7
    for _, row in merged_df.iterrows():
        try:
            ips = ip_range_to_list(row["LoopBack起始IP"], row["LoopBack结束IP"])
        except Exception as exc:
            raise ValueError(
                "请检查设备位置表和超平面地址规划的设备名称是否匹配，存在不匹配情况，"
                f"报错堆栈{exc}"
            ) from exc
        max_loopbacks = max(max_loopbacks, len(ips))

    for i in range(max_loopbacks):
        col_name = f"loopBack{i}"
        loopback_cols.append(col_name)
        merged_df[col_name] = None

    for idx, row in merged_df.iterrows():
        ips = ip_range_to_list(row["LoopBack起始IP"], row["LoopBack结束IP"])
        for i, ip in enumerate(ips):
            merged_df.at[idx, loopback_cols[i]] = ip
        merged_df.at[idx, "网关"] = f"{row['带外管理网关']}/{row['带外管理掩码']}"

    return finalize_output_dataframe(merged_df)


def finalize_output_dataframe(merged_df: pd.DataFrame) -> pd.DataFrame:
    out = merged_df.rename(columns=RENAME_MAP)
    for col in OUTPUT_COLUMNS_BASE:
        if col not in out.columns:
            out[col] = None
    return out[OUTPUT_COLUMNS_BASE]


def write_ztp_lld_excel(df: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, sheet_name=OUTPUT_SHEET, index=False)
    return output_path
