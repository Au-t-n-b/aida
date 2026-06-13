#!/usr/bin/env python3
"""Scaffold IPO directory tree under data/delivery/mock (0612 需求).

Creates folders only — no files. Idempotent.
"""
from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_PROJECT = "mock_project"

ORG_ASSET_DIRS = [
    "组织资产/智算部件配置标准库",
    "组织资产/AI平台白名单",
    "组织资产/三方系统配套表",
    "组织资产/解决方案版本配套表",
    "组织资产/昇腾训练版本标准表",
    "组织资产/昇腾推理版本标准表",
    "组织资产/入场评估标准表",
    "组织资产/工勘常见高风险库",
    "组织资产/标准勘测条目说明",
    "组织资产/活动依赖表",
    "组织资产/活动定义表",
    "组织资产/维保建议书",
    "组织资产/责任矩阵",
]


def _ipo(project: str, domain: str, module: str) -> list[str]:
    base = f"{project}/{domain}/{module}"
    return [f"{base}/输入文件", f"{base}/解析结果", f"{base}/输出结果"]


def project_dirs(project: str) -> list[str]:
    p = project
    return [
        # 孪生世界
        f"{p}/孪生世界/项目孪生",
        f"{p}/孪生世界/算力底座孪生/输入文件/CAD",
        f"{p}/孪生世界/算力底座孪生/输入文件/售前工勘",
        f"{p}/孪生世界/算力底座孪生/输入文件/机房勘测视频",
        f"{p}/孪生世界/算力底座孪生/解析结果",
        f"{p}/孪生世界/算力底座孪生/输出结果",
        # 早期介入 · 合同
        f"{p}/早期介入/合同/输入文件/合同文件",
        f"{p}/早期介入/合同/输入文件/BOQ",
        f"{p}/早期介入/合同/解析结果/BOQ",
        f"{p}/早期介入/合同/输出结果/建模仿真",
        *_ipo(p, "早期介入", "合同"),
        # 早期介入 · 交付预案
        f"{p}/早期介入/交付预案/输入文件/HLD",
        f"{p}/早期介入/交付预案/输入文件/服务建议书",
        f"{p}/早期介入/交付预案/输入文件/维保建议书",
        f"{p}/早期介入/交付预案/输入文件/技术建议书",
        f"{p}/早期介入/交付预案/输入文件/合同",
        f"{p}/早期介入/交付预案/输入文件/测试用例",
        f"{p}/早期介入/交付预案/解析结果/HLD解析结果",
        f"{p}/早期介入/交付预案/解析结果/服务建议书解析结果",
        f"{p}/早期介入/交付预案/解析结果/维保建议书解析结果",
        f"{p}/早期介入/交付预案/解析结果/技术建议书解析结果",
        f"{p}/早期介入/交付预案/解析结果/测试用例解析结果",
        f"{p}/早期介入/交付预案/解析结果/验收策略解析结果",
        f"{p}/早期介入/交付预案/输出结果",
        *_ipo(p, "早期介入", "交付预案"),
        # 交付方案
        f"{p}/交付方案/输入文件",
        f"{p}/交付方案/解析结果",
        f"{p}/交付方案/输出结果",
        # 项目管理
        f"{p}/项目管理/基本信息",
        f"{p}/项目管理/计划/输入文件",
        f"{p}/项目管理/计划/解析结果",
        f"{p}/项目管理/计划/输出结果",
        *_ipo(p, "项目管理", "任务"),
        *_ipo(p, "项目管理", "风险"),
        *_ipo(p, "项目管理", "假设"),
        *_ipo(p, "项目管理", "问题"),
        *_ipo(p, "项目管理", "变更"),
        # 交付作业
        f"{p}/交付作业/智慧工勘/输入文件/勘测图片文件夹",
        *_ipo(p, "交付作业", "智慧工勘"),
        f"{p}/交付作业/规划设计/输入文件",
        f"{p}/交付作业/规划设计/解析结果",
        f"{p}/交付作业/规划设计/输出结果/建模仿真",
        f"{p}/交付作业/规划设计/输出结果/系统设计",
        *_ipo(p, "交付作业", "设备安装"),
        *_ipo(p, "交付作业", "部署调测"),
        # 项目复盘 / Skill定制 / 项目文档
        f"{p}/项目复盘/输入文件",
        f"{p}/项目复盘/解析结果",
        f"{p}/项目复盘/输出结果",
        f"{p}/Skill定制",
        f"{p}/项目文档",
    ]


def collect_dirs(projects: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for d in ORG_ASSET_DIRS:
        if d not in seen:
            seen.add(d)
            ordered.append(d)
    for project in projects:
        for d in project_dirs(project):
            if d not in seen:
                seen.add(d)
                ordered.append(d)
    return ordered


def scaffold(root: Path, projects: list[str]) -> int:
    root.mkdir(parents=True, exist_ok=True)
    created = 0
    for rel in collect_dirs(projects):
        path = root / rel
        existed = path.is_dir()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created += 1
    return created


def main() -> None:
    here = Path(__file__).resolve().parents[1]
    default_root = here / "data" / "delivery" / "mock"

    parser = argparse.ArgumentParser(description="Scaffold data/delivery/mock IPO directories")
    parser.add_argument("--root", type=Path, default=default_root, help="Mock data root")
    parser.add_argument(
        "--project",
        action="append",
        dest="projects",
        default=None,
        help=f"Project folder name (repeatable, default: {DEFAULT_PROJECT})",
    )
    args = parser.parse_args()
    projects = args.projects or [DEFAULT_PROJECT]

    n = scaffold(args.root.resolve(), projects)
    print(f"Scaffold complete: root={args.root.resolve()} projects={projects} new_dirs={n}")


if __name__ == "__main__":
    main()
