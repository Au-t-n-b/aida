#!/usr/bin/env python3
"""校验端口互联表 + 资源表（L2/L3 互联规划）。退出码 0/1/2。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required.", file=sys.stderr)
    sys.exit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ni_io import (  # noqa: E402
    INTERCONNECT_POOL_COL,
    INTERCONNECTION_INTENTS,
    LEAF_SPINE_CONFIG,
    VLAN_COL,
    detect_ni_layer,
    get_switch_data_l2,
    get_switch_data_l3,
    read_connect_raw,
    read_interconnect_pool_for_plane,
    read_vlan_for_plane,
    resolve_connect_sheet,
    resolve_intent,
)

IP_POOL_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
)


def resolve_local_only(p: Path) -> Path:
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intent", required=True)
    parser.add_argument("--connect", type=Path)
    parser.add_argument("--resource", type=Path)
    parser.add_argument("--sheet-connect", default="auto")
    parser.add_argument("--sheet-res-index", type=int, default=0)
    parser.add_argument("--force-layer", choices=["L2", "L3"], default=None)
    args = parser.parse_args()

    errors: List[str] = []
    warnings: List[str] = []

    try:
        _, sheet_key, network_type = resolve_intent(args.intent)
        keyword = LEAF_SPINE_CONFIG[sheet_key]["keyword"]
    except Exception as e:
        print(f"FAIL intent: {e}")
        sys.exit(1)

    if not args.connect or not args.resource:
        print("FAIL: --connect and --resource required")
        sys.exit(1)

    connect = resolve_local_only(args.connect)
    resource = resolve_local_only(args.resource)
    raw = None
    layer = "L3"

    try:
        sheet = resolve_connect_sheet(connect, sheet_key, args.sheet_connect)
        raw = read_connect_raw(connect, sheet)
    except Exception as e:
        errors.append(f"connect: {e}")

    try:
        if args.force_layer:
            layer = args.force_layer
        else:
            layer, gw, _ = detect_ni_layer(resource, network_type, args.sheet_res_index)
            print(f"detected layer={layer} gateway={gw}")
    except Exception as e:
        errors.append(f"layer: {e}")

    if not errors and raw is not None:
        try:
            if layer == "L3":
                df, n = get_switch_data_l3(raw, keyword)
                pool = read_interconnect_pool_for_plane(
                    resource, network_type, args.sheet_res_index
                )
                if len(pool) != 2 or not IP_POOL_PATTERN.match(
                    f"{pool[0].strip()}-{pool[1].strip()}"
                ):
                    errors.append(f"L3: invalid {INTERCONNECT_POOL_COL}: {pool}")
                else:
                    print(f"L3 links={n} pool={pool[0]}-{pool[1]}")
            else:
                df, n = get_switch_data_l2(raw, keyword)
                vlan = read_vlan_for_plane(resource, network_type, args.sheet_res_index)
                print(f"L2 links={n} vlan={vlan}")
        except Exception as e:
            errors.append(f"data: {e}")

    if errors:
        print("FAIL:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    if warnings:
        for w in warnings:
            print(f"WARN: {w}")
    print("OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
