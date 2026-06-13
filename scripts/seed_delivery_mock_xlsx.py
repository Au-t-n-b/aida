#!/usr/bin/env python3
"""Seed minimal RACI template + delivery plan xlsx under data/delivery/mock (0612)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from agent.services.proposal_parse import write_xlsx_table

RACI_HEADERS = ["技术栈", "活动分类", "活动", "GTS", "华为云", "伙伴", "客户"]
RACI_ROWS = [
    {
        "技术栈": "公共",
        "活动分类": "项目管理",
        "活动": "计划进度管理、沟通管理、风险管理",
        "GTS": "R",
        "华为云": "",
        "伙伴": "S",
        "客户": "S",
    },
    {
        "技术栈": "公共",
        "活动分类": "计算-工程安装",
        "活动": "工程勘测",
        "GTS": "R",
        "华为云": "",
        "伙伴": "",
        "客户": "S",
    },
    {
        "技术栈": "算存网",
        "活动分类": "算存网-集群集成",
        "活动": "集群验收",
        "GTS": "S",
        "华为云": "",
        "伙伴": "",
        "客户": "R",
    },
]

PLAN_HEADERS = ["活动名称", "开始", "结束", "实际开始", "实际结束", "责任人", "管理单元", "任务状态", "进度"]
PLAN_ROWS = [
    {
        "活动名称": "L1机房准备",
        "开始": "2025-08-01",
        "结束": "",
        "实际开始": "",
        "实际结束": "",
        "责任人": "王长龙",
        "管理单元": "",
        "任务状态": "已派发",
        "进度": 90,
    },
    {
        "活动名称": "机房改造实施",
        "开始": "2025-12-15",
        "结束": "",
        "实际开始": "",
        "实际结束": "",
        "责任人": "王长龙",
        "管理单元": "",
        "任务状态": "已派发",
        "进度": 90,
    },
    {
        "活动名称": "工程勘测",
        "开始": "2025-08-16",
        "结束": "2025-09-20",
        "实际开始": "2026-01-10",
        "实际结束": "2026-02-28",
        "责任人": "王长龙",
        "管理单元": "",
        "任务状态": "已完成",
        "进度": 100,
    },
]


def seed(root: Path, project: str, project_name: str) -> None:
    raci_path = root / "组织资产/责任矩阵/责任矩阵模板.xlsx"
    plan_path = root / f"{project}/项目管理/计划/输入文件/交付计划表.xlsx"
    raci_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    write_xlsx_table(raci_path, RACI_HEADERS, RACI_ROWS, 0, "")
    write_xlsx_table(plan_path, PLAN_HEADERS, PLAN_ROWS, 0, project_name)
    print(f"Seeded {raci_path}")
    print(f"Seeded {plan_path}")


def main() -> None:
    here = Path(__file__).resolve().parents[1]
    default_root = here / "data" / "delivery" / "mock"
    parser = argparse.ArgumentParser(description="Seed delivery mock xlsx files")
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--project", default="mock_project")
    parser.add_argument("--project-name", default="京东三期")
    args = parser.parse_args()
    seed(args.root.resolve(), args.project, args.project_name)


if __name__ == "__main__":
    main()
