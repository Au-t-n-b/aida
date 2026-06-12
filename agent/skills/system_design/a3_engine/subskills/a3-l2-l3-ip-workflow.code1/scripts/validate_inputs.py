#!/usr/bin/env python3
"""Validate A3 L2/L3 gateway IP planning inputs."""

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

from a3_l2_l3_ip_rules import FILE_NETWORK_TYPE_CONFIG, SERVER_NAME_KEYWORD, SHEET_DEFAULT, find_header_row

RESOURCE_SHEET_DEFAULT = "网络资源需求表"


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
        errors.append("007: no data rows after '设备命名'")
        return errors
    if data.shape[1] < 2:
        errors.append("007: need at least 2 columns")
        return errors

    first_col = data.iloc[:, 0].astype(str)
    last_col = data.iloc[:, -1].astype(str)
    server_count = int(first_col.str.contains(SERVER_NAME_KEYWORD, case=False, regex=True, na=False).sum())
    leaf_count = int(last_col.str.contains("leaf", case=False, na=False).sum())
    spine_count = int(last_col.str.contains("spine|HXHJ-CSW", case=False, regex=True, na=False).sum())
    if server_count == 0:
        errors.append("007: no server rows matched SERVER_NAME_KEYWORD")

    print(
        f"007: sheet={sheet!r}, header_row_idx={header_idx}, "
        f"server_rows={server_count}, leaf_refs={leaf_count}, spine_refs={spine_count}"
    )
    return errors


def validate_resource(resource: Path, sheet: object, network_type: str) -> list[str]:
    errors: list[str] = []
    try:
        df = pd.read_excel(resource, sheet_name=sheet, header=0)
    except Exception as exc:
        return [f"resource: cannot read sheet {sheet!r}: {exc}"]

    if "网络平面" not in df.columns:
        return ["resource: missing column '网络平面'"]

    plane = FILE_NETWORK_TYPE_CONFIG.get(network_type, network_type)
    rows = df[df["网络平面"].astype(str) == plane]
    if rows.empty:
        return [f"resource: no row where 网络平面 == {plane!r}"]

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

    print(
        f"resource: 网络平面={plane!r}, 地址池*={ip_pool!r}, 掩码={mask!r}, "
        f"网关位置={gateway_location!r}, 网关={gateway!r}, VLAN={vlan!r}"
    )
    return errors


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate A3 计算管理面 L2/L3 gateway IP planning inputs")
    parser.add_argument("--007", dest="path_007", required=True, type=Path, help="007 端口连线表")
    parser.add_argument("--resource", required=True, type=Path, help="项目信息收集表/网络资源需求表")
    parser.add_argument("--sheet", default="计算管理面端口互联", help="端口互联 sheet 名")
    parser.add_argument(
        "--resource-sheet",
        default=RESOURCE_SHEET_DEFAULT,
        help=f"资源表 sheet，默认 {RESOURCE_SHEET_DEFAULT!r}",
    )
    args = parser.parse_args(argv)

    errors: list[str] = []
    errors.extend(validate_007(args.path_007, _sheet_arg(args.sheet)))
    errors.extend(validate_resource(args.resource, _sheet_arg(args.resource_sheet), args.sheet))

    if errors:
        print("Validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
