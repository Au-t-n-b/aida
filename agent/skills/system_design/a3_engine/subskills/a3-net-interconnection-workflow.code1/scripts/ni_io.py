"""读取 LEAF-SPINE 端口互联表与资源表（对齐 a3_l2_net_interconnection / a3_ni_ip_address）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

RESOURCE_SHEET_NAME = "网络资源需求表"
GATEWAY_POSITION_COL = "网关位置*"
VLAN_COL = "VLAN*"
INTERCONNECT_POOL_COL = "内部网络设备互连地址段"

# 对齐 config.LEAF_SPINE_CONFIG
LEAF_SPINE_CONFIG: Dict[str, Dict[str, str]] = {
    "参数面端口互联": {"keyword": "LEAF", "network_type": "计算参数面"},
    "计算管存面端口互联": {"keyword": "GCM-LEAF", "network_type": "计算管存面"},
    "计算业务面端口互联": {"keyword": "YWM-LEAF", "network_type": "计算业务面"},
    "计算管理面端口互联": {"keyword": "GLM-LEAF", "network_type": "计算管理面"},
    "存储面端口互联 | 样本面端口互联": {"keyword": "ZSYBM-LEAF", "network_type": "计算样本面"},
    "样本面端口互联 | 数据面端口互联": {"keyword": "CCYBM-LEAF", "network_type": "存储样本面"},
    "存储管理面端口互联": {"keyword": "CCGLM-LEAF", "network_type": "存储管理面"},
    "存储业务面端口互联": {"keyword": "CCYWM-LEAF", "network_type": "存储业务面"},
    "计算带外管理面端口互联": {"keyword": "DWGL-LEAF", "network_type": "计算带外管理面"},
    "网络带外管理面端口互联": {"keyword": "DWGL-LEAF", "network_type": "网络带外管理面"},
    "存储带外管理面端口互联": {"keyword": "DWGL-LEAF", "network_type": "存储带外管理面"},
    "灵衢带外管理面端口互联": {"keyword": "DWGL-LEAF", "network_type": "灵衢带外管理面"},
    "SPINE上行端口互联": {"keyword": "FW-", "network_type": "防火墙互联地址"},
}

# 对齐 config.INSTRUCTION_NETWORK_TYPE_CONFIG（仅 *互联规划*，不含接入规划）
INTERCONNECTION_INTENTS: Dict[str, str] = {
    "计算业务面互联规划": "计算业务面端口互联",
    "计算管理面互联规划": "计算管理面端口互联",
    "计算管存面互联规划": "计算管存面端口互联",
    "计算样本面互联规划": "存储面端口互联 | 样本面端口互联",
    "计算参数面互联规划": "参数面端口互联",
    "存储管理面互联规划": "存储管理面端口互联",
    "存储业务面互联规划": "存储业务面端口互联",
    "存储样本面互联规划": "样本面端口互联 | 数据面端口互联",
    "计算带外管理互联规划": "计算带外管理面端口互联",
    "计算带外管理面互联规划": "计算带外管理面端口互联",
    "存储带外管理互联规划": "存储带外管理面端口互联",
    "存储带外管理面互联规划": "存储带外管理面端口互联",
    "网络带外管理互联规划": "网络带外管理面端口互联",
    "网络带外管理面互联规划": "网络带外管理面端口互联",
    "灵衢带外管理互联规划": "灵衢带外管理面端口互联",
    "灵衢带外管理面互联规划": "灵衢带外管理面端口互联",
}


def coerce_sheet_spec(sheet: object) -> object:
    if sheet is None:
        return None
    s = str(sheet).strip()
    if s.lower() in ("", "auto"):
        return None
    if s.isdigit():
        return int(s)
    return sheet


def find_header_row(raw: pd.DataFrame) -> int:
    header_mask = raw.astype(str).apply(
        lambda row: row.str.contains("设备命名", case=False).any(), axis=1
    )
    if not header_mask.any():
        raise ValueError("未找到包含'设备命名'的行，请检查表格内容")
    return int(header_mask.idxmax())


def read_network_resource_df(path: Path, sheet_index: int = 0) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=RESOURCE_SHEET_NAME, header=0)
    except Exception:
        return pd.read_excel(path, sheet_name=sheet_index, header=0)


def get_net_to_gateway(path: Path, sheet_index: int = 0) -> Dict[str, str]:
    df = read_network_resource_df(path, sheet_index)
    if "网络平面" not in df.columns:
        raise ValueError("资源表缺少列：网络平面")
    gw_col = None
    for col in df.columns:
        if re.search(r"网关位置", str(col), re.I):
            gw_col = col
            break
    if gw_col is None:
        raise ValueError(f"资源表缺少列：{GATEWAY_POSITION_COL}")
    cleaned = df[["网络平面", gw_col]].dropna(subset=[gw_col])
    return {
        str(k).strip(): str(v).strip()
        for k, v in zip(cleaned["网络平面"], cleaned[gw_col])
    }


def detect_ni_layer(
    path: Path, net_plane: str, sheet_index: int = 0
) -> Tuple[str, str, str]:
    """
    自动识别 L2/L3，对齐 main_flow.execute_three_instruction：

    instruction += '_L3' if gateway == 'LEAF' else '_L2'

    - 网关位置* == LEAF → L3 → a3_ni_ip_address.a3_ni_ip_generate
    - 其它（如 SPINE）→ L2 → a3_l2_net_interconnection.a3_net_interconnection_generate
    """
    net_to_gateway = get_net_to_gateway(path, sheet_index)
    gateway_pos = net_to_gateway.get(net_plane)
    if gateway_pos is None or not str(gateway_pos).strip():
        raise ValueError(
            f"资源表未找到 网络平面={net_plane!r} 的 {GATEWAY_POSITION_COL}，"
            f"已有平面: {list(net_to_gateway.keys())}"
        )
    gw = str(gateway_pos).strip()
    if gw == "LEAF":
        return (
            "L3",
            gw,
            "网关位置*=LEAF → 三层互联 → *_互联规划_L3 → a3_ni_ip_address.py",
        )
    return (
        "L2",
        gw,
        f"网关位置*={gw!r} → 二层互联 → *_互联规划_L2 → a3_l2_net_interconnection.py",
    )


def resolve_intent(intent: str) -> Tuple[str, str, str]:
    """(三级指令, connect_sheet_key, network_type)"""
    intent = intent.strip()
    if intent not in INTERCONNECTION_INTENTS:
        known = ", ".join(sorted(INTERCONNECTION_INTENTS))
        raise ValueError(f"未知互联规划指令: {intent!r}。支持: {known}")
    sheet_key = INTERCONNECTION_INTENTS[intent]
    if sheet_key not in LEAF_SPINE_CONFIG:
        raise ValueError(f"连线表 sheet {sheet_key!r} 未在 LEAF_SPINE_CONFIG 中配置")
    network_type = LEAF_SPINE_CONFIG[sheet_key]["network_type"]
    return intent, sheet_key, network_type


def _sheet_name_matches(target: str, candidate: str) -> bool:
    """支持「存储面端口互联 | 样本面端口互联」与 sheet 名互含匹配。"""
    t = str(target).strip()
    c = str(candidate).strip()
    if t == c or t in c or c in t:
        return True
    parts = [p.strip() for p in t.split("|") if p.strip()]
    return any(p in c or c in p for p in parts)


def resolve_connect_sheet(path: Path, sheet_key: str, sheet: object) -> object:
    spec = coerce_sheet_spec(sheet)
    xf = pd.ExcelFile(path)
    if spec is not None:
        return spec
    for name in xf.sheet_names:
        if _sheet_name_matches(sheet_key, name):
            return name
    raise ValueError(
        f"未在 {path.name} 中找到与 {sheet_key!r} 匹配的 sheet。"
        f" 可用: {xf.sheet_names}"
    )


def read_connect_raw(path: Path, sheet: object) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet, header=None, dtype=str).fillna("")


def get_switch_data_l2(
    df_all: pd.DataFrame, keyword: str
) -> Tuple[pd.DataFrame, int]:
    """对齐 a3_l2_net_interconnection.get_switch_data（含带宽列）。"""
    header_row_idx = find_header_row(df_all)
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
            f'`leaf交换机`.str.contains("{keyword}", case=False, na=False) '
            f'& `spine交换机`.str.contains("spine", case=False, na=False)'
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
    """对齐 a3_ni_ip_address.get_switch_data。"""
    header_row_idx = find_header_row(df_all)
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
            f'`leaf交换机`.str.contains("{keyword}", case=False, na=False) '
            f'& `spine交换机`.str.contains("spine", case=False, na=False)'
        )
        .drop_duplicates()
    )
    row_count = result_df.shape[0]
    if row_count == 0:
        raise ValueError(
            f"未找到包含'{keyword}'关键字的行，未找到从LEAF到SPINE的物理连线，请检查连线表"
        )
    return result_df, row_count


def get_switch_mlag_data(df_all: pd.DataFrame) -> pd.DataFrame:
    """对齐 a3_l2_net_interconnection._get_all_switch_mlag_data。"""
    header_row_idx = find_header_row(df_all)
    df = df_all.iloc[header_row_idx + 1 :].reset_index(drop=True)
    df = df.rename(
        columns={df.columns[0]: "设备", df.columns[1]: "接口", df.columns[-1]: "接入交换机"}
    )
    switch_df = df[df["设备"].astype(str).str.contains("leaf|spine", case=False, na=False)]
    leaf_mask = switch_df["设备"].str.contains("leaf", case=False) & switch_df[
        "接入交换机"
    ].str.contains("leaf", case=False)
    spine_mask = switch_df["设备"].str.contains("spine", case=False) & switch_df[
        "接入交换机"
    ].str.contains("spine", case=False)
    switch_df = switch_df.copy()
    switch_df["标记"] = ""
    switch_df.loc[leaf_mask | spine_mask, "标记"] = "MLAG"
    leaf_result_df = switch_df[["设备", "接入交换机", "标记"]].drop_duplicates()
    return leaf_result_df[leaf_result_df["标记"] == "MLAG"]


def read_vlan_for_plane(path: Path, net_plane: str, sheet_index: int = 0):
    """L2：对齐 utils.get_net_ni_resource_info → VLAN*。"""
    df = read_network_resource_df(path, sheet_index)
    row = df[df["网络平面"].astype(str) == net_plane]
    if row.empty:
        raise ValueError(f"未找到{net_plane}所在行。")
    vlan_col = VLAN_COL
    if vlan_col not in df.columns:
        for col in df.columns:
            if re.match(r"VLAN", str(col), re.I):
                vlan_col = col
                break
    vlan = row[vlan_col].values[0]
    if pd.isna(vlan) or not str(vlan).strip():
        raise ValueError(f"{net_plane} {VLAN_COL} 为空。")
    return vlan


def read_interconnect_pool_for_plane(
    path: Path, net_plane: str, sheet_index: int = 0
) -> List[str]:
    """L3：对齐 a3_ni_ip_address.get_net_ni_resource_info → 内部网络设备互连地址段。"""
    df = read_network_resource_df(path, sheet_index)
    row = df[df["网络平面"].astype(str) == net_plane]
    if row.empty:
        raise ValueError(f"未找到{net_plane}所在行。")
    pool_col = INTERCONNECT_POOL_COL
    if pool_col not in df.columns:
        for col in df.columns:
            if "互连地址段" in str(col):
                pool_col = col
                break
    ip_pool = row[pool_col].values[0]
    if pd.isna(ip_pool) or not str(ip_pool).strip():
        raise ValueError(f"{net_plane}{INTERCONNECT_POOL_COL}为空。")
    return str(ip_pool).split("-")


def collect_used_trunks_from_prior(prior_path: Optional[Path]) -> List[int]:
    """离线替代 assigned_trunk_list：从已有互连/接入规划表收集已用 ETH-TRUNK 编号。"""
    if prior_path is None or not prior_path.is_file():
        return []
    trunks: List[int] = []
    try:
        df = pd.read_excel(prior_path, sheet_name=0, header=0)
        for col in ("本端ETH-TRUNK", "对端ETH-TRUNK", "ETH-TRUNK"):
            if col in df.columns:
                for v in df[col].dropna().unique():
                    try:
                        trunks.append(int(v))
                    except (TypeError, ValueError):
                        pass
    except Exception:
        pass
    return trunks
