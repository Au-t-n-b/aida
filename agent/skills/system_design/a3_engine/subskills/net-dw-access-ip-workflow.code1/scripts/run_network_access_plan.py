#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CLI for querying the standalone network device access plan workbook."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from net_dw_access_ip.access_plan import DEFAULT_ACCESS_PLAN_FILE, query_access_plan  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="离线查询 A3网络设备接入规划.xlsx，按项目 a3_network_access_plan.py 逻辑过滤结果。"
    )
    parser.add_argument(
        "--access-plan",
        default=DEFAULT_ACCESS_PLAN_FILE,
        help=f"已生成的网络设备接入规划文件，默认：{DEFAULT_ACCESS_PLAN_FILE}",
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--plan", help="接入规划名称，例如：计算业务面接入规划；也兼容 _L2/_L3 后缀。")
    selector.add_argument("--sheet", help="main_flow.py 中对应的 007 sheet，例如：计算业务面端口互联。")
    selector.add_argument("--plane", help="直接指定网络平面，例如：计算业务面。")
    parser.add_argument("--out", help="可选离线增强：将过滤结果写入单独 Excel 文件；项目函数仅展示原接入规划文件。")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = query_access_plan(
        access_plan_file=args.access_plan,
        plan_name=args.plan,
        sheet_name=args.sheet,
        plane=args.plane,
        output_file=args.out,
    )
    print(f"展示标题: {result.title}")
    print(f"接入规划 sheet: {result.sheet_name or '(direct-plane)'}")
    print(f"过滤网络平面: {result.network_plane}")
    print(f"匹配记录数: {len(result.result_df)}")
    if result.output_file:
        print(f"已生成过滤结果: {result.output_file}")
    print(result.reason)
    print(result.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
