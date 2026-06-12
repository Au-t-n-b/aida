#!/usr/bin/env python3
"""校验端口互联 + 资源表是否满足 ASN 规划。退出码 0/1/2。"""

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

from switch_asn_io import LOOPBACK_SHEET_ORDER, detect_plane_plans  # noqa: E402

SHEET_RES_DEFAULT_INDEX = 0


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


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate inputs for 网络设备ASN规划 skill")
    ap.add_argument("--connect", type=Path, default=None)
    ap.add_argument("--resource", type=Path, default=None)
    ap.add_argument("--sheet-res-index", type=int, default=SHEET_RES_DEFAULT_INDEX)
    ap.add_argument("--only-plane", default=None)
    args = ap.parse_args()

    connect = require_under_cwd(args.connect or autodetect_connect(), "connect")
    resource = require_under_cwd(args.resource or autodetect_resource(), "resource")

    only_key = args.only_plane.strip() if args.only_plane else None
    if only_key and only_key not in LOOPBACK_SHEET_ORDER:
        print(f"ERROR: --only-plane 无效，可选: {LOOPBACK_SHEET_ORDER}", file=sys.stderr)
        raise SystemExit(1)

    plans, skipped, override_notes = detect_plane_plans(
        connect, resource, sheet_res_index=args.sheet_res_index, only_config_key=only_key
    )
    errors: List[str] = []
    if not plans:
        errors.append("未识别到可执行平面（需端口 sheet + 资源表 EBGP AS规划 含 '-'）")

    print(f"connect: {connect}")
    print(f"resource: {resource}")
    print(f"planes_ok: {[p.config_key for p in plans]}")
    if override_notes:
        print("override_notes:")
        for line in override_notes:
            print(f"  - {line}")
    if skipped:
        print("skipped:")
        for line in skipped:
            print(f"  - {line}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    print("OK")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
