#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""007 + 项目信息收集表（网络资源需求表）→ output/run_*/A3网络互联规划.xlsx（确定性，无 LLM / EDM）。

默认按资源表「网关位置*」自动选 L2（SPINE）或 L3（LEAF）；亦可显式指定 --mode + --sheet。
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from net_interconnect_rules import (
    allocate_connection,
    allocate_ips,
    find_working_007_sheet,
    gateway_column_name,
    get_switch_data_l2,
    get_switch_data_l3,
    merge_interconnect_output,
    read_plane_row_from_resource_df,
    read_resource_interconnect_segment,
    read_resource_vlan,
    resolve_gateway_mode,
    resolve_keyword_network_from_plane,
    resolve_sheet_config,
    validate_network_range,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SHEET_RESOURCE_DEFAULT = "网络资源需求表"
OUTPUT_SHEET_NAME = "网络互联规划"
OUTPUT_FILENAME = "A3网络互联规划.xlsx"


def _resolve_local_only(p: Path) -> Path:
    if p.is_absolute():
        return p
    return (Path.cwd() / p).resolve()


def _require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = _resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception:
        raise SystemExit(
            f"ERROR: {label} must be under cwd.\n  resolved: {resolved}\n  cwd: {cwd}"
        )
    return resolved


def _detect_007() -> Optional[Path]:
    cwd = Path.cwd().resolve()
    for p in sorted(cwd.rglob("*.xlsx")):
        if p.name.startswith("~$"):
            continue
        n = p.name
        if "007" in n or "端口连线" in n or "端口互联" in n:
            return p
    return None


def _detect_resource() -> Optional[Path]:
    cwd = Path.cwd().resolve()
    for p in sorted(cwd.rglob("*.xlsx")):
        if p.name.startswith("~$"):
            continue
        n = p.name
        if "项目信息收集" in n or "信息收集表" in n or "资源" in n:
            return p
    return None


def _detect_resource_prefer_project_info() -> Optional[Path]:
    """优先同目录下的「项目信息收集表.xlsx」。"""
    cwd = Path.cwd().resolve()
    exact = cwd / "项目信息收集表.xlsx"
    if exact.is_file():
        return exact
    return _detect_resource()


def _read_007(path: Path, sheet: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=sheet, header=None)
    except Exception:
        xl = pd.ExcelFile(path)
        if sheet in xl.sheet_names:
            return pd.read_excel(path, sheet_name=sheet, header=None)
        raise SystemExit(f"ERROR: sheet {sheet!r} not in {path}. Available: {xl.sheet_names}")


def _load_merge_base(path: Optional[Path]) -> pd.DataFrame:
    if not path or not path.exists():
        return pd.DataFrame()
    return pd.read_excel(path, sheet_name=0, header=0)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="A3 计算侧 Leaf–Spine 网络互联规划：按资源表网关位置自动 L2/L3，或显式 --mode"
    )
    ap.add_argument(
        "--plane",
        type=str,
        help="网络平面（与「网络资源需求表」第一列一致，如 计算样本面）；指定后根据该行「网关位置*」选 L2(SPINE)/L3(LEAF)，只生成一份结果",
    )
    ap.add_argument(
        "--mode",
        choices=("l2", "l3"),
        help="显式 L2/L3（需与 --sheet 同时使用；与 --plane 互斥）",
    )
    ap.add_argument("--007", dest="path_007", type=Path, help="007 端口连线表 xlsx（省略则 cwd 自动探测）")
    ap.add_argument("--resource", type=Path, help="项目信息收集表 xlsx（--plane 时默认优先 cwd/项目信息收集表.xlsx）")
    ap.add_argument(
        "--sheet",
        type=str,
        help="007 中 sheet 名（仅在与 --mode 同时指定时使用）",
    )
    ap.add_argument("--resource-sheet", type=str, default=SHEET_RESOURCE_DEFAULT)
    ap.add_argument("--out-dir", type=Path, default=Path("output"), help="输出根目录（须在 cwd 下）")
    ap.add_argument(
        "--merge-from",
        type=Path,
        help="已有 A3网络互联规划.xlsx：先删除同网络平面行再与新结果合并",
    )
    args = ap.parse_args(argv)

    path_007 = args.path_007
    if not path_007:
        path_007 = _detect_007()
    if not path_007:
        raise SystemExit("ERROR: 请指定 --007 或在 cwd 下放可自动探测的 007 端口连线表")
    path_007 = _require_under_cwd(Path(path_007), "--007")

    resource = args.resource
    if not resource:
        if args.plane:
            resource = _detect_resource_prefer_project_info()
        else:
            resource = _detect_resource()
    if not resource:
        raise SystemExit("ERROR: 请指定 --resource 或在 cwd 下放项目信息收集表等资源 xlsx")
    resource = _require_under_cwd(Path(resource), "--resource")

    out_root = _require_under_cwd(Path(args.out_dir), "--out-dir")
    run_dir = out_root  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)
    out_file = run_dir / OUTPUT_FILENAME

    old_df = _load_merge_base(args.merge_from)

    if args.plane:
        df_res = pd.read_excel(str(resource), sheet_name=args.resource_sheet, header=0)
        row = read_plane_row_from_resource_df(df_res, args.plane)
        gw_col = gateway_column_name(df_res)
        mode = resolve_gateway_mode(row[gw_col])
        keyword, network_type = resolve_keyword_network_from_plane(args.plane)
        df_raw, sheet_007 = find_working_007_sheet(path_007, mode, keyword, network_type)
        logger.info(
            "网络平面=%s 网关位置(%s)=%s -> %s；007 sheet=%s",
            network_type,
            gw_col,
            row[gw_col],
            mode.upper(),
            sheet_007,
        )
    else:
        if not args.mode or not args.sheet:
            raise SystemExit("ERROR: 请指定 --plane（推荐），或同时指定 --mode 与 --sheet")
        mode = args.mode
        keyword, network_type = resolve_sheet_config(args.sheet)
        df_raw = _read_007(path_007, args.sheet)
        sheet_007 = args.sheet
        logger.info("显式模式 %s；007 sheet=%s；网络平面=%s", mode.upper(), sheet_007, network_type)

    if mode == "l2":
        csm_df, _n = get_switch_data_l2(df_raw, keyword)
        vlan = read_resource_vlan(str(resource), network_type, args.resource_sheet)
        result_df = allocate_connection(csm_df, vlan, network_type)
    else:
        csm_df, n = get_switch_data_l3(df_raw, keyword)
        seg = read_resource_interconnect_segment(str(resource), network_type, args.resource_sheet)
        validate_network_range(seg, n)
        result_df = allocate_ips(csm_df, seg, network_type)

    merged = merge_interconnect_output(old_df, result_df, network_type)
    merged.to_excel(out_file, sheet_name=OUTPUT_SHEET_NAME, index=False)
    logger.info("已写入 %s （行数 %s）", out_file, len(merged))
    print(str(out_file.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
