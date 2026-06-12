#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Offline implementation aligned with a3_network_access_plan.py.

The project implementation only reads the merged "A3网络设备接入规划.xlsx"
workbook and filters rows by the network plane resolved from main_flow.py and
WEB_NETWORK_TYPE_CONFIG. This module keeps that behavior offline and exposes a
small CLI-friendly wrapper around the same core logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ACCESS_PLAN_SHEET_NAME = "网络设备接入规划"
DEFAULT_ACCESS_PLAN_FILE = "A3网络设备接入规划.xlsx"

WEB_NETWORK_TYPE_CONFIG = {
    "存储面端口互联 | 样本面端口互联": "计算样本面",
    "计算管理面端口互联": "计算管理面",
    "计算业务面端口互联": "计算业务面",
    "计算管存面端口互联": "计算管存面",
    "参数面端口互联": "计算参数面",
    "样本面端口互联 | 数据面端口互联": "存储样本面",
    "存储业务面端口互联": "存储业务面",
    "存储管理面端口互联": "存储管理面",
    "计算带外管理面端口互联": "计算带外管理面",
    "网络带外管理面端口互联": "网络带外管理面",
    "灵衢带外管理面端口互联": "灵衢带外管理面",
    "存储带外管理面端口互联": "存储带外管理面",
    "带外管理面端口互联": "带外管理面",
    "超平面端口互联": "超平面",
    "网络业务地址规划": "其它",
}


# Mirrors main_flow.py lines 276-411. Values are sheet names, and the displayed
# network plane is resolved through WEB_NETWORK_TYPE_CONFIG, just like the
# project code does inside a3_network_access_plan.network_access_plan().
ACCESS_PLAN_TO_SHEET = {
    "带外管理面接入规划": "存储管理面端口互联",
    "计算管理面接入规划": "计算管理面端口互联",
    "计算业务面接入规划": "计算业务面端口互联",
    "计算样本面接入规划": "存储面端口互联 | 样本面端口互联",
    "计算参数面接入规划": "参数面端口互联",
    "计算管存面接入规划": "计算管存面端口互联",
    "存储管理面接入规划": "存储管理面端口互联",
    "存储业务面接入规划": "存储业务面端口互联",
    "存储样本面接入规划": "样本面端口互联 | 数据面端口互联",
    "计算带外管理接入规划": "计算带外管理面端口互联",
    "计算带外管理面接入规划": "计算带外管理面端口互联",
    "存储带外管理接入规划": "存储带外管理面端口互联",
    "存储带外管理面接入规划": "存储带外管理面端口互联",
    "网络带外管理接入规划": "网络带外管理面端口互联",
    "网络带外管理面接入规划": "网络带外管理面端口互联",
    "灵衢带外管理接入规划": "灵衢带外管理面端口互联",
    "灵衢带外管理面接入规划": "灵衢带外管理面端口互联",
}


@dataclass(frozen=True)
class AccessPlanResult:
    result_df: pd.DataFrame
    network_plane: str
    sheet_name: str
    output_file: Path | None
    title: str
    reason: str
    markdown: str


def normalize_plan_name(plan_name: str) -> str:
    """Drop L2/L3 suffixes so CLI users can pass main_flow keys directly."""
    normalized = str(plan_name).strip()
    for suffix in ("_L2", "_L3"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def resolve_access_plan(plan_name: str | None = None, sheet_name: str | None = None, plane: str | None = None) -> tuple[str, str]:
    if plane:
        resolved_sheet = sheet_name or ""
        return resolved_sheet, str(plane).strip()

    if sheet_name:
        if sheet_name not in WEB_NETWORK_TYPE_CONFIG:
            raise ValueError(f"不支持的接入规划 sheet：{sheet_name}")
        return sheet_name, WEB_NETWORK_TYPE_CONFIG[sheet_name]

    if not plan_name:
        raise ValueError("必须提供 --plan、--sheet 或 --plane 之一")

    normalized = normalize_plan_name(plan_name)
    if normalized not in ACCESS_PLAN_TO_SHEET:
        supported = "、".join(sorted(ACCESS_PLAN_TO_SHEET))
        raise ValueError(f"不支持的接入规划：{plan_name}；支持：{supported}")

    resolved_sheet = ACCESS_PLAN_TO_SHEET[normalized]
    return resolved_sheet, WEB_NETWORK_TYPE_CONFIG[resolved_sheet]


def _read_access_plan(access_plan_file: str | Path) -> pd.DataFrame:
    """Read the first worksheet, matching the project implementation."""
    return pd.read_excel(Path(access_plan_file), sheet_name=0, header=0)


def _filter_access_plan(df: pd.DataFrame, network_plane: str) -> pd.DataFrame:
    """Apply the same filtering and display normalization as the project code."""
    result_df = df[df["网络平面"].isin([network_plane])].copy()
    result_df["vlan"] = pd.to_numeric(result_df["vlan"], errors="coerce").astype("Int64")
    result_df["pvid"] = pd.to_numeric(result_df["pvid"], errors="coerce").astype("Int64")
    return result_df.astype(object).fillna("")


def _build_reason(network_plane: str, result_df: pd.DataFrame) -> str:
    if not result_df.empty:
        return f"{network_plane}的网络设备接入规划已生成，结果如下。"
    return f"{network_plane}的网络设备接入规划暂未查询到，请检查是否已经执行{network_plane}的地址规划指令"


def network_access_plan(access_plan_file: str | Path, sheet_name: str) -> pd.DataFrame:
    """Project-aligned offline entry point.

    The project function receives user/project/dialogue context and then reads
    ``{user_id}_{project_id}_A3网络设备接入规划.xlsx`` from project storage. In the
    standalone skill, callers pass that workbook path directly while the core
    Excel and DataFrame behavior stays aligned with the project file.
    """
    network_plane = WEB_NETWORK_TYPE_CONFIG[sheet_name]
    df = _read_access_plan(access_plan_file)
    return _filter_access_plan(df, network_plane)


def query_access_plan(
    access_plan_file: str | Path,
    *,
    plan_name: str | None = None,
    sheet_name: str | None = None,
    plane: str | None = None,
    output_file: str | Path | None = None,
) -> AccessPlanResult:
    resolved_sheet, network_plane = resolve_access_plan(plan_name=plan_name, sheet_name=sheet_name, plane=plane)
    df = _read_access_plan(access_plan_file)
    result_df = _filter_access_plan(df, network_plane)
    markdown = result_df.to_markdown(index=False)
    reason = _build_reason(network_plane, result_df)

    output_path: Path | None = None
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_excel(output_path, sheet_name=ACCESS_PLAN_SHEET_NAME, index=False)

    return AccessPlanResult(
        result_df=result_df,
        network_plane=network_plane,
        sheet_name=resolved_sheet,
        output_file=output_path,
        title=f"{network_plane}网络设备接入规划",
        reason=reason,
        markdown=markdown,
    )
