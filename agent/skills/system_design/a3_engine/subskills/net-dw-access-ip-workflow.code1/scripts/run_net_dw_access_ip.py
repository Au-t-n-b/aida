#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CLI for the standalone network out-of-band management IP planning skill."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from net_dw_access_ip import run_from_files  # noqa: E402
from net_dw_access_ip.planner import (  # noqa: E402
    DEFAULT_INTERMEDIATE_FILE,
    DEFAULT_OUTPUT_FILE,
    DEFAULT_RESOURCE_PLANE,
    DEFAULT_SHEET_NAME,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="离线生成 A3 网络带外管理地址规划表，不依赖 CPCIA_AGENT 项目服务。"
    )
    parser.add_argument("--topology", required=True, help="建模仿真输出文档007-端口连线表.xlsx")
    parser.add_argument("--resource", required=True, help="项目信息收集表.xlsx")
    parser.add_argument("--sheet", default=DEFAULT_SHEET_NAME, help=f"007 页签，默认：{DEFAULT_SHEET_NAME}")
    parser.add_argument("--plane", default=DEFAULT_RESOURCE_PLANE, help=f"资源表网络平面，默认：{DEFAULT_RESOURCE_PLANE}")
    parser.add_argument("--out", default=DEFAULT_OUTPUT_FILE, help=f"输出文件，默认：{DEFAULT_OUTPUT_FILE}")
    parser.add_argument(
        "--intermediate",
        default=DEFAULT_INTERMEDIATE_FILE,
        help=f"网关中间结果文件，默认：{DEFAULT_INTERMEDIATE_FILE}",
    )
    parser.add_argument(
        "--no-intermediate",
        action="store_true",
        help="不生成网关中间结果文件。",
    )
    parser.add_argument(
        "--leaf-scope",
        choices=["global", "segment"],
        default="global",
        help="LEAF 虚拟 vlanif 地址分配范围；global 复刻源文件全局追加行为，segment 仅追加本网段 LEAF。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_from_files(
        topology_file=args.topology,
        resource_file=args.resource,
        sheet_name=args.sheet,
        resource_plane=args.plane,
        output_file=args.out,
        intermediate_file=None if args.no_intermediate else args.intermediate,
        leaf_scope=args.leaf_scope,
    )
    print(f"已生成输出文件: {result.output_file}")
    print(f"输出记录数: {len(result.address_df)}")
    if result.intermediate_file:
        print(f"已生成网关中间文件: {result.intermediate_file}")
        print(f"网关记录数: {len(result.gateway_df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
