"""读取计算参数面端口互联表与资源表；A2/A3 场景自动识别（对齐 a3_csm_ip_address / csm_ip_address）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

_SCRIPTS = Path(__file__).resolve().parent
_SUBSKILLS = _SCRIPTS.parents[1]
if str(_SUBSKILLS) not in sys.path:
    sys.path.insert(0, str(_SUBSKILLS))

from _runtime_shared.connect_007_structured import (  # noqa: E402
    find_header_row,
    read_server_leaf_connect,
    try_read_structured,
    pick_column,
)

# 对齐 config.py
A2_SERVER_NAME_KEYWORD = "AT800TA2|AT800IA2|AT900A2"
A3_SERVER_NAME_KEYWORD = "AT800TA3|AT800IA3|AT900A3"
SERVER_NAME_KEYWORD = (
    "AT900A3|AT900|AT800TA3|AT800IA3|AT800TA2|AT800IA2|CCAE|NCEFI|NCEFB|DME|K8SM|K8SW|MINDIE"
)

NET_PLANE = "计算参数面"
WEB_NETWORK_TYPE_NAME = "计算参数面"
SHEET_CONNECT_PREFERRED = "参数面端口互联"
RESOURCE_SHEET_NAME = "网络资源需求表"

def coerce_sheet_spec(sheet: object) -> object:
    if sheet is None:
        return None
    s = str(sheet).strip()
    if s.lower() in ("", "auto"):
        return None
    if s.isdigit():
        return int(s)
    return sheet


def _sheet_has_csm_data(path: Path, sheet: object) -> bool:
    try:
        structured = try_read_structured(path, sheet)
        if structured is not None:
            src = pick_column(structured, "起始端信息-设备命名", "设备命名")
            names = structured[src].astype(str)
            return bool(
                names.str.contains(SERVER_NAME_KEYWORD, case=False, na=False, regex=True).any()
            )
        raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str).fillna("")
        header_idx = find_header_row(raw)
        data = raw.iloc[header_idx + 1 :]
        if data.shape[1] < 2 or data.empty:
            return False
        # 扁平行：首列或次列含服务器名（次列为建模仿真误用扁平行时）
        for col_idx in (0, 1):
            if col_idx >= data.shape[1]:
                continue
            names = data.iloc[:, col_idx].astype(str)
            if names.str.contains(SERVER_NAME_KEYWORD, case=False, na=False, regex=True).any():
                return True
        return False
    except Exception:
        return False


def resolve_connect_sheet(path: Path, sheet: object) -> object:
    spec = coerce_sheet_spec(sheet)
    if spec is not None:
        if _sheet_has_csm_data(path, spec):
            return spec
        xf = pd.ExcelFile(path)
        raise ValueError(
            f"指定 sheet {spec!r} 无法读取计算参数面互联数据。可用 sheet: {xf.sheet_names}"
        )

    xf = pd.ExcelFile(path)
    for name in xf.sheet_names:
        if SHEET_CONNECT_PREFERRED in str(name):
            if _sheet_has_csm_data(path, name):
                return name

    for i, name in enumerate(xf.sheet_names):
        if _sheet_has_csm_data(path, i):
            return name

    raise ValueError(
        f"未在 {path.name} 中找到含「设备命名」且含计算服务器（{SERVER_NAME_KEYWORD}）的 sheet。"
        f" 可用 sheet: {xf.sheet_names}"
    )


def read_connectivity_raw(path: Path, sheet: object) -> pd.DataFrame:
    resolved = resolve_connect_sheet(path, sheet)
    return read_server_leaf_connect(path, resolved, server_keyword=SERVER_NAME_KEYWORD)


def read_network_resource_df(path: Path, sheet_index: int = 0) -> pd.DataFrame:
    xf = pd.ExcelFile(path)
    if RESOURCE_SHEET_NAME in xf.sheet_names:
        return pd.read_excel(path, sheet_name=RESOURCE_SHEET_NAME, header=0, dtype=str).fillna("")
    return pd.read_excel(path, sheet_name=sheet_index, header=0, dtype=str).fillna("")


def fuzzy_column_value(row: pd.Series, needle: str) -> object:
    for k in row.index:
        if needle in str(k):
            return row.get(k)
    raise ValueError(f"资源表缺少匹配 {needle!r} 的列")


def gateway_mode_from_row(row: pd.Series) -> object:
    """A2 用 网关位置*；A3 用 网关地址*（与两脚本 get_net_resource_info 一致）。"""
    for col in ("网关地址*", "网关位置*"):
        if col in row.index and str(row.get(col, "")).strip():
            return row.get(col)
    return fuzzy_column_value(row, "网关")


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


def net_resource_markdown(row: pd.Series, scenario: str) -> str:
    mask = fuzzy_column_value(row, "最小规划掩码")
    gw_col = "网关位置*" if scenario == "a2" else "网关地址*"
    gw = row.get(gw_col, "")
    if not str(gw).strip():
        gw = gateway_mode_from_row(row)
    return (
        "|网络平面|地址池|掩码|网关|VLAN|\n"
        "|---|---|---|---|---|\n"
        f"|{NET_PLANE}|{row.get('地址池*','')}|{mask}|{gw}|{row.get('VLAN*','')}|\n"
    )


def detect_csm_scenario(path: Path, sheet: object) -> Tuple[str, str, str]:
    """
    对齐 a3_csm_ip_generate 中 process_excel_or_db_data + 起始端信息-设备命名 判断：

    - 任一设备名匹配 A2 关键字 → a2 → csm_ip_address.py（优先于 A3）
    - 否则任一匹配 A3 → a3
    - 否则报错
    """
    df = read_connectivity_raw(path, sheet)
    names = df["计算服务器"].astype(str)
    has_a2 = bool(names.str.contains(A2_SERVER_NAME_KEYWORD, case=False, na=False, regex=True).any())
    has_a3 = bool(names.str.contains(A3_SERVER_NAME_KEYWORD, case=False, na=False, regex=True).any())
    if has_a2:
        return (
            "a2",
            A2_SERVER_NAME_KEYWORD,
            "端口表含 A2 服务器 → csm_ip_address.csm_ip_generate（优先于 A3）",
        )
    if has_a3:
        return (
            "a3",
            A3_SERVER_NAME_KEYWORD,
            "端口表含 A3 服务器 → a3_csm_ip_address.a3_csm_ip_generate",
        )
    raise ValueError("计算参数面端口互联中未匹配到 A2 和 A3 机器")


def _filter_servers(df: pd.DataFrame, pattern: str) -> pd.DataFrame:
    sub = df[df["计算服务器"].astype(str).str.contains(pattern, case=False, na=False, regex=True)]
    return sub.drop_duplicates()


def infer_rail_mode(result_df: pd.DataFrame) -> int:
    if result_df.empty:
        return 2
    n = int(result_df.groupby("计算服务器", sort=False)["leaf交换机"].nunique().max())
    if n >= 8:
        return 8
    if n >= 4:
        return 4
    if n >= 2:
        return 2
    return 2


def canonical_leaf_order(result_df: pd.DataFrame) -> List[str]:
    seen = set()
    out: List[str] = []
    for leaf in result_df["leaf交换机"].dropna().astype(str).str.strip():
        lf = str(leaf).strip()
        if lf and lf not in seen:
            seen.add(lf)
            out.append(lf)
    return out


def extract_sp_and_index(server_name: str) -> Tuple[float, float]:
    sp_part = re.search(r"SP(\d+)", str(server_name))
    idx_part = re.search(r"-(\d+)$", str(server_name))
    sp_num = int(sp_part.group(1)) if sp_part else float("inf")
    index = int(idx_part.group(1)) if idx_part else float("inf")
    return sp_num, index


def extract_pic_channel(port: str) -> int:
    s = str(port).strip().upper()
    parts = s.split("/")
    if parts:
        try:
            return int(parts[-1].strip())
        except ValueError:
            pass
    m = re.search(r"(\d+)\s*$", s)
    return int(m.group(1)) if m else 0


def min_device_id_for_port(port: str) -> int:
    return 8 - extract_pic_channel(port)


def build_switch_to_servers_ordered(
    result_df: pd.DataFrame, leaf_order: List[str]
) -> Dict[str, List[Tuple[str, str]]]:
    out: Dict[str, List[Tuple[str, str]]] = {}
    for leaf in leaf_order:
        sub = result_df[result_df["leaf交换机"].astype(str).str.strip() == str(leaf).strip()]
        pairs = list(dict.fromkeys(zip(sub["计算服务器"], sub["服务器端口"])))
        pairs.sort(
            key=lambda t: (
                extract_sp_and_index(t[0]),
                min_device_id_for_port(t[1]),
                -extract_pic_channel(t[1]),
            )
        )
        out[leaf] = pairs
    return out


def get_a3_topology(
    path: Path, sheet: object
) -> Tuple[str, Dict[str, List[Tuple[str, str]]], List[str], int]:
    """对齐 a3_csm_ip_address.get_switch_info。"""
    df = _filter_servers(read_connectivity_raw(path, sheet), A3_SERVER_NAME_KEYWORD)
    rail_mode = infer_rail_mode(df)
    leaf_order = canonical_leaf_order(df)
    lines = ["|交换机|IP数量|", "|--------|-------|"]
    for leaf in leaf_order:
        sub = df[df["leaf交换机"].astype(str).str.strip() == str(leaf).strip()]
        link_cnt = len(sub.drop_duplicates(subset=["计算服务器", "服务器端口"]))
        lines.append(f"|{leaf}|{link_cnt * 2}|")
    switch_to_servers = build_switch_to_servers_ordered(df, leaf_order)
    return "\n".join(lines), switch_to_servers, leaf_order, rail_mode


def get_a2_switch_demand_markdown(path: Path, sheet: object) -> Tuple[str, List[str]]:
    """对齐 csm_ip_address.get_switch_info（SERVER_NAME_KEYWORD，IP数量=行数×2）。"""
    df = _filter_servers(read_connectivity_raw(path, sheet), SERVER_NAME_KEYWORD)
    switch_counts = df.groupby("leaf交换机", sort=False)["计算服务器"].count().reset_index()
    switch_counts.columns = ["leaf交换机", "节点数量"]
    switch_counts["节点数量"] = switch_counts["节点数量"] * 2
    leaf_order = list(switch_counts["leaf交换机"].astype(str))
    lines = ["|交换机|IP数量|", "|--------|-------|"]
    for _, row in switch_counts.iterrows():
        lines.append(f"|{row['leaf交换机']}|{row['节点数量']}|")
    return "\n".join(lines), leaf_order


def get_a2_server_leaf_df(path: Path, sheet: object) -> pd.DataFrame:
    """对齐 csm_ip_address.get_server_data（不过滤 A2/A3，全表去重）。"""
    df = read_connectivity_raw(path, sheet)
    out = df[["计算服务器", "leaf交换机"]].drop_duplicates()
    return out


def leaf_order_from_demand_md(md: str) -> List[str]:
    lines = [ln for ln in md.splitlines() if ln.startswith("|") and "---" not in ln]
    if len(lines) <= 1:
        return []
    out: List[str] = []
    for ln in lines[2:]:
        parts = [p.strip() for p in ln.strip("|").split("|")]
        if parts and parts[0]:
            out.append(parts[0])
    return out
