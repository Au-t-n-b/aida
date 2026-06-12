"""007 端口互联表 · 建模仿真结构化格式读取（起始端信息 / 目的端信息 双行表头）。

对齐 utils.process_excel_or_db_data、storage_dw_manage_rules.read_structured_007、
network_access_plan.read_connect_dataframe。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

import pandas as pd

SheetSpec = Union[str, int]


def find_header_row(df: pd.DataFrame, needle: str = "设备命名") -> int:
    for idx, row in df.iterrows():
        if row.astype(str).str.contains(needle, case=False, na=False).any():
            return int(idx)
    raise ValueError(f"未找到包含{needle!r}的行，请检查表格内容")


def is_structured_007(raw: pd.DataFrame) -> bool:
    """首行含「起始端信息」且次行含「设备命名」→ 建模仿真双行表头格式。"""
    if raw.empty or raw.shape[0] < 2:
        return False
    row0 = raw.iloc[0].astype(str).tolist()
    row1 = raw.iloc[1].astype(str).tolist()
    has_group = any("起始端信息" in str(c) for c in row0)
    has_name = any("设备命名" in str(c) for c in row1)
    return has_group and has_name


def read_structured_007_raw(raw: pd.DataFrame) -> pd.DataFrame:
    """将已读入的 raw（header=None）解析为带合并列名的 DataFrame。"""
    if raw.iloc[0].astype(str).str.contains("起始端信息-设备命名", case=False, na=False).any():
        return raw.iloc[1:].reset_index(drop=True)

    if not is_structured_007(raw):
        raise ValueError("not structured 007 layout")

    header_idx = 1
    group_idx = 0
    row0 = raw.iloc[group_idx].values
    row1 = raw.iloc[header_idx].values
    new_columns: List[str] = []
    j = 0
    for i in range(len(row0)):
        g = str(row0[i] or "").strip()
        sub = str(row1[i] or "").strip()
        if g == "起始端信息":
            new_columns.append(f"起始端信息-{sub}")
            j = i
        elif g == "目的端信息":
            new_columns.append(f"目的端信息-{sub}")
            j = i
        elif g == "线缆信息":
            new_columns.append(f"线缆信息-{sub}")
            j = i
        elif sub:
            new_columns.append(f"{str(row0[j] or '').strip()}-{sub}" if str(row0[j] or "").strip() else sub)
        else:
            new_columns.append(f"col{i}")
    data_rows = raw.iloc[header_idx + 1 :].values.tolist()
    return pd.DataFrame(data_rows, columns=new_columns)


def read_structured_007(path: Path, sheet: SheetSpec) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str).fillna("")
    return read_structured_007_raw(raw)


def pick_column(df: pd.DataFrame, *candidates: str) -> str:
    cols = [str(c) for c in df.columns]
    for cand in candidates:
        for col in cols:
            if cand == col or cand in col:
                return col
    raise KeyError(f"columns missing any of {candidates!r}; have {cols}")


def try_read_structured(path: Path, sheet: SheetSpec) -> Optional[pd.DataFrame]:
    try:
        raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str).fillna("")
        if not is_structured_007(raw):
            return None
        return read_structured_007_raw(raw)
    except Exception:
        return None


def read_legacy_flat_connect(
    path: Path,
    sheet: SheetSpec,
    *,
    server_col: int = 0,
    port_col: int = 1,
    peer_col: int = -1,
) -> pd.DataFrame:
    """旧版扁平行：表头行含「设备命名」，数据区首列=服务器、末列=对端交换机。"""
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str).fillna("")
    header_idx = find_header_row(raw)
    df = raw.iloc[header_idx + 1 :].reset_index(drop=True)
    if df.shape[1] < 3:
        raise ValueError("端口互联表列数不足（至少需要：计算服务器、端口、leaf）")
    cols = list(df.columns)
    df = df.rename(
        columns={
            cols[server_col]: "计算服务器",
            cols[port_col]: "服务器端口",
            cols[peer_col]: "leaf交换机",
        }
    )
    return df[["计算服务器", "服务器端口", "leaf交换机"]]


def read_server_leaf_connect(
    path: Path,
    sheet: SheetSpec,
    *,
    server_keyword: str,
) -> pd.DataFrame:
    """统一读取：自动识别结构化 / 扁平行，返回 计算服务器 / 服务器端口 / leaf交换机。"""
    structured = try_read_structured(path, sheet)
    if structured is not None:
        src = pick_column(structured, "起始端信息-设备命名", "设备命名")
        port = pick_column(structured, "起始端信息-接口信息", "接口信息")
        leaf = pick_column(structured, "目的端信息-设备命名")
        out = pd.DataFrame(
            {
                "计算服务器": structured[src].astype(str).str.strip(),
                "服务器端口": structured[port].astype(str).str.strip(),
                "leaf交换机": structured[leaf].astype(str).str.strip(),
            }
        )
        out = out[
            (out["计算服务器"] != "")
            & (out["leaf交换机"] != "")
            & (out["计算服务器"].str.lower() != "nan")
            & (out["leaf交换机"].str.lower() != "nan")
        ]
        if not out.empty:
            return out.reset_index(drop=True)

    flat = read_legacy_flat_connect(path, sheet)
    # 扁平行：若首列为设备 ID（纯数字），设备名在第二列
    sample = flat["计算服务器"].astype(str).head(20)
    if sample.str.fullmatch(r"\d+", na=False).mean() > 0.5:
        raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str).fillna("")
        header_idx = find_header_row(raw)
        df = raw.iloc[header_idx + 1 :].reset_index(drop=True)
        cols = list(df.columns)
        if len(cols) >= 3:
            flat = df.rename(
                columns={
                    cols[1]: "计算服务器",
                    cols[2]: "服务器端口",
                    cols[-2]: "leaf交换机",
                }
            )[["计算服务器", "服务器端口", "leaf交换机"]]
    if not flat["计算服务器"].astype(str).str.contains(server_keyword, case=False, na=False, regex=True).any():
        raise ValueError(
            f"端口互联表未匹配到服务器关键字 {server_keyword!r}（结构化/扁平行均已尝试）"
        )
    return flat


def structured_peer_devices(path: Path, sheet: SheetSpec) -> list[str]:
    """结构化表：目的端设备命名去重列表（超平面 L2 等）。"""
    structured = try_read_structured(path, sheet)
    if structured is None:
        return []
    leaf = pick_column(structured, "目的端信息-设备命名")
    vals = [str(v).strip() for v in structured[leaf].tolist()]
    seen: set[str] = set()
    out: list[str] = []
    for v in vals:
        if v and v.lower() != "nan" and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def structured_source_devices(path: Path, sheet: SheetSpec) -> list[str]:
    """结构化表：起始端设备命名去重列表。"""
    structured = try_read_structured(path, sheet)
    if structured is None:
        return []
    src = pick_column(structured, "起始端信息-设备命名", "设备命名")
    vals = [str(v).strip() for v in structured[src].tolist()]
    seen: set[str] = set()
    out: list[str] = []
    for v in vals:
        if v and v.lower() != "nan" and v not in seen:
            seen.add(v)
            out.append(v)
    return out
