#!/usr/bin/env python3
"""校验 参数面端口互联 + 资源表。退出码 0/1/2。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    sys.exit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from csm_io import (  # noqa: E402
    NET_PLANE,
    detect_csm_scenario,
    read_connectivity_raw,
    read_resource_row,
    resolve_connect_sheet,
)
from dw_manage_segment_rules import IP_POOL_PATTERN  # noqa: E402

SHEET_CONNECT_DEFAULT = "参数面端口互联"
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
        raise SystemExit(f"ERROR: {label} must be under cwd.\n  resolved: {resolved}\n  cwd: {cwd}")
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
        df = read_connectivity_raw(path, resolved)
    except Exception as e:
        return [f"connect: {e}"]
    if df.empty:
        errors.append("connect: 无数据行")
    if "计算服务器" not in df.columns:
        errors.append("connect: 缺少 计算服务器 列")
    return errors


def validate_resource(path: Path, sheet_index: int) -> List[str]:
    errors: List[str] = []
    try:
        row, pool = read_resource_row(path, sheet_index)
    except Exception as e:
        return [f"resource: {e}"]
    if not IP_POOL_PATTERN.match(str(pool).strip()):
        errors.append(f"resource: 地址池* 格式无效: {pool!r}")
    try:
        int(str(row.get("最小规划掩码", "")).strip().split(".")[0])
    except Exception:
        errors.append("resource: 最小规划掩码 无效")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--connect", type=Path, default=None)
    ap.add_argument("--resource", type=Path, default=None)
    ap.add_argument("--sheet-connect", default=SHEET_CONNECT_DEFAULT)
    ap.add_argument("--sheet-res-index", default=SHEET_RES_DEFAULT)
    args = ap.parse_args()

    connect = require_under_cwd(args.connect or autodetect_connect(), "connect")
    resource = require_under_cwd(args.resource or autodetect_resource(), "resource")

    errs: List[str] = []
    errs.extend(validate_connect(connect, args.sheet_connect))
    errs.extend(validate_resource(resource, args.sheet_res_index))
    try:
        scenario, kw, rule = detect_csm_scenario(connect, args.sheet_connect)
        print(f"OK scenario={scenario} keyword={kw}")
        print(f"  rule: {rule}")
    except Exception as e:
        errs.append(f"scenario: {e}")

    if errs:
        for e in errs:
            print(f"FAIL {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"OK 网络平面={NET_PLANE}")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
