# -*- coding: utf-8 -*-
"""Leaf–Spine 网络互联规划：确定性规则。

L3 与 a3_ni_ip_address 对齐。L2 在接口/VLAN/列结构上与 a3_l2_net_interconnection 对齐，
**本 skill 约定：`本端ETH-TRUNK` 与 `对端ETH-TRUNK` 输出恒为 2**（不按设备动态递增）。
"""

from __future__ import annotations

import ipaddress
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# 与 src/manage_agent/sub_agents/LLD_IP/config.py LEAF_SPINE_CONFIG 中计算侧五类平面一致
LEAF_SPINE_COMPUTE_PLANES: Dict[str, Dict[str, str]] = {
    "参数面端口互联": {"keyword": "LEAF", "network_type": "计算参数面"},
    "计算管存面端口互联": {"keyword": "GCM-LEAF", "network_type": "计算管存面"},
    "计算业务面端口互联": {"keyword": "YWM-LEAF", "network_type": "计算业务面"},
    "计算管理面端口互联": {"keyword": "GLM-LEAF", "network_type": "计算管理面"},
    # config 全名（竖线）；部分 007 仅提供简名「样本面端口互联」
    "存储面端口互联 | 样本面端口互联": {"keyword": "ZSYBM-LEAF", "network_type": "计算样本面"},
    "样本面端口互联": {"keyword": "ZSYBM-LEAF", "network_type": "计算样本面"},
}

# 由网络平面反查 007 sheet 候选（按顺序尝试，直至解析出 Leaf–Spine 连线）
NETWORK_TYPE_TO_007_SHEET_CANDIDATES: Dict[str, List[str]] = {
    "计算参数面": ["参数面端口互联"],
    "计算管存面": ["计算管存面端口互联"],
    "计算业务面": ["计算业务面端口互联"],
    "计算管理面": ["计算管理面端口互联"],
    "计算样本面": ["样本面端口互联", "存储面端口互联 | 样本面端口互联"],
}


def supported_network_planes() -> List[str]:
    return sorted({c["network_type"] for c in LEAF_SPINE_COMPUTE_PLANES.values()})


def resolve_keyword_network_from_plane(network_plane: str) -> Tuple[str, str]:
    """--plane 与资源表第一列「网络平面」取值一致时，解析 keyword / network_type。"""
    plane_st = str(network_plane).strip()
    for _sheet, cfg in LEAF_SPINE_COMPUTE_PLANES.items():
        if cfg["network_type"] == plane_st:
            return cfg["keyword"], cfg["network_type"]
    raise ValueError(
        f"网络平面 {plane_st!r} 不在本 skill 支持范围，支持: {supported_network_planes()}"
    )


def read_plane_row_from_resource_df(df: pd.DataFrame, network_plane: str) -> pd.Series:
    """按资源表第一列匹配「网络平面」行。"""
    first_col = df.columns[0]
    mask = df[first_col].astype(str).str.strip() == str(network_plane).strip()
    hit = df.loc[mask]
    if hit.empty:
        raise ValueError(
            f"资源表第一列「{first_col}」未找到网络平面: {network_plane!r}；"
            f"支持取值: {supported_network_planes()}"
        )
    if len(hit) > 1:
        logger.warning("第一列匹配到多行，取首行")
    return hit.iloc[0]


def gateway_column_name(df: pd.DataFrame) -> str:
    for c in df.columns:
        if "网关位置" in str(c):
            return str(c)
    raise ValueError("资源表中未找到含「网关位置」的列（如 网关位置*）")


def resolve_gateway_mode(gateway_value: Any) -> str:
    """网关位置：SPINE -> l2；LEAF -> l3（与计算管理面 L2/L3 接入规划约定一致）。"""
    if gateway_value is None or (isinstance(gateway_value, float) and pd.isna(gateway_value)):
        raise ValueError("网关位置为空，无法选择 L2/L3")
    s = str(gateway_value).strip().upper().replace(" ", "")
    if s == "LEAF":
        return "l3"
    if s == "SPINE":
        return "l2"
    raise ValueError(f"网关位置无法识别: {gateway_value!r}，期望 LEAF 或 SPINE（不区分大小写）")


def find_working_007_sheet(
    path_007: Path | str,
    mode: str,
    keyword: str,
    network_type: str,
) -> Tuple[pd.DataFrame, str]:
    """在 007 工作簿中按候选 sheet 顺序尝试，返回首个能解析出连线的 sheet 及其 DataFrame。"""
    path_007 = Path(path_007)
    candidates = NETWORK_TYPE_TO_007_SHEET_CANDIDATES.get(network_type)
    if not candidates:
        raise ValueError(f"未配置 network_type 对应的 007 sheet 候选: {network_type!r}")
    xl = pd.ExcelFile(path_007)
    available = set(xl.sheet_names)
    last_err: Optional[BaseException] = None
    for sheet in candidates:
        if sheet not in available:
            continue
        df_raw = pd.read_excel(path_007, sheet_name=sheet, header=None)
        try:
            if mode == "l2":
                get_switch_data_l2(df_raw, keyword)
            else:
                get_switch_data_l3(df_raw, keyword)
            return df_raw, sheet
        except Exception as e:
            last_err = e
            logger.debug("007 sheet %s 跳过: %s", sheet, e)
            continue
    msg = (
        f"007 中未能为 {network_type!r} 解析出 Leaf–Spine 连线；"
        f"候选 sheet: {candidates}；实际 sheet: {sorted(available)}"
    )
    if last_err is not None:
        msg += f"；最后错误: {last_err}"
    raise ValueError(msg)


def resolve_sheet_config(sheet_name: str) -> Tuple[str, str]:
    if sheet_name not in LEAF_SPINE_COMPUTE_PLANES:
        raise ValueError(f"sheet_name '{sheet_name}' 没有对应的配置项（本 skill 仅支持计算侧五类平面）。")
    c = LEAF_SPINE_COMPUTE_PLANES[sheet_name]
    return c["keyword"], c["network_type"]


def _header_row_idx(df_all: pd.DataFrame) -> int:
    header_mask = df_all.astype(str).apply(lambda row: row.str.contains("设备命名", case=False).any(), axis=1)
    if not header_mask.any():
        raise ValueError("未找到包含'设备命名'的行，请检查表格内容")
    return int(header_mask.idxmax())


def get_switch_data_l2(df_all: pd.DataFrame, keyword: str) -> Tuple[pd.DataFrame, int]:
    header_row_idx = _header_row_idx(df_all)
    result_df = (
        df_all.iloc[header_row_idx + 1 :]
        .reset_index(drop=True)
        .rename(
            columns={
                df_all.columns[0]: "leaf交换机",
                df_all.columns[1]: "本端端口",
                df_all.columns[2]: "本端接口带宽",
                df_all.columns[-4]: "对端带宽",
                df_all.columns[-2]: "对端端口",
                df_all.columns[-3]: "对端接口类型",
                df_all.columns[-1]: "spine交换机",
            }
        )
        .query(
            f"`leaf交换机`.str.contains(\"{keyword}\", case=False, na=False) & "
            f'`spine交换机`.str.contains("spine", case=False, na=False)'
        )
        .drop_duplicates()
    )
    row_count = result_df.shape[0]
    if row_count == 0:
        raise ValueError(
            f"未找到包含'{keyword}'关键字的行，未找到从LEAF到SPINE的物理连线，请检查连线表"
        )
    return result_df, row_count


def get_switch_data_l3(df_all: pd.DataFrame, keyword: str) -> Tuple[pd.DataFrame, int]:
    header_row_idx = _header_row_idx(df_all)
    result_df = (
        df_all.iloc[header_row_idx + 1 :]
        .reset_index(drop=True)
        .rename(
            columns={
                df_all.columns[0]: "leaf交换机",
                df_all.columns[1]: "本端端口",
                df_all.columns[-2]: "对端端口",
                df_all.columns[-3]: "对端接口类型",
                df_all.columns[-1]: "spine交换机",
            }
        )
        .query(
            f"`leaf交换机`.str.contains(\"{keyword}\", case=False, na=False) & "
            f'`spine交换机`.str.contains("spine", case=False, na=False)'
        )
        .drop_duplicates()
    )
    row_count = result_df.shape[0]
    if row_count == 0:
        raise ValueError(
            f"未找到包含'{keyword}'关键字的行，未找到从LEAF到SPINE的物理连线，请检查连线表"
        )
    return result_df, row_count


def allocate_connection(
    df: pd.DataFrame,
    vlan: Any,
    network_type: str,
) -> pd.DataFrame:
    df = df.copy()
    df.loc[
        :,
        [
            "端口类型",
            "本端ETH-TRUNK",
            "本端VLAN",
            "对端ETH-TRUNK",
            "对端VLAN",
            "PVID",
            "标签",
            "网络平面",
            "本端接口IP地址",
            "本端接口掩码",
            "对端接口IP地址",
            "对端接口掩码",
        ],
    ] = ["trunk", "", "", "", "", "", "", "", "", "", "", ""]
    df["本端接口"] = df.iloc[:, 2].fillna("") + df.iloc[:, 1].fillna("")
    df["本端接口"] = df["本端接口"].str.strip()
    df["对端接口"] = df.iloc[:, 5].fillna("") + df.iloc[:, 7].fillna("")
    df["对端接口"] = df["对端接口"].str.strip()
    df.rename(columns={df.columns[0]: "本端设备", df.columns[8]: "对端设备"}, inplace=True)
    df = df[
        [
            "本端设备",
            "对端设备",
            "本端ETH-TRUNK",
            "本端VLAN",
            "对端ETH-TRUNK",
            "对端VLAN",
            "PVID",
            "端口类型",
            "标签",
            "网络平面",
            "本端接口IP地址",
            "本端接口掩码",
            "对端接口IP地址",
            "对端接口掩码",
            "本端接口",
            "对端接口",
        ]
    ]
    new_order = [
        "网络平面",
        "本端设备",
        "本端接口",
        "本端接口IP地址",
        "本端接口掩码",
        "本端ETH-TRUNK",
        "本端VLAN",
        "对端设备",
        "对端接口",
        "对端接口IP地址",
        "对端接口掩码",
        "对端ETH-TRUNK",
        "对端VLAN",
        "PVID",
        "端口类型",
        "标签",
    ]
    df = df[new_order]
    # 避免 pandas StringDtype 列无法写入整数（ETH-TRUNK、VLAN 等）
    for _col in ("本端ETH-TRUNK", "对端ETH-TRUNK", "本端VLAN", "对端VLAN", "网络平面"):
        df[_col] = df[_col].astype(object)

    # 本 skill 约定：互联规划输出中本端/对端 ETH-TRUNK 统一为 2
    df["本端ETH-TRUNK"] = 2
    df["对端ETH-TRUNK"] = 2
    df.loc[:, ["网络平面", "本端VLAN", "对端VLAN", "PVID", "标签"]] = [
        network_type,
        vlan,
        vlan,
        "",
        "INTER_LINK",
    ]
    return df


def read_resource_vlan(resource_xlsx: str, network_type: str, resource_sheet: str = "网络资源需求表") -> Any:
    df = pd.read_excel(resource_xlsx, sheet_name=resource_sheet, header=0)
    row = df[df["网络平面"] == network_type]
    if row.empty:
        raise ValueError(f"未找到{network_type}所在行。")
    vlan = row["VLAN*"].values[0]
    if pd.isna(vlan):
        raise ValueError(f"{network_type} VLAN* 为空。")
    return vlan


def read_resource_interconnect_segment(
    resource_xlsx: str, network_type: str, resource_sheet: str = "网络资源需求表"
) -> List[str]:
    df = pd.read_excel(resource_xlsx, sheet_name=resource_sheet, header=0)
    row = df[df["网络平面"] == network_type]
    if row.empty:
        raise ValueError(f"未找到{network_type}所在行。")
    ip_pool = row["内部网络设备互连地址段"].values[0]
    if pd.isna(ip_pool) or not str(ip_pool).strip():
        raise ValueError(f"{network_type}内部网络设备互连地址段为空。")
    s = str(ip_pool).strip()
    parts = s.split("-", 1)
    if len(parts) != 2:
        parts = s.split("-")
        if len(parts) != 2:
            raise ValueError(f"内部网络设备互连地址段格式无效: {ip_pool!r}（期望 起始IP-结束IP）")
    return [parts[0].strip(), parts[1].strip()]


def validate_network_range(network_range: List[str], required_subnets: int) -> None:
    start_ip = ipaddress.IPv4Address(network_range[0].strip())
    end_ip = ipaddress.IPv4Address(network_range[1].strip())
    if start_ip >= end_ip:
        raise ValueError("错误: 网段范围无效 - 起始IP必须小于结束IP")
    valid_start_ip = int(start_ip)
    if valid_start_ip % 4 != 0:
        valid_start_ip = (valid_start_ip // 4 + 1) * 4
    adjusted_total = int(end_ip) - valid_start_ip + 1
    if adjusted_total < 4:
        raise ValueError("错误: 网段范围无效 - 调整后的网段范围太小，无法容纳任何/30子网")
    max_subnets = adjusted_total // 4
    if required_subnets > max_subnets:
        raise ValueError(
            f"错误: 网段范围无效 - 错误: 网段范围只能容纳 {max_subnets} 个/30子网，但需要分配 {required_subnets} 个"
        )
    logger.info("网段范围校验通过，可分配 %s 个/30子网，需要分配 %s 个", max_subnets, required_subnets)


def allocate_ips(df: pd.DataFrame, custom_network: List[str], network_type: str) -> pd.DataFrame:
    start_ip = ipaddress.IPv4Address(custom_network[0].strip())
    end_ip = ipaddress.IPv4Address(custom_network[1].strip())
    start_ip_int = int(start_ip)
    if start_ip_int % 4 != 0:
        start_ip_int = (start_ip_int // 4 + 1) * 4
        start_ip = ipaddress.IPv4Address(start_ip_int)
        logger.info("起始IP已调整为: %s", start_ip)

    df = df.copy()
    df["本端接口"] = df.iloc[:, 2].fillna("") + df.iloc[:, 1].fillna("")
    df["本端接口"] = df["本端接口"].str.strip()
    df["对端接口"] = df.iloc[:, 5].fillna("") + df.iloc[:, 7].fillna("")
    df["对端接口"] = df["对端接口"].str.strip()

    result_df = pd.DataFrame(
        columns=[
            "网络平面",
            "本端设备",
            "本端接口",
            "本端接口IP地址",
            "本端接口掩码",
            "本端ETH-TRUNK",
            "本端VLAN",
            "对端设备",
            "对端接口",
            "对端接口IP地址",
            "对端接口掩码",
            "对端ETH-TRUNK",
            "对端VLAN",
            "PVID",
            "端口类型",
            "标签",
        ]
    )
    current_ip = start_ip
    for _index, row in df.iterrows():
        device1 = row["leaf交换机"]
        device2 = row["spine交换机"]
        if current_ip + 3 > end_ip:
            logger.warning(
                "网络范围 %s 中的IP地址已分配完，无法继续为设备 %s 和 %s 分配",
                custom_network,
                device1,
                device2,
            )
            continue
        ip1 = current_ip + 1
        ip2 = current_ip + 2
        result_df.loc[len(result_df)] = [
            network_type,
            device1,
            row["本端接口"],
            f"{ip1}",
            30,
            "",
            "",
            device2,
            row["对端接口"],
            f"{ip2}",
            30,
            "",
            "",
            "",
            "",
            "INTER_LINK",
        ]
        current_ip += 4
    out = result_df.dropna(axis=1, how="all").apply(
        lambda x: x.str.strip() if x.dtype == "object" else x
    )
    return out


def merge_interconnect_output(
    old_df: pd.DataFrame, new_df: pd.DataFrame, network_type: str
) -> pd.DataFrame:
    if old_df.empty:
        return new_df
    if "网络平面" not in old_df.columns:
        return new_df
    old_df = old_df[~old_df["网络平面"].isin([network_type])]
    return pd.concat([old_df, new_df], axis=0)
