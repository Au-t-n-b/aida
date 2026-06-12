#!/usr/bin/env python3
"""Validate 007 topology and resource workbook before LLD workflow plan."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

try:
    import pandas as pd
except ImportError:
    print("ERROR: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2) from None

from lld_path_utils import autodetect_resource, autodetect_topology, require_under_cwd, resolve_local


def validate_topology(path: Path) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        xls = pd.ExcelFile(path)
    except Exception as exc:
        return [f"无法打开 007: {exc}"]
    if not xls.sheet_names:
        errors.append("007 无任何 sheet")
    else:
        warnings.append(f"007 sheets ({len(xls.sheet_names)}): {', '.join(xls.sheet_names[:8])}...")
    return errors + [f"WARN: {w}" for w in warnings]


def validate_resource(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        xls = pd.ExcelFile(path)
    except Exception as exc:
        return [f"无法打开资源表: {exc}"]
    found_plane = False
    for name in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=name, nrows=5)
        if "网络平面" in df.columns:
            found_plane = True
            break
    if not found_plane:
        errors.append("资源表未找到含「网络平面」列的 sheet")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LLD workflow inputs")
    parser.add_argument("--topology", type=Path, help="007 端口连线表")
    parser.add_argument("--resource", type=Path, help="项目信息收集表")
    args = parser.parse_args()
    cwd = Path.cwd().resolve()

    topo = require_under_cwd(args.topology, cwd, "topology") if args.topology else autodetect_topology(cwd)
    res = require_under_cwd(args.resource, cwd, "resource") if args.resource else autodetect_resource(cwd)

    if not topo or not topo.is_file():
        print("ERROR: topology file not found", file=sys.stderr)
        return 2
    if not res or not res.is_file():
        print("ERROR: resource file not found", file=sys.stderr)
        return 2

    topo = resolve_local(topo, cwd)
    res = resolve_local(res, cwd)

    issues: list[str] = []
    issues.extend(validate_topology(topo))
    issues.extend(validate_resource(res))

    hard = [i for i in issues if not i.startswith("WARN:")]
    for line in issues:
        print(line)

    if hard:
        return 1
    print(f"OK: topology={topo.name} resource={res.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
