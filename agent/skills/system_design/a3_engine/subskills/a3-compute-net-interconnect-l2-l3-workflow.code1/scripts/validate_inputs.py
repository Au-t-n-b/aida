#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选：校验输入（不写入结果）。支持 --plane 自动网关模式或 --mode + --sheet 显式模式。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

try:
    import pandas as pd
except ImportError:
    print("ERROR: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from net_interconnect_rules import (
    LEAF_SPINE_COMPUTE_PLANES,
    find_working_007_sheet,
    gateway_column_name,
    get_switch_data_l2,
    get_switch_data_l3,
    read_plane_row_from_resource_df,
    read_resource_interconnect_segment,
    read_resource_vlan,
    resolve_gateway_mode,
    resolve_keyword_network_from_plane,
    resolve_sheet_config,
    validate_network_range,
)


def _read_007(path: Path, sheet: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet, header=None)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--007", dest="path_007", type=Path, required=True)
    ap.add_argument("--resource", type=Path, required=True)
    ap.add_argument("--resource-sheet", type=str, default="网络资源需求表")
    ap.add_argument("--plane", type=str, help="网络平面（资源表第一列）；与 --mode/--sheet 二选一")
    ap.add_argument("--mode", choices=("l2", "l3"), help="显式 L2/L3（需同时 --sheet）")
    ap.add_argument("--sheet", type=str, help="007 sheet 名（与 --mode 同时使用）")
    args = ap.parse_args(argv)

    if args.plane:
        df_res = pd.read_excel(str(args.resource), sheet_name=args.resource_sheet, header=0)
        row = read_plane_row_from_resource_df(df_res, args.plane)
        gw_col = gateway_column_name(df_res)
        mode = resolve_gateway_mode(row[gw_col])
        keyword, network_type = resolve_keyword_network_from_plane(args.plane)
        df_raw, sheet = find_working_007_sheet(Path(args.path_007), mode, keyword, network_type)
        if mode == "l2":
            _df, n = get_switch_data_l2(df_raw, keyword)
            read_resource_vlan(str(args.resource), network_type, args.resource_sheet)
            print(
                f"OK plane={args.plane} gateway={row[gw_col]!r}->{mode} sheet007={sheet!r} "
                f"L2 rows={n} VLAN ok"
            )
        else:
            _df, n = get_switch_data_l3(df_raw, keyword)
            seg = read_resource_interconnect_segment(
                str(args.resource), network_type, args.resource_sheet
            )
            validate_network_range(seg, n)
            print(
                f"OK plane={args.plane} gateway={row[gw_col]!r}->{mode} sheet007={sheet!r} "
                f"L3 rows={n} segment={seg}"
            )
        return 0

    if not args.mode or not args.sheet:
        print("FAIL: 请指定 --plane，或同时指定 --mode 与 --sheet", file=sys.stderr)
        return 1

    if args.sheet not in LEAF_SPINE_COMPUTE_PLANES:
        print(f"FAIL: sheet not in supported list: {list(LEAF_SPINE_COMPUTE_PLANES)}", file=sys.stderr)
        return 1

    keyword, network_type = resolve_sheet_config(args.sheet)
    df_raw = _read_007(Path(args.path_007), args.sheet)

    if args.mode == "l2":
        _df, n = get_switch_data_l2(df_raw, keyword)
        read_resource_vlan(str(args.resource), network_type, args.resource_sheet)
        print(f"OK l2: {n} leaf-spine rows, VLAN row present for {network_type}")
    else:
        _df, n = get_switch_data_l3(df_raw, keyword)
        seg = read_resource_interconnect_segment(str(args.resource), network_type, args.resource_sheet)
        validate_network_range(seg, n)
        print(f"OK l3: {n} leaf-spine rows, segment ok for {network_type}: {seg}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
