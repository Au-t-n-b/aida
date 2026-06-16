"""§4.2 交付预案输出表注册 · 对齐 05-数据目录与平台规范。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RowsEnvelope = Literal["rows", "cases", "array", "auto"]

_PARSE_ROOT = "早期介入/交付预案/解析结果"
_CONTRACT_PARSE = "早期介入/合同/解析结果"


@dataclass(frozen=True)
class OutputTableSpec:
    logical_name: str
    xlsx_name: str
    chapter_key: str | None
    parse_dirs: tuple[str, ...]
    parse_glob: str = "*.json"
    rows_envelope: RowsEnvelope = "auto"
    upstream_writes_output: bool = False
    """True 时若 输出结果/xlsx 已存在则 promote 跳过（不覆盖上游直写）。"""


PROPOSAL_OUTPUT_TABLES: tuple[OutputTableSpec, ...] = (
    OutputTableSpec(
        "预案版本信息表",
        "预案版本信息表.xlsx",
        "meta",
        (),
    ),
    OutputTableSpec(
        "项目背景信息表",
        "项目背景信息表.xlsx",
        "1",
        (f"{_PARSE_ROOT}/HLD解析结果",),
    ),
    OutputTableSpec(
        "设备信息表",
        "设备信息表.xlsx",
        "2",
        (),
        upstream_writes_output=True,
    ),
    OutputTableSpec(
        "智算部件配置信息表",
        "智算部件配置信息表.xlsx",
        "3",
        (f"{_PARSE_ROOT}/部件配置解析结果",),
    ),
    OutputTableSpec(
        "软件配置信息表",
        "软件配置信息表.xlsx",
        "4",
        (f"{_PARSE_ROOT}/软件配置解析结果",),
    ),
    OutputTableSpec(
        "共平面类型表",
        "共平面类型表.xlsx",
        "5.1",
        (f"{_PARSE_ROOT}/共平面类型解析结果",),
    ),
    OutputTableSpec(
        "网络平面配置信息表",
        "网络平面配置信息表.xlsx",
        "5.1",
        (f"{_PARSE_ROOT}/网络平面配置解析结果",),
    ),
    OutputTableSpec(
        "网管服务器配置表",
        "网管服务器配置表.xlsx",
        "5.2",
        (f"{_PARSE_ROOT}/网管服务器配置解析结果",),
    ),
    OutputTableSpec(
        "集群设备清单表",
        "集群设备清单表.xlsx",
        "5.3",
        (f"{_PARSE_ROOT}/集群设备清单解析结果",),
    ),
    OutputTableSpec(
        "预集成预验证需求信息表",
        "预集成预验证需求信息表.xlsx",
        "6",
        (f"{_PARSE_ROOT}/集成验证需求解析结果",),
    ),
    OutputTableSpec(
        "服务配置表",
        "服务配置表.xlsx",
        "8.1",
        (
            f"{_PARSE_ROOT}/服务配置解析结果",
            f"{_CONTRACT_PARSE}/服务BOQ解析结果",
        ),
    ),
    OutputTableSpec(
        "服务内容表",
        "服务内容表.xlsx",
        "8.2",
        (
            f"{_PARSE_ROOT}/服务内容解析结果",
            f"{_CONTRACT_PARSE}/服务BOQ解析结果",
        ),
    ),
    OutputTableSpec(
        "维保策略表",
        "维保策略表.xlsx",
        "8.3",
        (
            f"{_PARSE_ROOT}/维保策略解析结果",
            f"{_CONTRACT_PARSE}/服务BOQ解析结果",
        ),
    ),
    OutputTableSpec(
        "维保SLA表",
        "维保SLA表.xlsx",
        "8.4",
        (f"{_PARSE_ROOT}/维保建议书解析结果",),
    ),
    OutputTableSpec(
        "项目责任矩阵",
        "项目责任矩阵.xlsx",
        "9",
        (f"{_PARSE_ROOT}/责任矩阵解析结果",),
    ),
    OutputTableSpec(
        "验收策略",
        "验收策略.xlsx",
        "11",
        (
            f"{_PARSE_ROOT}/验收策略解析结果",
            f"{_PARSE_ROOT}/服务建议书解析结果",
            f"{_PARSE_ROOT}/技术建议书解析结果",
        ),
        rows_envelope="rows",
    ),
    OutputTableSpec(
        "测试用例",
        "测试用例.xlsx",
        "12",
        (f"{_PARSE_ROOT}/测试用例解析结果",),
        rows_envelope="auto",
    ),
)

OUTPUT_TABLE_BY_XLSX = {spec.xlsx_name: spec for spec in PROPOSAL_OUTPUT_TABLES}

SPEC_XLSX_NAMES: frozenset[str] = frozenset(OUTPUT_TABLE_BY_XLSX.keys())
