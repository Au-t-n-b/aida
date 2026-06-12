#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CLI for the standalone switch MLAG planner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from switch_mlag_planning import (  # noqa: E402
    DEFAULT_OUTPUT_FILE,
    DEFAULT_RESOURCE_FILE,
    DEFAULT_TEMP_FILE,
    DEFAULT_TOPOLOGY_FILE,
    available_mlag_sheets,
    generate_switch_mlag,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="离线生成 A3交换机MLAG规划.xlsx，复刻项目 a3_switch_mlag.py 核心逻辑。"
    )
    parser.add_argument(
        "--topology",
        default=DEFAULT_TOPOLOGY_FILE,
        help=f"007 端口连线表，默认：{DEFAULT_TOPOLOGY_FILE}",
    )
    parser.add_argument(
        "--resource",
        default=DEFAULT_RESOURCE_FILE,
        help=f"项目信息收集表，默认：{DEFAULT_RESOURCE_FILE}",
    )
    parser.add_argument(
        "--out",
        help=(
            f"最终输出 Excel。未指定且传入 --user-id/--project-id 时使用项目同款命名；"
            f"否则默认：{DEFAULT_OUTPUT_FILE}"
        ),
    )
    parser.add_argument(
        "--temp",
        help=(
            f"未合并区域的中间 Excel。未指定且传入 --user-id/--project-id 时使用项目同款命名；"
            f"否则默认：{DEFAULT_TEMP_FILE}"
        ),
    )
    parser.add_argument(
        "--user-id",
        help="按项目输出模式生成文件名时使用，例如：user_id_交换机MLAG规划.xlsx。",
    )
    parser.add_argument(
        "--project-id",
        help="按项目输出模式生成文件名时使用，例如：user_id_project_id_A3交换机MLAG规划.xlsx。",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="按项目输出模式生成文件名时的输出目录，默认当前目录。",
    )
    parser.add_argument(
        "--sheet",
        action="append",
        dest="sheets",
        help="只处理指定 007 sheet；可重复传入。未指定时处理工作簿中所有支持的 sheet。",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="读取已有未合并结果，删除本次网络平面后追加新结果；默认整表重新生成。",
    )
    parser.add_argument(
        "--existing",
        help="--merge-existing 使用的已有结果文件；默认优先读取 --temp，缺失时读取 --out。",
    )
    parser.add_argument(
        "--list-sheets",
        action="store_true",
        help="列出当前 007 文件中可用于 MLAG 规划的 sheet 后退出。",
    )
    parser.add_argument(
        "--compat-composite-sheets",
        action="store_true",
        help="离线增强：自动扫描时兼容按 | 拆分组合 sheet；默认按项目入口只处理工作簿中与 WEB_NETWORK_TYPE_CONFIG 完全同名的 sheet。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_sheets:
        for sheet in available_mlag_sheets(
            args.topology, project_exact=not args.compat_composite_sheets
        ):
            print(sheet)
        return 0

    result = generate_switch_mlag(
        topology_file=args.topology,
        resource_file=args.resource,
        output_file=args.out,
        sheets=args.sheets,
        merge_existing=args.merge_existing,
        existing_file=args.existing,
        temp_file=args.temp,
        user_id=args.user_id,
        project_id=args.project_id,
        output_dir=args.output_dir,
        project_exact_sheets=not args.compat_composite_sheets,
    )
    print(f"已处理 sheet: {', '.join(result.processed_sheets)}")
    print(f"生成记录数: {len(result.result_df)}")
    for sheet, row_count in result.sheet_row_counts.items():
        print(f"  {sheet}: {row_count} 行")
    print(f"输出文件: {result.output_file}")
    if result.temp_file:
        print(f"未合并中间文件: {result.temp_file}")
    if result.used_project_filenames:
        print("输出命名: 项目同款 user_id/project_id 文件名")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
