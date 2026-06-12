"""端口连线表解析：定位表头、按关键字筛选 LEAF–SPINE 连线、识别 MLAG 对。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from oob_interconnect.constants import HEADER_TOKEN, SPINE_TOKEN


def read_sheet_raw(path: str, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name, header=None)


def find_header_row_idx(df_all: pd.DataFrame) -> int:
    header_mask = df_all.astype(str).apply(
        lambda row: row.str.contains(HEADER_TOKEN, case=False, na=False).any(), axis=1
    )
    if not header_mask.any():
        raise ValueError(f"未找到包含 '{HEADER_TOKEN}' 的表头行，请检查表格内容")
    return int(header_mask.idxmax())


def get_switch_data_l2(
    file_path: str,
    sheet_name_str: str,
    keyword: str,
    peer_keyword: str = SPINE_TOKEN,
) -> tuple[pd.DataFrame, int]:
    """二层：列映射含本端/对端带宽。"""
    df_all = read_sheet_raw(file_path, sheet_name_str)
    header_row_idx = find_header_row_idx(df_all)
    result_df = (
        df_all.iloc[header_row_idx + 1 :]
        .reset_index(drop=True)
        .rename(
            columns={
                df_all.columns[0]: "leaf交换机",
                df_all.columns[1]: "本端端口",
                df_all.columns[2]: "本端接口带宽",
                df_all.columns[-4]: "对端带宽",
                df_all.columns[-2]: "对端端口",
                df_all.columns[-3]: "对端接口类型",
                df_all.columns[-1]: "spine交换机",
            }
        )
    )
    mask = result_df["leaf交换机"].astype(str).str.contains(keyword, case=False, na=False) & result_df[
        "spine交换机"
    ].astype(str).str.contains(peer_keyword, case=False, na=False)
    result_df = result_df.loc[mask].drop_duplicates()
    row_count = result_df.shape[0]
    if row_count == 0:
        raise ValueError(f"未找到包含 '{keyword}' 与 '{peer_keyword}' 的物理连线，请检查连线表")
    return result_df, row_count


def get_switch_data_l3(
    file_path: str,
    sheet_name_str: str,
    keyword: str,
    peer_keyword: str = SPINE_TOKEN,
) -> tuple[pd.DataFrame, int]:
    """三层：不读取带宽列。"""
    df_all = read_sheet_raw(file_path, sheet_name_str)
    header_row_idx = find_header_row_idx(df_all)
    result_df = (
        df_all.iloc[header_row_idx + 1 :]
        .reset_index(drop=True)
        .rename(
            columns={
                df_all.columns[0]: "leaf交换机",
                df_all.columns[1]: "本端端口",
                df_all.columns[-2]: "对端端口",
                df_all.columns[-3]: "对端接口类型",
                df_all.columns[-1]: "spine交换机",
            }
        )
    )
    mask = result_df["leaf交换机"].astype(str).str.contains(keyword, case=False, na=False) & result_df[
        "spine交换机"
    ].astype(str).str.contains(peer_keyword, case=False, na=False)
    result_df = result_df.loc[mask].drop_duplicates()
    row_count = result_df.shape[0]
    if row_count == 0:
        raise ValueError(f"未找到包含 '{keyword}' 与 '{peer_keyword}' 的物理连线，请检查连线表")
    return result_df, row_count


def get_all_switch_mlag_data(file_path: str, sheet_name: str) -> pd.DataFrame:
    """同表识别 MLAG 对：设备列含 leaf|spine，且与「接入交换机」列两端同为 leaf 或同为 spine。"""
    df_all = read_sheet_raw(file_path, sheet_name)
    header_row_idx = None
    for idx, row in df_all.iterrows():
        if row.astype(str).str.contains(HEADER_TOKEN, case=False, na=False).any():
            header_row_idx = idx
            break
    if header_row_idx is None:
        raise ValueError(f"未找到包含 '{HEADER_TOKEN}' 的表头行，请检查表格内容")
    df = df_all.iloc[header_row_idx + 1 :].reset_index(drop=True)
    df.rename(
        columns={
            df.columns[0]: "设备",
            df.columns[1]: "接口",
            df.columns[-1]: "接入交换机",
        },
        inplace=True,
    )
    switch_df = df[df["设备"].astype(str).str.contains("leaf|spine", case=False, na=False)].copy()
    leaf_mask = switch_df["设备"].str.contains("leaf", case=False) & switch_df["接入交换机"].str.contains(
        "leaf", case=False
    )
    spine_mask = switch_df["设备"].str.contains(SPINE_TOKEN, case=False) & switch_df[
        "接入交换机"
    ].str.contains(SPINE_TOKEN, case=False)
    switch_df["标记"] = np.where(leaf_mask | spine_mask, "MLAG", "")
    pair_df = switch_df[["设备", "接入交换机", "标记"]].drop_duplicates()
    return pair_df[pair_df["标记"] == "MLAG"]
