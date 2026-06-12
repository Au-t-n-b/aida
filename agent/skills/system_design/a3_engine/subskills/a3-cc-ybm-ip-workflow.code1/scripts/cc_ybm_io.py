"""读取存储样本面端口互联表与资源表（对齐 a3_cc_ybm_ip_address.py）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

STORAGE_NAME_KEYWORD = ["OSP9950", "OSP9550", "OSP9920", "OSA800", "OD1600T", "OD1301"]
NET_PLANE = "存储样本面"
NET_PLANE_OD1600T = "OceanDisk样本面"
WEB_NETWORK_TYPE_NAME = "存储样本面"
SHEET_CONNECT_PREFERRED = "样本面端口互联 | 数据面端口互联"
SHEET_COMPUTE_MANAGE_FALLBACK = "计算管理面端口互联"
RESOURCE_SHEET_NAME = "网络资源需求表"
GATEWAY_POSITION_COL = "网关位置*"


def _storage_pattern() -> str:
    return "|".join(map(re.escape, STORAGE_NAME_KEYWORD))


def coerce_sheet_spec(sheet: object) -> object:
    if sheet is None:
        return None
    s = str(sheet).strip()
    if s.lower() in ("", "auto"):
        return None
    if s.isdigit():
        return int(s)
    return sheet


def find_header_row(df: pd.DataFrame, needle: str = "设备命名") -> int:
    for idx, row in df.iterrows():
        if row.astype(str).str.contains(needle, case=False, na=False).any():
            return int(idx)
    raise ValueError(f"未找到包含{needle!r}的行，请检查表格内容")


def _sheet_has_connectivity_data(path: Path, sheet: object) -> bool:
    try:
        raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str).fillna("")
        find_header_row(raw)
        data = raw.iloc[find_header_row(raw) + 1 :]
        if data.shape[1] < 3 or data.empty:
            return False
        pattern = _storage_pattern()
        first_col = data.iloc[:, 0].astype(str)
        return bool(first_col.str.contains(pattern, na=False).any())
    except Exception:
        return False


def _is_ybm_connect_sheet_name(name: str) -> bool:
    """匹配 main_flow sheet「样本面端口互联 | 数据面端口互联」或简写「样本面端口互联」。"""
    n = str(name).strip()
    if SHEET_CONNECT_PREFERRED in n:
        return True
    if "样本面" in n and "数据面" in n:
        return True
    if n == "样本面端口互联":
        return True
    return False


def resolve_connect_sheet(path: Path, sheet: object) -> object:
    spec = coerce_sheet_spec(sheet)
    if spec is not None:
        if _sheet_has_connectivity_data(path, spec):
            return spec
        xf = pd.ExcelFile(path)
        raise ValueError(
            f"指定 sheet {spec!r} 无法读取存储样本面互联数据。"
            f" 可用 sheet: {xf.sheet_names}"
        )

    xf = pd.ExcelFile(path)
    # 优先「样本面 | 数据面」互联 sheet，避免误选存储业务面等同设备表
    for name in xf.sheet_names:
        if _is_ybm_connect_sheet_name(name) and _sheet_has_connectivity_data(path, name):
            return name

    for i, name in enumerate(xf.sheet_names):
        if _is_ybm_connect_sheet_name(name) and _sheet_has_connectivity_data(path, i):
            return name

    for i, name in enumerate(xf.sheet_names):
        if _sheet_has_connectivity_data(path, i):
            return name

    raise ValueError(
        f"未在 {path.name} 中找到含「设备命名」且含存储设备（{STORAGE_NAME_KEYWORD}）的 sheet。"
        f" 可用 sheet: {xf.sheet_names}"
    )


def read_connectivity_raw(path: Path, sheet: object) -> pd.DataFrame:
    resolved = resolve_connect_sheet(path, sheet)
    raw = pd.read_excel(path, sheet_name=resolved, header=None, dtype=str).fillna("")
    header_idx = find_header_row(raw)
    return raw.iloc[header_idx + 1 :].reset_index(drop=True)


def _extract_node(interface: object) -> str:
    s = str(interface)
    if "node" in s.lower():
        try:
            return s.split("/")[0].split("-")[0]
        except IndexError:
            return s
    return s


def get_node_info(path: Path, sheet: object) -> pd.DataFrame:
    """对齐 a3_cc_ybm_ip_address.get_node_info。"""
    df = read_connectivity_raw(path, sheet)
    if df.shape[1] < 3:
        raise ValueError("端口互联表至少需要 3 列（起始端设备、接口、目的端）")
    equip = df.iloc[:, [0, 1, -1]].copy()
    equip.columns = ["起始端设备", "起始端接口名称", "目的端设备"]
    equip = equip[equip["起始端设备"].str.contains(_storage_pattern(), na=False)].copy()
    equip["节点名称"] = equip["起始端设备"] + "-" + equip["起始端接口名称"].map(_extract_node)
    return equip[["节点名称", "目的端设备"]]


def get_server_info_od1600t(path: Path, sheet: object) -> pd.DataFrame:
    """对齐 a3_cc_ybm_ip_address.get_server_info（OD1600T 四列互联）。"""
    df = read_connectivity_raw(path, sheet)
    if df.shape[1] < 4:
        raise ValueError("OD1600T 互联表至少需要 4 列")
    equip = df.iloc[:, [0, 1, -2, -1]].copy()
    equip.columns = ["本端设备名称", "本端接口名称", "对端接口名称", "对端设备名称"]
    return equip[equip["本端设备名称"].str.contains("OD1600T", na=False)].copy()


def get_switch_to_nodes(path: Path, sheet: object) -> Dict[str, List[str]]:
    """对齐 get_switch_info：起始端设备去重，IP 需求 = 设备数 × 8。"""
    df = read_connectivity_raw(path, sheet)
    work = df.iloc[:, [0, df.columns[-1]]].copy()
    work.columns = ["起始端设备", "leaf交换机"]
    work = work[work["起始端设备"].str.contains(_storage_pattern(), na=False)]
    work = work.drop_duplicates(subset=["起始端设备"], keep="first")
    out: Dict[str, List[str]] = {}
    for leaf, g in work.groupby("leaf交换机", sort=False):
        out[str(leaf)] = [str(x) for x in g["起始端设备"].tolist() if str(x).strip()]
    return out


def switch_demand_markdown(switch_to_nodes: Dict[str, List[str]], header: str) -> str:
    from cc_ybm_segment_rules import ip_demand_for_nodes

    lines = [f"|{header}|IP数量|", "|--------|-------|"]
    for sw, devices in switch_to_nodes.items():
        lines.append(f"|{sw}|{ip_demand_for_nodes(len(devices))}|")
    return "\n".join(lines)


def read_network_resource_df(path: Path, sheet_index: int = 0) -> pd.DataFrame:
    xf = pd.ExcelFile(path)
    if RESOURCE_SHEET_NAME in xf.sheet_names:
        return pd.read_excel(path, sheet_name=RESOURCE_SHEET_NAME, header=0)
    if 0 <= sheet_index < len(xf.sheet_names):
        return pd.read_excel(path, sheet_name=sheet_index, header=0)
    raise ValueError(
        f"资源表缺少 sheet {RESOURCE_SHEET_NAME!r}，可用: {xf.sheet_names}"
    )


def get_net_to_gateway(path: Path, sheet_index: int = 0) -> Dict[str, str]:
    df = read_network_resource_df(path, sheet_index)
    if "网络平面" not in df.columns:
        raise ValueError("资源表缺少列：网络平面")
    gw_col = GATEWAY_POSITION_COL
    if gw_col not in df.columns:
        alt = [c for c in df.columns if "网关位置" in str(c)]
        if not alt:
            raise ValueError(f"资源表缺少列：{GATEWAY_POSITION_COL}")
        gw_col = alt[0]
    cleaned = df[["网络平面", gw_col]].dropna(subset=[gw_col])
    return {
        str(k).strip(): str(v).strip()
        for k, v in zip(cleaned["网络平面"], cleaned[gw_col])
    }


def detect_cc_ybm_layer(path: Path, sheet_index: int = 0) -> Tuple[str, str, str]:
    """
    自动识别 L2/L3（与 main_flow / a3-cc-ywm-ip-workflow 一致）：

    - 网关位置* == LEAF → L3 → a3_cc_ybm_ip_address.py
    - 其它（如 SPINE）→ L2 → I2 网段规划 + 同脚本 OSP/OSA800 分配语义
      （在线 L2 暂为 a3_ni_ip_generate，待 a3_l2_cc_ybm_ip_address 落地）
    """
    net_to_gateway = get_net_to_gateway(path, sheet_index)
    gateway_pos = net_to_gateway.get(NET_PLANE)
    if gateway_pos is None or not str(gateway_pos).strip():
        raise ValueError(
            f"资源表未找到 网络平面={NET_PLANE!r} 的 {GATEWAY_POSITION_COL}，"
            f"已有平面: {list(net_to_gateway.keys())}"
        )
    gw = str(gateway_pos).strip()
    if gw == "LEAF":
        return (
            "L3",
            gw,
            "网关位置*=LEAF → LEAF接入三层 → 存储样本面地址规划_L3 → a3_cc_ybm_ip_address.py",
        )
    return (
        "L2",
        gw,
        f"网关位置*={gw!r} → LEAF接入二层 → 存储样本面地址规划_L2 → "
        f"I2网段(a3_l2_cc_ywm 同类) + a3_cc_ybm 分配逻辑",
    )


def read_resource_row(path: Path, sheet_index: int = 0) -> Tuple[pd.Series, str]:
    df = read_network_resource_df(path, sheet_index)
    if "网络平面" not in df.columns:
        raise ValueError("资源表缺少列：网络平面")
    rows = df[df["网络平面"].astype(str) == NET_PLANE]
    if rows.empty:
        raise ValueError(f"资源表未找到 网络平面 == {NET_PLANE!r} 的行")
    r = rows.iloc[0]
    pool = str(r.get("地址池*", "")).strip()
    if not pool:
        raise ValueError("地址池* 为空")
    return r, pool


def read_od1600t_resource_row(path: Path, sheet_index: int = 0) -> Tuple[pd.Series, str]:
    df = read_network_resource_df(path, sheet_index)
    rows = df[df["网络平面"].astype(str) == NET_PLANE_OD1600T]
    if rows.empty:
        raise ValueError(f"资源表未找到 网络平面 == {NET_PLANE_OD1600T!r} 的行")
    r = rows.iloc[0]
    pool = str(r.get("地址池*", "")).strip()
    if not pool:
        raise ValueError("OceanDisk样本面 地址池* 为空")
    return r, pool


def fuzzy_column_value(row: pd.Series, needle: str) -> object:
    for k in row.index:
        if needle in str(k):
            return row.get(k)
    raise ValueError(f"资源表缺少匹配 {needle!r} 的列")


def net_resource_markdown(row: pd.Series) -> str:
    mask = fuzzy_column_value(row, "最小规划掩码")
    return (
        "|网络平面|地址池|掩码|网关|VLAN|\n"
        "|---|---|---|---|---|\n"
        f"|{NET_PLANE}|{row.get('地址池*','')}|{mask}|{row.get('网关地址*','')}|{row.get('VLAN*','')}|\n"
    )


def classify_device_scenario(node_df: pd.DataFrame) -> str:
    """
    对齐 a3_cc_ybm_ip_address_generate 分支优先级：
    OD1600T > OSA800 > OSP（默认）
    """
    names = node_df["节点名称"].astype(str)
    if names.str.contains("OD1600T", case=False, na=False).any():
        return "od1600t"
    if names.str.contains("OSA800", case=False, na=False).any():
        return "osa800_only"
    if names.str.contains("OSP9950|OSP9550|OSP9920|OSP", case=False, na=False).any():
        return "osp_only"
    raise ValueError(
        f"端口互联表中未找到 OD1600T / OSA800 / OSP 存储设备（关键字 {STORAGE_NAME_KEYWORD}）"
    )


def read_leaf_spine_mapping(
    path: Path,
    sheet: object,
    target_leafs: List[str],
) -> Dict[str, List[str]]:
    df = read_connectivity_raw(path, sheet)
    if df.shape[1] < 2:
        return {}
    work = df.iloc[:, [0, df.columns[-1]]].copy()
    work.columns = ["leaf", "spine"]
    targets = set(target_leafs)
    out: Dict[str, List[str]] = {}
    for _, row in work.iterrows():
        leaf = str(row["leaf"]).strip()
        spine = str(row["spine"]).strip()
        if "LEAF" not in leaf.upper() or leaf not in targets or not spine:
            continue
        out.setdefault(leaf, [])
        if spine not in out[leaf]:
            out[leaf].append(spine)
    return out


def resolve_leaf_spine_mapping(
    path: Path,
    sheet: object,
    target_leafs: List[str],
    fallback_sheet: Optional[object] = None,
) -> Dict[str, List[str]]:
    mapping = read_leaf_spine_mapping(path, sheet, target_leafs)
    if mapping:
        return mapping
    if fallback_sheet is not None:
        return read_leaf_spine_mapping(path, fallback_sheet, target_leafs)
    return {}
