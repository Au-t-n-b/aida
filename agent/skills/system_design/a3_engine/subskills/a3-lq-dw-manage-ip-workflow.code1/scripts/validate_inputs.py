#!/usr/bin/env python3
"""Validate inputs for A3 灵衢带外管理地址规划 offline pipeline."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lq_dw_manage_rules import NET_PLANE_RESOURCE, SHEET_DEFAULT, count_lq_by_leaf, find_header_row, read_structured_007

IP_POOL_PATTERN = re.compile(
    r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\s*-\s*\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
)
GATEWAY_PATTERN = re.compile(r"^(网段起始位|网段结束位|\d{1,3}(?:\.\d{1,3}){3})$")
VLAN_PATTERN = re.compile(r"^\d+(?:\s*-\s*\d+)?$")


def _sheet_arg(value: str) -> object:
    value = str(value).strip()
    return int(value) if value.isdigit() else value


def validate_007(path_007: Path, sheet: object) -> list[str]:
    errors: list[str] = []
    try:
        df = pd.read_excel(path_007, sheet_name=sheet, header=None, dtype=str).fillna("")
    except Exception as exc:
        return [f"007: cannot read sheet {sheet!r}: {exc}"]

    try:
        header_idx = find_header_row(df, "设备命名")
    except Exception as exc:
        return [f"007: {exc}"]

    data = df.iloc[header_idx + 1 :]
    if data.empty:
        return ["007: no data rows after '设备命名'"]
    if data.shape[1] < 2:
        return ["007: need at least 2 columns (网络设备, 接入交换机)"]

    try:
        structured = read_structured_007(str(path_007), sheet)
        for col in ("起始端信息-设备命名", "起始端信息-接口信息"):
            if col not in structured.columns:
                errors.append(f"007: structured data missing column {col!r}")
        leaf_counts = count_lq_by_leaf(str(path_007), sheet)
        if leaf_counts.empty:
            errors.append("007: no LQ rows matched -sp数字- and LEAF")
        else:
            print("007: leaf/node counts:")
            print(leaf_counts.to_string(index=False))
    except Exception as exc:
        errors.append(f"007: structured read failed: {exc}")

    print(f"007: sheet={sheet!r}, header_row_idx={header_idx}, data_rows={len(data)}")
    return errors


def validate_resource(resource: Path, sheet: object, net_plane: str) -> list[str]:
    errors: list[str] = []
    try:
        df = pd.read_excel(resource, sheet_name=sheet, header=0)
    except Exception as exc:
        return [f"resource: cannot read sheet {sheet!r}: {exc}"]

    if "网络平面" not in df.columns:
        return ["resource: missing column '网络平面'"]

    plane_series = df["网络平面"].astype(str).str.strip()
    rows = df[plane_series == net_plane]
    if rows.empty:
        return [f"resource: no row where 网络平面 == {net_plane!r}"]

    row = rows.iloc[0]
    for col in ("地址池*", "网关地址*", "VLAN*"):
        if col not in df.columns:
            errors.append(f"resource: missing column {col!r}")
    mask_cols = [c for c in df.columns if "最小规划掩码" in str(c)]
    gateway_location_cols = [c for c in df.columns if "网关位置" in str(c)]
    if not mask_cols:
        errors.append("resource: missing column containing '最小规划掩码'")
    if not gateway_location_cols:
        errors.append("resource: missing column containing '网关位置'")
    if errors:
        return errors

    ip_pool = str(row["地址池*"]).strip()
    gateway = str(row["网关地址*"]).strip()
    vlan = str(row["VLAN*"]).strip()
    mask = str(row[mask_cols[0]]).strip()
    gateway_location = str(row[gateway_location_cols[0]]).strip().upper()
    if not IP_POOL_PATTERN.match(ip_pool):
        errors.append(f"resource: 地址池* must be 'A.B.C.D-E.F.G.H', got {ip_pool!r}")
    if gateway_location not in {"SPINE", "LEAF"}:
        errors.append(f"resource: 网关位置* must be SPINE or LEAF, got {gateway_location!r}")
    if not GATEWAY_PATTERN.match(gateway):
        errors.append(f"resource: 网关地址* invalid: {gateway!r}")
    if not VLAN_PATTERN.match(vlan):
        errors.append(f"resource: VLAN* invalid: {vlan!r}")
    try:
        mask_int = int(mask)
        if not 1 <= mask_int <= 32:
            errors.append(f"resource: 最小规划掩码 out of range: {mask!r}")
    except Exception:
        errors.append(f"resource: 最小规划掩码 must be integer, got {mask!r}")

    resolved_mode = "L2" if gateway_location == "SPINE" else "L3"
    print(
        f"resource: 网络平面={row['网络平面']!r}, 地址池*={ip_pool!r}, 掩码={mask!r}, "
        f"网关位置={gateway_location!r} -> {resolved_mode}, 网关={gateway!r}, VLAN={vlan!r}"
    )
    return errors


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate A3 灵衢带外管理地址规划 inputs")
    parser.add_argument("--007", dest="path_007", required=True, type=Path, help="007 端口连线表")
    parser.add_argument("--resource", required=True, type=Path, help="项目信息收集表")
    parser.add_argument("--sheet", default=SHEET_DEFAULT, help="007 sheet 名")
    parser.add_argument("--resource-sheet", default="网络资源需求表", help="资源表 sheet")
    parser.add_argument("--net-plane", default=NET_PLANE_RESOURCE, help="网络平面行名")
    args = parser.parse_args(argv)

    errors: list[str] = []
    errors.extend(validate_007(args.path_007, _sheet_arg(args.sheet)))
    errors.extend(validate_resource(args.resource, _sheet_arg(args.resource_sheet), args.net_plane))

    if errors:
        print("Validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
