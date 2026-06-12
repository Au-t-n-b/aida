#!/usr/bin/env python3
"""校验 YBM 离线流水线输入 — 可按 --network-plane 指定网络平面。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    sys.exit(2)


SHEET_007_DEFAULT = "存储面端口互联 | 样本面端口互联"
SHEET_RES_DEFAULT = "网络资源需求表"
IP_POOL_PATTERN = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$")


_THIS_FILE = Path(__file__).resolve()
_A3_YBM_DIR = _THIS_FILE.parent.parent
_REPO_ROOT = _A3_YBM_DIR.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

for p in (str(_SCRIPTS_DIR), str(_THIS_FILE.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from ybm_excel_io import autodetect_007_in_cwd, autodetect_resource_in_cwd, require_under_cwd


def _find_header_row_007(df_raw: pd.DataFrame) -> Optional[int]:
    for idx, row in df_raw.iterrows():
        if row.astype(str).str.contains("设备命名", case=False, na=False).any():
            return int(idx)
    return None


def validate_007(path: Path, sheet_name: str, server_substring: str) -> List[str]:
    errors: List[str] = []
    try:
        xls = pd.ExcelFile(path)
    except Exception as e:
        return [f"007: cannot open file: {e}"]
    sheet_spec = str(sheet_name).strip()
    if sheet_spec.isdigit():
        sheet_idx = int(sheet_spec)
        if sheet_idx < 0 or sheet_idx >= len(xls.sheet_names):
            errors.append(f"007: sheet index {sheet_idx} out of range.")
            return errors
        sheet: object = sheet_idx
        sheet_label = f"index={sheet_idx}"
    else:
        if sheet_spec not in xls.sheet_names:
            errors.append(f"007: sheet '{sheet_spec}' not found.")
            return errors
        sheet = sheet_spec
        sheet_label = repr(sheet_spec)

    df_raw = pd.read_excel(path, sheet_name=sheet, header=None)
    h = _find_header_row_007(df_raw)
    if h is None:
        errors.append(f"007: no row containing '设备命名' ({sheet_label})")
        return errors
    data = df_raw.iloc[h + 1 :]
    if data.empty:
        errors.append("007: no data rows after header row")
        return errors
    if data.shape[1] < 2:
        errors.append("007: need at least 2 columns")
        return errors
    col0 = data.iloc[:, 0].astype(str)
    if server_substring:
        filtered = data[col0.str.contains(re.escape(server_substring), regex=True, na=False)]
        if filtered.empty:
            errors.append(f"007: after filter server_substring={server_substring!r}, no rows left in first column")
            return errors
    print(f"007: OK — sheet={sheet_name!r}, header_row_idx={h}, data_rows={len(data)}")
    return errors


def validate_resource_plane(path: Path, sheet_index: int, plane: str) -> List[str]:
    errors: List[str] = []
    try:
        df = pd.read_excel(path, sheet_name=sheet_index, header=0)
    except Exception as e:
        return [f"resource: cannot read sheet {sheet_index}: {e}"]
    if "网络平面" not in df.columns:
        errors.append("resource: column '网络平面' missing")
        return errors
    row = df[df["网络平面"].astype(str) == str(plane)]
    if row.empty:
        errors.append(f"resource: no row with 网络平面 == {plane!r}")
        return errors
    r = row.iloc[0]
    if "地址池*" not in df.columns:
        errors.append("resource: column '地址池*' missing")
    else:
        pool = str(r.get("地址池*", "")).strip()
        if not IP_POOL_PATTERN.match(pool):
            errors.append(f"resource: 地址池* format invalid: {pool!r}")
    mask_cols = [c for c in df.columns if "最小规划掩码" in str(c)]
    if not mask_cols:
        errors.append("resource: no column matching '最小规划掩码'")
    else:
        v = r[mask_cols[0]]
        if pd.isna(v):
            errors.append("resource: 最小规划掩码 is empty")
        else:
            try:
                int(v)
            except (TypeError, ValueError):
                errors.append(f"resource: 最小规划掩码 must be integer, got: {v!r}")
    if "网关地址*" not in df.columns:
        errors.append("resource: column '网关地址*' missing")
    if "VLAN*" not in df.columns:
        errors.append("resource: column 'VLAN*' missing")
    if errors:
        return errors
    print(f"resource: OK — sheet index={sheet_index}, 网络平面={plane!r}, 地址池*={r.get('地址池*', 'N/A')}")
    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Validate inputs for offline YBM pipeline")
    p.add_argument("--007", dest="path_007", default=None, type=Path)
    p.add_argument("--resource", default=None, type=Path)
    p.add_argument("--sheet007", default=SHEET_007_DEFAULT)
    p.add_argument("--sheet-res-index", "--sheet-resource", default=SHEET_RES_DEFAULT)
    p.add_argument("--network-plane", default="计算样本面", help="资源表中要匹配的网络平面名称")
    p.add_argument("--server-substring", default="AT800T", help="与主流程一致的服务器名过滤子串")
    p.add_argument(
        "--no-server-filter",
        action="store_true",
        help="禁用 007 首列服务器名过滤（等价于 --server-substring 空字符串）",
    )
    args = p.parse_args(argv)
    server_substring = "" if args.no_server_filter else (args.server_substring or "")

    try:
        if args.path_007 is None:
            args.path_007 = autodetect_007_in_cwd()
        args.path_007 = require_under_cwd(args.path_007, "007")
        if args.resource is None:
            args.resource = autodetect_resource_in_cwd()
        args.resource = require_under_cwd(args.resource, "resource")
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2

    all_err: List[str] = []
    all_err.extend(validate_007(args.path_007, args.sheet007, server_substring))
    all_err.extend(validate_resource_plane(args.resource, args.sheet_res_index, args.network_plane))
    if all_err:
        print("Validation failed:", file=sys.stderr)
        for e in all_err:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

