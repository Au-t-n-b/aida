#!/usr/bin/env python3
"""Offline A3 device naming: five subcommands aligned with online secondary intents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from device_list_generator import generate_device_list
from lld_device_name_replacer import replace_lld_device_names
from naming_path_utils import (
    autodetect_device_list_in_cwd,
    autodetect_lld_in_cwd,
    autodetect_location_in_cwd,
    autodetect_mapping_in_cwd,
    autodetect_ztp_lld_in_cwd,
)
from ztp_device_name_replacer import replace_ztp_device_names

COMMANDS = [
    ("generate-list", "生成设备清单", None),
    ("replace-lld", "替换设备名称", None),
    ("replace-ztp", "ZTP名称替换", None),
    ("replace-ztp-l1", "ZTP名称替换_L1", 1),
    ("replace-ztp-l2", "ZTP名称替换_L2", 2),
]


def _print_list() -> None:
    print("Offline device naming commands (1:1 with online secondary intents):")
    for cli, online, plane in COMMANDS:
        plane_note = f" plane={plane}" if plane is not None else " plane=ALL"
        print(f"  {cli:18} <- {online}{plane_note}")


def cmd_generate_list(args: argparse.Namespace) -> int:
    loc = args.location or autodetect_location_in_cwd()
    out = generate_device_list(
        location_path=loc,
        sheet_name=args.sheet,
        out_dir=args.out_dir,
    )
    print(f"OK: wrote {out}")
    return 0


def cmd_replace_lld(args: argparse.Namespace) -> int:
    dev = args.device_list or autodetect_device_list_in_cwd()
    lld = args.lld or autodetect_lld_in_cwd()
    old_col, new_col = "设备名称", "客户定义设备名称"
    if args.mapping_cols:
        parts = [p.strip() for p in args.mapping_cols.split(",")]
        if len(parts) != 2:
            raise SystemExit("ERROR: --mapping-cols must be OLD,NEW")
        old_col, new_col = parts[0], parts[1]

    out, stats = replace_lld_device_names(
        device_list_path=dev,
        lld_path=lld,
        out_dir=args.out_dir,
        dry_run=args.dry_run,
        old_col=old_col,
        new_col=new_col,
    )
    if args.dry_run:
        print(
            f"DRY-RUN: mapping={stats.mapping_size} "
            f"scanned={stats.cells_scanned} would_replace={stats.cells_replaced}"
        )
        return 0
    print(f"OK: wrote {out} (replaced={stats.cells_replaced})")
    return 0


def _cmd_replace_ztp(args: argparse.Namespace, plane: Optional[int]) -> int:
    ztp = args.ztp_lld or autodetect_ztp_lld_in_cwd()
    mapping = args.mapping or autodetect_mapping_in_cwd()
    out, stats = replace_ztp_device_names(
        ztp_lld_path=ztp,
        mapping_path=mapping,
        plane=plane,
        out_dir=args.out_dir,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(
            f"DRY-RUN: plane={stats.plane_label} mapping={stats.mapping_size} "
            f"hit_sources={stats.hit_sources} replaced={stats.replaced} "
            f"missed_sources={stats.missed_sources} "
            f"filtered_rows={stats.filtered_rows if plane is not None else 'ALL'}"
        )
        return 0
    print(
        f"OK: wrote {out} plane={stats.plane_label} replaced={stats.replaced} "
        f"hit_sources={stats.hit_sources}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Offline A3 device naming workflow (5 subcommands)"
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List five commands and online intent names")

    g = sub.add_parser("generate-list", help="生成设备清单")
    g.add_argument("--location", type=Path, default=None)
    g.add_argument("--sheet", default="设备位置信息")
    g.add_argument("--out-dir", type=Path, default=Path("output"))
    g.set_defaults(handler=cmd_generate_list)

    r = sub.add_parser("replace-lld", help="替换设备名称")
    r.add_argument("--device-list", type=Path, default=None)
    r.add_argument("--lld", type=Path, default=None)
    r.add_argument("--out-dir", type=Path, default=Path("output"))
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--mapping-cols", default=None, help="OLD,NEW column names")
    r.set_defaults(handler=cmd_replace_lld)

    for name, plane in (
        ("replace-ztp", None),
        ("replace-ztp-l1", 1),
        ("replace-ztp-l2", 2),
    ):
        z = sub.add_parser(name, help=f"ZTP名称替换{'_L'+str(plane) if plane else ''}")
        z.add_argument("--ztp-lld", type=Path, default=None)
        z.add_argument("--mapping", type=Path, default=None)
        z.add_argument("--out-dir", type=Path, default=Path("output"))
        z.add_argument("--dry-run", action="store_true")
        z.set_defaults(handler=lambda a, pl=plane: _cmd_replace_ztp(a, pl))

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        _print_list()
        return 0
    try:
        return args.handler(args)
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
