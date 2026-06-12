#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LEAF–SPINE 互联规划离线 CLI。

单平面：指定 --sheet/--plan，默认覆盖写入 A3网络互联规划.xlsx。
多平面：--sheets a,b,c 或 --all-planes 内存合并后一次写入。
兼容项目脚本：--merge-existing 会读取旧 --out，删除本次网络平面后追加新结果。
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oob_interconnect.pipeline import (  # noqa: E402
    resolve_plane_name,
    run_l2,
    run_l2_multi,
    run_l3,
    run_l3_multi,
)
from oob_interconnect.constants import DEFAULT_OUTPUT_FILENAME  # noqa: E402
from oob_interconnect.plane_config import load_plane_config  # noqa: E402


def _parse_sheet_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [s.strip() for s in value.split(",") if s.strip()]
    return items or None


def main() -> None:
    parser = argparse.ArgumentParser(description="LEAF–SPINE 互联规划（L2/L3）离线运行")
    parser.add_argument("--layer", choices=("l2", "l3"), required=True, help="二层或三层")
    parser.add_argument("--topology", required=True, help="端口连线表 xlsx 路径")
    parser.add_argument("--resource", required=True, help="资源表 xlsx 路径")
    parser.add_argument(
        "--out",
        default=DEFAULT_OUTPUT_FILENAME,
        help=f"输出 xlsx 路径（默认: {DEFAULT_OUTPUT_FILENAME}）",
    )
    parser.add_argument(
        "--plane-config",
        default=None,
        help="可选：平面配置 JSON 路径（缺省使用内置默认配置）",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="单平面：平面配置 key（兼容旧用法；优先使用 --plan）",
    )
    parser.add_argument(
        "--plan",
        default=None,
        help="单平面：互联规划名称，如 计算带外管理互联规划",
    )
    parser.add_argument(
        "--sheets",
        default=None,
        help="多平面：逗号分隔的 sheet 名集合（如 a,b,c），与 --all-planes 互斥",
    )
    parser.add_argument(
        "--all-planes",
        action="store_true",
        help="多平面：使用平面配置中全部条目",
    )
    parser.add_argument(
        "--access-plan",
        default=None,
        help="可选：接入规划 xlsx（仅 L2 用于 Trunk 避让）",
    )
    parser.add_argument(
        "--trunk-history",
        default=None,
        help="可选：历史互联规划 xlsx（仅 L2 解析 Trunk 占用，不参与输出合并）",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="按项目脚本口径合并输出：读取旧 --out，删除本次网络平面后追加新结果",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    cfg = load_plane_config(args.plane_config)

    if args.all_planes and args.sheets:
        parser.error("--all-planes 与 --sheets 互斥")

    plan = args.plan or args.sheet
    if args.plan and args.sheet:
        parser.error("--plan 与 --sheet 互斥")

    sheets = _parse_sheet_list(args.sheets) if not args.all_planes else list(cfg.keys())
    if sheets is None and not plan:
        parser.error("请指定 --plan 或 --sheet 或 --sheets 或 --all-planes")
    if plan and sheets:
        parser.error("单平面参数与多平面参数互斥")

    if sheets:
        if args.layer == "l2":
            run_l2_multi(
                args.topology,
                args.resource,
                args.out,
                sheets=sheets,
                plane_config=cfg,
                access_plan_path=args.access_plan,
                trunk_history_path=args.trunk_history,
                merge_existing=args.merge_existing,
            )
        else:
            run_l3_multi(
                args.topology,
                args.resource,
                args.out,
                sheets=sheets,
                plane_config=cfg,
                merge_existing=args.merge_existing,
            )
        logging.info("完成（多平面），输出: %s", args.out)
        return

    try:
        plan = resolve_plane_name(cfg, plan)
    except ValueError as exc:
        parser.error(f"{exc} 可选规划: {', '.join(cfg.keys())}")
    if args.layer == "l2":
        run_l2(
            args.topology,
            plan,
            args.resource,
            args.out,
            plane_config=cfg,
            access_plan_path=args.access_plan,
            trunk_history_path=args.trunk_history,
            merge_existing=args.merge_existing,
        )
    else:
        run_l3(
            args.topology,
            plan,
            args.resource,
            args.out,
            plane_config=cfg,
            merge_existing=args.merge_existing,
        )
    logging.info("完成（单平面 %s），输出: %s", plan, args.out)


if __name__ == "__main__":
    main()
