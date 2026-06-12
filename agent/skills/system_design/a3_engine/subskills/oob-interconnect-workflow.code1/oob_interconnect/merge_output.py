"""输出 Excel：支持整表覆盖或按网络平面替换后合并。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from oob_interconnect.constants import OUTPUT_SHEET


def write_output(path: str | Path, df: pd.DataFrame, sheet_name: str = OUTPUT_SHEET) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, sheet_name=sheet_name, index=False)


def merge_output_by_plane(
    path: str | Path,
    df: pd.DataFrame,
    sheet_name: str = OUTPUT_SHEET,
) -> pd.DataFrame:
    """按项目脚本口径合并输出：删除旧表中本次网络平面后追加新结果。"""
    output_path = Path(path)
    if "网络平面" not in df.columns:
        raise ValueError("输出结果缺少 '网络平面' 列，无法按平面合并。")

    new_planes = set(df["网络平面"].dropna().astype(str).str.strip())
    old_df = pd.DataFrame()
    if output_path.is_file():
        try:
            old_df = pd.read_excel(output_path, sheet_name=sheet_name, header=0)
        except ValueError:
            old_df = pd.read_excel(output_path, sheet_name=0, header=0)
    if not old_df.empty and "网络平面" in old_df.columns:
        old_planes = old_df["网络平面"].astype(str).str.strip()
        old_df = old_df.loc[~old_planes.isin(new_planes)]

    merged = pd.concat([old_df, df], axis=0, ignore_index=True)
    write_output(output_path, merged, sheet_name)
    return merged
