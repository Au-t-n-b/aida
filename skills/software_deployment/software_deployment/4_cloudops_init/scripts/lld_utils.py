# vendored from CPCIA deploymentandtest handler/file_handler/utils.py (subset)
from __future__ import annotations

import ipaddress
import re
from typing import Any, Callable

import numpy as np
import pandas as pd


def find_start_row(df: pd.DataFrame, keyword: str) -> int | None:
    for idx in range(min(10, len(df))):
        row = df.iloc[idx]
        if row.astype(str).str.contains(keyword, na=False).any():
            return idx
    return None


def is_valid_ip(ip_str: Any) -> bool:
    if not isinstance(ip_str, str):
        return False
    try:
        ipaddress.ip_address(ip_str)
        return True
    except (ValueError, TypeError):
        return False


def locate_invalid_cells(df: pd.DataFrame, columns: list[str], func: Callable[[Any], bool]) -> tuple[bool, list]:
    valid_mask = df[columns].apply(lambda col: col.map(func))
    invalid_positions = [
        (row, col) for col in columns for row in df[~valid_mask[col]].index
    ]
    return bool(valid_mask.all().all()), invalid_positions


def split_string_with_num(s: Any) -> tuple[Any, Any]:
    if not s:
        return np.nan, np.nan
    match = re.match(r"([a-zA-Z]+)(\d+)", str(s))
    if match:
        return match.group(1), match.group(2)
    return np.nan, np.nan


def convert_mask_to_prefix(mask: Any) -> str | int:
    try:
        if isinstance(mask, int):
            return mask
        if not mask or len(str(mask)) == 0:
            return ""
        s = str(mask)
        if s.isdigit():
            return s
        ipaddress.IPv4Address(s)
        binary_mask = "".join([bin(int(v) + 256)[3:] for v in s.split(".")])
        return str(binary_mask.count("1"))
    except ipaddress.AddressValueError:
        return ""


def clear_excel_sheet(workbook: Any, sheet_name: str) -> None:
    """对齐 CPCIA ``CloudopsConfigHandler.clear_excel_sheet``。"""
    ws = workbook[sheet_name]
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            cell.value = None


def write_data_to_workbook(df: pd.DataFrame, workbook: Any, sheet_name: str) -> None:
    """按 Excel 表头名写入（对齐 CPCIA ``CloudopsConfigHandler.write_data_to_workbook``）。"""
    ws = workbook[sheet_name]
    header_mapping: dict[str, int] = {}
    for col_idx in range(1, ws.max_column + 1):
        header_value = ws.cell(row=1, column=col_idx).value
        if header_value:
            header_mapping[str(header_value).strip()] = col_idx

    new_row_idx = 2
    for _, row in df.iterrows():
        for col_name in df.columns:
            col_key = str(col_name).strip()
            if col_key not in header_mapping:
                continue
            col_idx = header_mapping[col_key]
            value = row[col_name]
            try:
                if pd.isna(value) or value is None:
                    ws.cell(row=new_row_idx, column=col_idx, value="")
                else:
                    ws.cell(row=new_row_idx, column=col_idx, value=value)
            except Exception:
                pass
        new_row_idx += 1
