#!/usr/bin/env python3
"""校验 存储业务面端口互联 + 资源表。退出码 0/1/2。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    sys.exit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from cc_ywm_io import (  # noqa: E402
    GATEWAY_POSITION_COL,
    NET_PLANE,
    STORAGE_NAME_KEYWORD,
    classify_device_scenario,
    detect_cc_ywm_layer,
    get_node_info,
    resolve_connect_sheet,
)
from dw_manage_segment_rules import IP_POOL_PATTERN  # noqa: E402

SHEET_CONNECT_DEFAULT = "存储业务面端口互联"
SHEET_RES_DEFAULT = "网络资源需求表"
SHEET_RES_DEFAULT_INDEX = SHEET_RES_DEFAULT


def resolve_local_only(p: Path) -> Path:
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


def require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception:
        raise SystemExit(
            f"ERROR: {label} must be under cwd.\n  resolved: {resolved}\n  cwd: {cwd}"
        )
    return resolved


def _list_excel_files_in_cwd() -> List[Path]:
    cwd = Path.cwd().resolve()
    files: List[Path] = []
    for ext in (".xlsx", ".xls"):
        files.extend([p for p in cwd.rglob(f"*{ext}") if p.is_file() and not p.name.startswith("~$")])
    return list(dict.fromkeys(files))


def autodetect_connect() -> Path:
    for p in _list_excel_files_in_cwd():
        if ("007" in p.name) or ("端口连线" in p.name) or ("端口互联" in p.name):
            return p
    raise SystemExit("ERROR: cannot autodetect 端口互联 excel in cwd.")


def autodetect_resource() -> Path:
    for p in _list_excel_files_in_cwd():
        if ("项目信息收集" in p.name) or ("资源" in p.name):
            return p
    raise SystemExit("ERROR: cannot autodetect resource excel in cwd.")


def validate_connect(path: Path, sheet: object) -> List[str]:
    errors: List[str] = []
    try:
        resolved = resolve_connect_sheet(path, sheet)
        raw = pd.read_excel(path, sheet_name=resolved, header=None, dtype=str).fillna("")
    except Exception as e:
        return [f"connect: cannot read sheet: {e}"]
    try:
        from cc_ywm_io import find_header_row

        h = find_header_row(raw)
    except ValueError as e:
        return [f"connect: {e}"]
    data = raw.iloc[h + 1 :]
    if data.empty:
        return [f"connect: no data rows after header"]
    if data.shape[1] < 3:
        return ["connect: need >= 3 columns"]
    pattern = "|".join(map(re.escape, STORAGE_NAME_KEYWORD))
    storage_rows = data.iloc[:, 0].astype(str).str.contains(pattern, na=False).sum()
    if storage_rows == 0:
        errors.append(
            f"connect: no rows matching STORAGE_NAME_KEYWORD {STORAGE_NAME_KEYWORD}"
        )
    try:
        osp_df, osa800_df = get_node_info(path, sheet)
        scenario = classify_device_scenario(osp_df, osa800_df)
        print(
            f"connect: OK — sheet={resolved!r}, storage_rows={storage_rows}, "
            f"scenario={scenario}, osp_nodes={len(osp_df)}, osa800_rows={len(osa800_df)}"
        )
    except Exception as e:
        errors.append(f"connect device scenario: {e}")
    return errors


def validate_resource(path: Path, sheet_index: int) -> List[str]:
    errors: List[str] = []
    try:
        from cc_ywm_io import read_network_resource_df

        df = read_network_resource_df(path, sheet_index)
    except Exception as e:
        return [f"resource: {e}"]
    if "网络平面" not in df.columns:
        return ["resource: missing column 网络平面"]
    rows = df[df["网络平面"].astype(str) == NET_PLANE]
    if rows.empty:
        return [f"resource: no row 网络平面 == {NET_PLANE!r}"]
    r = rows.iloc[0]
    pool = str(r.get("地址池*", "")).strip()
    if not IP_POOL_PATTERN.match(pool):
        errors.append(f"resource: invalid 地址池*: {pool!r}")
    if not any("最小规划掩码" in str(c) for c in df.columns):
        errors.append("resource: no 最小规划掩码 column")
    if "网关地址*" not in df.columns:
        errors.append("resource: missing 网关地址*")
    if "VLAN*" not in df.columns:
        errors.append("resource: missing VLAN*")
    gw_col = GATEWAY_POSITION_COL if GATEWAY_POSITION_COL in df.columns else None
    if gw_col is None:
        alt = [c for c in df.columns if "网关位置" in str(c)]
        gw_col = alt[0] if alt else None
    if gw_col is None:
        errors.append("resource: missing 网关位置*")
    else:
        gw_val = str(r.get(gw_col, "")).strip()
        if not gw_val:
            errors.append(f"resource: {NET_PLANE!r} 的网关位置* 为空")
    if not errors:
        try:
            layer, gw_pos, rule = detect_cc_ywm_layer(path, sheet_index)
            print(
                f"resource: OK — 网络平面={NET_PLANE!r}, 地址池*={pool}, "
                f"网关位置*={gw_pos!r} → auto layer={layer}"
            )
            print(f"  detection: {rule}")
        except Exception as e:
            errors.append(f"resource layer detect: {e}")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Validate A3 存储业务面 IP inputs")
    p.add_argument("--connect", default=None, type=Path)
    p.add_argument("--resource", default=None, type=Path)
    p.add_argument("--sheet-connect", default=SHEET_CONNECT_DEFAULT)
    p.add_argument("--sheet-res-index", default=SHEET_RES_DEFAULT)
    args = p.parse_args()

    connect = require_under_cwd(args.connect or autodetect_connect(), "connect")
    resource = require_under_cwd(args.resource or autodetect_resource(), "resource")
    print(f"input.connect: {connect.name}")
    print(f"input.resource: {resource.name}")

    errs: List[str] = []
    errs.extend(validate_connect(connect, args.sheet_connect))
    errs.extend(validate_resource(resource, args.sheet_res_index))
    if errs:
        print("Validation failed:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
