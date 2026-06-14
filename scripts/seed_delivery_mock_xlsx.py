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

ACCEPTANCE_HEADERS = [
    "分类", "验收方案", "验收标准", "验收里程碑", "验收文档", "回款条款", "回款里程碑",
]
ACCEPTANCE_ROWS = [
    {
        "分类": "到货",
        "验收方案": "设备到货清点",
        "验收标准": "型号/数量与 BOQ 一致，外观无损",
        "验收里程碑": "到货签收",
        "验收文档": "到货验收单",
        "回款条款": "20%",
        "回款里程碑": "到货",
    },
    {
        "分类": "安装 PAC",
        "验收方案": "整机柜 ST 测试",
        "验收标准": "GPU 数量与 BOQ 一致，误码率 ≤ 1e-12",
        "验收里程碑": "部署调测完成",
        "验收文档": "验收测试报告",
        "回款条款": "30%",
        "回款里程碑": "安装 PAC",
    },
    {
        "分类": "安装 PAC",
        "验收方案": "RDMA 全互联压测",
        "验收标准": "400G 带宽达标，时延 p99 ≤ 2μs",
        "验收里程碑": "集群联调完成",
        "验收文档": "网络测试报告",
        "回款条款": "—",
        "回款里程碑": "—",
    },
    {
        "分类": "维保",
        "验收方案": "维保服务启动",
        "验收标准": "维保策略与 SLA 合同一致",
        "验收里程碑": "维保生效",
        "验收文档": "维保确认函",
        "回款条款": "—",
        "回款里程碑": "—",
    },
    {
        "分类": "培训",
        "验收方案": "AI 使能培训",
        "验收标准": "参训人数 ≥ 合同，考核通过",
        "验收里程碑": "培训完成",
        "验收文档": "培训签到表",
        "回款条款": "—",
        "回款里程碑": "—",
    },
]

TESTCASE_HEADERS = [
    "勾选", "用例编号", "一级分类", "二级分类", "三级分类",
    "测试目的", "测试组网", "预置条件", "测试步骤", "预期结果", "测试结果", "备注",
]
TESTCASE_ROWS = [
    {
        "勾选": "是",
        "用例编号": "1.1.1",
        "一级分类": "计算子系统测试用例",
        "二级分类": "基本功能测试",
        "三级分类": "机柜硬件检测",
        "测试目的": "检查机柜硬件信息。",
        "测试组网": "NA",
        "预置条件": "机房温度，海拔，湿度满足要求。",
        "测试步骤": "将机柜外包装打开。\n记录机柜的产品名称。",
        "预期结果": "根据实际到货情况进行记录。",
        "测试结果": "",
        "备注": "",
    },
    {
        "勾选": "是",
        "用例编号": "1.1.2",
        "一级分类": "计算子系统测试用例",
        "二级分类": "基本功能测试",
        "三级分类": "计算节点硬件检测",
        "测试目的": "检查计算节点硬件信息。",
        "测试组网": "NA",
        "预置条件": "机房环境满足要求。",
        "测试步骤": "将计算节点外包装打开。\n记录计算节点的产品名称。",
        "预期结果": "根据实际到货情况进行记录。",
        "测试结果": "",
        "备注": "",
    },
    {
        "勾选": "是",
        "用例编号": "1.1.3",
        "一级分类": "计算子系统测试用例",
        "二级分类": "基本功能测试",
        "三级分类": "计算节点硬件模块标示测试",
        "测试目的": "检查计算节点硬件模块标示是否清晰易辨认。",
        "测试组网": "NA",
        "预置条件": "计算节点外包装已打开。",
        "测试步骤": "检查计算节点外部模块标示是否清晰易辨认。",
        "预期结果": "计算节点内外部硬件模块标示清晰易辨认。",
        "测试结果": "",
        "备注": "",
    },
]


def seed(root: Path, project: str, project_name: str) -> None:
    raci_path = root / "组织资产/责任矩阵/责任矩阵模板.xlsx"
    plan_path = root / f"{project}/项目管理/计划/输入文件/交付计划表.xlsx"
    acceptance_path = root / f"{project}/早期介入/交付预案/输出结果/验收策略.xlsx"
    testcases_path = root / f"{project}/早期介入/交付预案/输出结果/测试用例.xlsx"
    raci_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    acceptance_path.parent.mkdir(parents=True, exist_ok=True)
    testcases_path.parent.mkdir(parents=True, exist_ok=True)
    write_xlsx_table(raci_path, RACI_HEADERS, RACI_ROWS, 0, "")
    write_xlsx_table(plan_path, PLAN_HEADERS, PLAN_ROWS, 0, project_name)
    write_xlsx_table(acceptance_path, ACCEPTANCE_HEADERS, ACCEPTANCE_ROWS, 1, project_name)
    write_xlsx_table(testcases_path, TESTCASE_HEADERS, TESTCASE_ROWS, 1, project_name)
    print(f"Seeded {raci_path}")
    print(f"Seeded {plan_path}")
    print(f"Seeded {acceptance_path}")
    print(f"Seeded {testcases_path}")


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
