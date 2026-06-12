#!/usr/bin/env python3
"""校验 CCAE 离线规划输入。退出码 0=通过，1=业务错误，2=依赖缺失。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from ccae_planner import PlannerInputs, validate_inputs
except ImportError:
    print("ERROR: pandas/openpyxl required. pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

from ccae_topology_parser import DEFAULT_SHEET
from run_ccae_planner import _auto_resource, _auto_topology, _require_under_cwd


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topology", type=Path)
    parser.add_argument("--resource", type=Path)
    parser.add_argument("--mlag-list", type=Path)
    parser.add_argument("--sheet", default=DEFAULT_SHEET)
    parser.add_argument("--resource-sheet-index", type=int, default=0)
    args = parser.parse_args(argv)

    try:
        topo = _require_under_cwd(args.topology or _auto_topology(), "topology")
        resource = _require_under_cwd(args.resource or _auto_resource(), "resource")
        mlag = (
            str(_require_under_cwd(args.mlag_list, "mlag-list"))
            if args.mlag_list
            else None
        )
        validate_inputs(
            PlannerInputs(
                topology_path=str(topo),
                resource_path=str(resource),
                sheet_topology=args.sheet,
                resource_sheet_index=args.resource_sheet_index,
                mlag_list_path=mlag,
            )
        )
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("OK: inputs valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
