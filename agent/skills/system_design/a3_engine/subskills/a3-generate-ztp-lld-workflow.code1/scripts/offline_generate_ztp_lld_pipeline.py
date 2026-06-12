#!/usr/bin/env python3
"""Offline: 超平面规划 + 灵衢带外管理地址 + 设备位置 → ZTP_LLD.xlsx。

业务来源：generate_ztp_lld.generate_ztp_lld_file
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from prerequisite_runner import PrereqSession, resolved_inputs  # noqa: E402
from ztp_lld_inputs import LABELS, SCAN_RULES, find_excel  # noqa: E402
from ztp_lld_rules import (  # noqa: E402
    OUTPUT_FILENAME,
    generate_ztp_lld_dataframe,
    read_inputs,
    write_ztp_lld_excel,
)


def _resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def discover_inputs(
    scan_dir: Path,
    *,
    allow_auto_prereq: bool = True,
    session: PrereqSession | None = None,
) -> dict[str, Path]:
    """扫描输入；缺失规划表时可自动运行前置 skill。"""
    if allow_auto_prereq:
        if session is None:
            raise ValueError("allow_auto_prereq 需要传入 PrereqSession")
        from prerequisite_runner import resolve_all_inputs

        return resolve_all_inputs(
            scan_dir, _SKILL_ROOT, session, allow_auto_prereq=True
        )

    found: dict[str, Path] = {}
    missing: list[str] = []
    for key in SCAN_RULES:
        path = find_excel(key, scan_dir)
        if path:
            found[key] = path.resolve()
        else:
            missing.append(LABELS[key])
    if missing:
        raise FileNotFoundError(f"未找到必要输入件：{', '.join(missing)}")
    return found


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="离线生成 ZTP 设计文件（ZTP_LLD.xlsx）")
    p.add_argument("--cpm", help="A3超平面网络规划.xlsx")
    p.add_argument("--manage", help="A3灵衢带外管理地址规划.xlsx")
    p.add_argument("--location", help="设备位置信息表（004）")
    p.add_argument("--location-sheet", default="设备位置信息")
    p.add_argument("--scan-dir", help="自动扫描输入目录，默认 cwd")
    p.add_argument("--out-dir", default="output")
    p.add_argument(
        "--no-auto-prereq",
        action="store_true",
        help="缺失规划表时不自动运行 _skill_staging 中的前置 skill",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    scan_dir = Path(args.scan_dir) if args.scan_dir else Path.cwd()
    allow_auto = not args.no_auto_prereq

    if args.cpm and args.manage and args.location:
        paths = {
            "cpm": _resolve(Path(args.cpm)),
            "manage": _resolve(Path(args.manage)),
            "location": _resolve(Path(args.location)),
        }
        df_location, df_loopback, df_manage = read_inputs(
            paths["location"],
            paths["cpm"],
            paths["manage"],
            location_sheet=args.location_sheet,
        )
        merged = generate_ztp_lld_dataframe(df_location, df_loopback, df_manage)
        run_dir = (Path(args.out_dir) / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}").resolve()
        out_file = write_ztp_lld_excel(merged, run_dir / OUTPUT_FILENAME)
        print(f"已生成: {out_file}")
        print(f"sheet: 网络IP规划, 行数: {len(merged)}")
        return

    if allow_auto:
        with resolved_inputs(scan_dir.resolve(), _SKILL_ROOT, allow_auto_prereq=True) as paths:
            df_location, df_loopback, df_manage = read_inputs(
                paths["location"],
                paths["cpm"],
                paths["manage"],
                location_sheet=args.location_sheet,
            )
            merged = generate_ztp_lld_dataframe(df_location, df_loopback, df_manage)
    else:
        paths = discover_inputs(scan_dir.resolve(), allow_auto_prereq=False)
        df_location, df_loopback, df_manage = read_inputs(
            paths["location"],
            paths["cpm"],
            paths["manage"],
            location_sheet=args.location_sheet,
        )
        merged = generate_ztp_lld_dataframe(df_location, df_loopback, df_manage)

    run_dir = (Path(args.out_dir) / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}").resolve()
    out_file = write_ztp_lld_excel(merged, run_dir / OUTPUT_FILENAME)

    print(f"已生成: {out_file}")
    print(f"sheet: 网络IP规划, 行数: {len(merged)}")


if __name__ == "__main__":
    main()
