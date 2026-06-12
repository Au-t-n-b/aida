"""端口互联 / 资源表读取与平面自动识别（对齐 config.LOOPBACK_CONFIG / WEB_NETWORK_TYPE_CONFIG）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

# 常见非 ASCII 连字符，归一为 '-'（便于识别 65001-65099）
_DASH_NORMALIZE_PATTERN = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uff0d~～至到]+")

# 对齐 src/manage_agent/sub_agents/LLD_IP/config.py
LOOPBACK_CONFIG: Dict[str, Dict[str, str]] = {
    "参数面端口互联": {"keyword": "LEAF", "network_type": "计算参数面"},
    "计算管存面端口互联": {"keyword": "GCM-LEAF", "network_type": "计算管存面"},
    "计算业务面端口互联": {"keyword": "YWM-LEAF", "network_type": "计算业务面"},
    "计算管理面端口互联": {"keyword": "GLM-LEAF", "network_type": "计算管理面"},
    "存储面端口互联 | 样本面端口互联": {"keyword": "ZSYBM-LEAF", "network_type": "计算样本面"},
    "样本面端口互联 | 数据面端口互联": {"keyword": "CCYBM-LEAF", "network_type": "存储样本面"},
    "存储管理面端口互联": {"keyword": "CCGLM-LEAF", "network_type": "存储管理面"},
    "存储业务面端口互联": {"keyword": "CCYWM-LEAF", "network_type": "存储业务面"},
}

WEB_NETWORK_TYPE_CONFIG: Dict[str, str] = {
    "存储面端口互联 | 样本面端口互联": "计算样本面",
    "计算管理面端口互联": "计算管理面",
    "计算业务面端口互联": "计算业务面",
    "计算管存面端口互联": "计算管存面",
    "参数面端口互联": "计算参数面",
    "样本面端口互联 | 数据面端口互联": "存储样本面",
    "存储业务面端口互联": "存储业务面",
    "存储管理面端口互联": "存储管理面",
}

LOOPBACK_SHEET_ORDER: List[str] = list(LOOPBACK_CONFIG.keys())
RESOURCE_SHEET_NAME = "网络资源需求表"
OUTPUT_ASN_XLSX = "A3交换机ASN规划.xlsx"
OUTPUT_ASN_SHEET = "交换机ASN规划"


@dataclass
class PlanePlan:
    sheet_connect: str
    config_key: str
    keyword: str
    network_type: str
    web_network_type_name: str
    as_range_str: str


@dataclass
class GatewayRecord:
    """内存网关表，字段下标与线上一致：scope=3, name=4, network_segment=5, ebgp_as=6, vlan=7."""

    scope: str
    name: str
    network_segment: str = "NA"
    ebgp_as: str = "NA"
    vlan: str = "NA"
    extend: str = "NA"

    def as_tuple(self) -> Tuple[object, ...]:
        """对齐 T_GATEWAY_INFO query：ID, USER_ID, PROJECT_ID, SCOPE, NAME, NETWORK_SEGMENT, EBGP_AS, VLAN, EXTEND."""
        return (
            0,
            "",
            "",
            self.scope,
            self.name,
            self.network_segment,
            self.ebgp_as,
            self.vlan,
            self.extend,
        )


class InMemoryGatewayStore:
    """替代 gateway_info_db，供离线跨平面 AS 冲突检测与 ASN 汇总。"""

    def __init__(self, records: Optional[List[GatewayRecord]] = None) -> None:
        self._records: List[GatewayRecord] = list(records or [])

    def query_all(self) -> List[Tuple[str, str, str, str, str, str, str, str]]:
        return [r.as_tuple() for r in self._records]

    def delete_by_scope(self, scope: str) -> None:
        self._records = [r for r in self._records if r.scope != scope]

    def upsert_scope_from_allocation(
        self,
        scope: str,
        allocation_rows: Sequence[Dict[str, str]],
    ) -> None:
        self.delete_by_scope(scope)
        for row in allocation_rows:
            raw_as = row.get("BGP AS", "")
            if raw_as is None or str(raw_as).strip() == "":
                asn = ""
            elif str(raw_as).strip().upper() == "NA":
                asn = "NA"
            else:
                asn = str(raw_as).strip()
            self._records.append(
                GatewayRecord(
                    scope=scope,
                    name=str(row["设备名称"]),
                    network_segment="NA",
                    ebgp_as=asn,
                    vlan="NA",
                    extend="NA",
                )
            )

    def merge_snapshot(self, other: "InMemoryGatewayStore") -> None:
        for r in other._records:
            self.delete_by_scope(r.scope)
        self._records.extend(other._records)

    def ensure_devices(
        self,
        scope: str,
        device_names: Sequence[str],
        *,
        default_ebgp_as: str = "",
    ) -> None:
        """为导出预置设备行（ebgp 为空字符串，对齐库中非 'NA' 但 ASN 为空的记录）。"""
        existing = {r.name for r in self._records if r.scope == scope}
        for name in device_names:
            n = str(name).strip()
            if not n or n in existing:
                continue
            ebgp = default_ebgp_as if default_ebgp_as not in ("", None) else ""
            self._records.append(
                GatewayRecord(
                    scope=scope,
                    name=n,
                    network_segment="NA",
                    ebgp_as=ebgp,
                    vlan="NA",
                    extend="NA",
                )
            )
            existing.add(n)


def normalize_ebgp_as_planning(value: object) -> str:
    """清洗 EBGP AS规划 字符串（对齐线上 str(...) 后再判断 '-'）。"""
    s = str(value).strip()
    if s.lower() in ("nan", "none", "na"):
        return ""
    s = _DASH_NORMALIZE_PATTERN.sub("-", s)
    s = re.sub(r"\s*-\s*", "-", s)
    return s


def has_as_range(value: object) -> bool:
    """是否形如 start-end（与 a3_switch_loopback_ip_address 中 `if '-' in as_range_str` 一致）。"""
    s = normalize_ebgp_as_planning(value)
    if "-" not in s:
        return False
    left, _, right = s.partition("-")
    return left.isdigit() and right.isdigit()


def parse_as_range_override_arg(spec: str) -> Tuple[str, str]:
    """
    解析 CLI --as-range，键可为 network_type（如 存储管理面）或 LOOPBACK sheet 名。
    返回 (key, normalized_range)。
    """
    if "=" not in spec:
        raise ValueError(f"--as-range 格式应为「平面=65001-65099」，收到: {spec!r}")
    key, val = spec.split("=", 1)
    key = key.strip()
    val = normalize_ebgp_as_planning(val)
    if not has_as_range(val):
        raise ValueError(f"--as-range 值须为数字区间，例如 65001-65099，收到: {val!r}")
    return key, val


def build_as_range_override_map(specs: Sequence[str]) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    for spec in specs:
        key, val = parse_as_range_override_arg(spec)
        overrides[key] = val
        for config_key, cfg in LOOPBACK_CONFIG.items():
            if key == config_key or key == cfg["network_type"] or key == WEB_NETWORK_TYPE_CONFIG.get(config_key, ""):
                overrides[config_key] = val
                overrides[cfg["network_type"]] = val
                overrides[WEB_NETWORK_TYPE_CONFIG[config_key]] = val
    return overrides


def resolve_as_range_for_plane(
    *,
    network_type: str,
    config_key: str,
    resource_path: Path,
    sheet_res_index: int,
    as_range_overrides: Optional[Dict[str, str]] = None,
) -> Tuple[str, str]:
    """
    返回 (as_range_str, source)，source 为 resource | override。
    """
    if as_range_overrides:
        for k in (network_type, config_key, WEB_NETWORK_TYPE_CONFIG.get(config_key, "")):
            if k and k in as_range_overrides and has_as_range(as_range_overrides[k]):
                return as_range_overrides[k], "override"

    _, raw = get_net_resource_info(resource_path, network_type, sheet_res_index)
    normalized = normalize_ebgp_as_planning(raw)
    return normalized, "resource"


def format_missing_as_range_help(
    *,
    resource_path: Path,
    skipped: Sequence[str],
    as_range_overrides: Optional[Dict[str, str]] = None,
) -> str:
    lines = [
        "未识别到可执行的 ASN 规划平面。",
        "",
        "原因：资源表「网络资源需求表」中下列「网络平面」行的「EBGP AS规划」为空或非 start-end 区间。",
        "（与线上一致：仅当 EBGP AS规划 含 '-' 时才调用 a3_switch_loopback_ip_generate 分配 AS。）",
        "",
        f"资源文件: {resource_path.name}",
        "",
        "需在资源表填写的网络平面（LOOPBACK_CONFIG 对应）示例值：",
    ]
    for config_key in LOOPBACK_SHEET_ORDER:
        if config_key not in LOOPBACK_CONFIG:
            continue
        nt = LOOPBACK_CONFIG[config_key]["network_type"]
        lines.append(f"  - {nt}  →  EBGP AS规划 填写如 65001-65099（sheet: {config_key}）")
    lines.extend(
        [
            "",
            "临时覆盖（不改 Excel）示例：",
            '  python scripts/offline_switch_asn_pipeline.py --only-plane "存储管理面端口互联" --as-range "存储管理面=65001-65099"',
            "",
            "若已在其它地址规划 skill 生成 gateway_snapshot.csv，可仅导出：",
            "  python scripts/offline_switch_asn_pipeline.py --export-only --gateway-snapshot output/run_xxx/gateway_snapshot.csv",
            "",
            "本次跳过明细:",
        ]
    )
    lines.extend(skipped)
    if as_range_overrides:
        lines.append("")
        lines.append(f"已提供的 --as-range 覆盖: {as_range_overrides}")
    return "\n".join(lines)


def coerce_sheet_spec(sheet: object) -> Optional[object]:
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
    raise ValueError(f"未找到包含{needle!r}的行")


def read_connect_raw(path: Path, sheet_name: object) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None, dtype=str).fillna("")
    header_idx = find_header_row(raw)
    df = raw.iloc[header_idx + 1 :].reset_index(drop=True)
    if df.shape[1] < 2:
        raise ValueError("端口互联表列数不足")
    df = df.rename(columns={df.columns[0]: "leaf交换机", df.columns[-1]: "交换机"})
    return df


def get_leaf_spine_data(path: Path, sheet_name: object, keyword: str) -> Tuple[List[str], List[str]]:
    """对齐 a3_switch_loopback_ip_address.get_leaf_spine_data。"""
    df = read_connect_raw(path, sheet_name)
    df_leaf = df[df["交换机"].astype(str).str.contains(keyword, case=False, na=False)]
    df_spine = df[df["交换机"].astype(str).str.contains("spine", case=False, na=False)]
    leafs = df_leaf["交换机"].dropna().astype(str).str.strip().unique().tolist()
    spines = df_spine["交换机"].dropna().astype(str).str.strip().unique().tolist()
    return leafs, spines


def _sheet_has_loopback_devices(path: Path, sheet_name: object, keyword: str) -> bool:
    try:
        leafs, spines = get_leaf_spine_data(path, sheet_name, keyword)
        return bool(leafs or spines)
    except Exception:
        return False


def _match_loopback_sheet(available: Sequence[str], config_key: str) -> Optional[str]:
    if config_key in available:
        return config_key
    for name in available:
        if config_key in str(name) or str(name) in config_key:
            return name
    return None


def read_network_resource_df(path: Path, sheet_index: int = 0) -> pd.DataFrame:
    xf = pd.ExcelFile(path)
    if RESOURCE_SHEET_NAME in xf.sheet_names:
        return pd.read_excel(path, sheet_name=RESOURCE_SHEET_NAME, header=0, dtype=str).fillna("")
    return pd.read_excel(path, sheet_name=sheet_index, header=0, dtype=str).fillna("")


def get_net_resource_info(resource_path: Path, network_type: str, sheet_index: int = 0) -> Tuple[str, str]:
    """对齐 a3_switch_loopback_ip_address.get_net_resource_info。"""
    df = read_network_resource_df(resource_path, sheet_index)
    if "网络平面" not in df.columns:
        raise ValueError("资源表缺少列「网络平面」")
    row = df[df["网络平面"].astype(str).str.strip() == network_type]
    if row.empty:
        raise ValueError(f"未找到{network_type}所在行。")
    ip_pool = str(row["地址池*"].values[0])
    if "EBGP AS规划" not in df.columns:
        raise ValueError("资源表缺少列「EBGP AS规划」")
    ebgp_as = normalize_ebgp_as_planning(row["EBGP AS规划"].values[0])
    return ip_pool, ebgp_as


def detect_plane_plans(
    connect_path: Path,
    resource_path: Path,
    *,
    sheet_res_index: int = 0,
    only_config_key: Optional[str] = None,
    as_range_overrides: Optional[Dict[str, str]] = None,
) -> Tuple[List[PlanePlan], List[str]]:
    """
    自动识别待规划平面（不区分 L2/L3）：
    - 端口文件中存在 LOOPBACK_CONFIG 对应 sheet 且含 keyword/spine 设备
    - 资源表对应 network_type 行存在且 EBGP AS规划 含 '-'（可用 as_range_overrides 覆盖）
    """
    xf = pd.ExcelFile(connect_path)
    available = list(xf.sheet_names)
    plans: List[PlanePlan] = []
    skipped: List[str] = []
    override_notes: List[str] = []

    keys = [only_config_key] if only_config_key else LOOPBACK_SHEET_ORDER
    for config_key in keys:
        if config_key not in LOOPBACK_CONFIG:
            skipped.append(f"{config_key}: 非 LOOPBACK_CONFIG 键")
            continue
        matched = _match_loopback_sheet(available, config_key)
        if not matched:
            skipped.append(f"{config_key}: 端口表无对应 sheet")
            continue
        cfg = LOOPBACK_CONFIG[config_key]
        keyword = cfg["keyword"]
        network_type = cfg["network_type"]
        if config_key not in WEB_NETWORK_TYPE_CONFIG:
            skipped.append(f"{config_key}: 无 WEB_NETWORK_TYPE 映射")
            continue
        web_name = WEB_NETWORK_TYPE_CONFIG[config_key]
        if not _sheet_has_loopback_devices(connect_path, matched, keyword):
            skipped.append(f"{config_key}: sheet {matched!r} 无 {keyword}/spine 设备")
            continue
        try:
            as_range_str, as_source = resolve_as_range_for_plane(
                network_type=network_type,
                config_key=config_key,
                resource_path=resource_path,
                sheet_res_index=sheet_res_index,
                as_range_overrides=as_range_overrides,
            )
        except ValueError as e:
            skipped.append(f"{config_key}: {e}")
            continue
        if not has_as_range(as_range_str):
            raw_hint = ""
            try:
                _, raw = get_net_resource_info(resource_path, network_type, sheet_res_index)
                raw_hint = f"（资源表当前值={raw!r}）"
            except ValueError:
                pass
            skipped.append(
                f"{config_key}: EBGP AS规划无区间{raw_hint}；"
                f"请在资源表「{network_type}」行填写如 65001-65099，"
                f"或 --as-range {network_type}=65001-65099"
            )
            continue
        plans.append(
            PlanePlan(
                sheet_connect=matched,
                config_key=config_key,
                keyword=keyword,
                network_type=network_type,
                web_network_type_name=web_name,
                as_range_str=as_range_str,
            )
        )
        if as_source == "override":
            override_notes.append(f"{config_key}: --as-range → {as_range_str}")

    return plans, skipped, override_notes


def detect_plane_sheets_for_export(
    connect_path: Path,
    *,
    only_config_key: Optional[str] = None,
) -> Tuple[List[PlanePlan], List[str]]:
    """
    识别端口表中存在 Leaf/Spine 的所有 LOOPBACK 平面（不要求资源表 EBGP AS 区间）。
    用于预置 gateway 设备列表，对齐线上仅从 t_gateway_info 汇总 ASN 表（ASN 可为空）。
    """
    xf = pd.ExcelFile(connect_path)
    available = list(xf.sheet_names)
    sheets: List[PlanePlan] = []
    skipped: List[str] = []

    keys = [only_config_key] if only_config_key else LOOPBACK_SHEET_ORDER
    for config_key in keys:
        if config_key not in LOOPBACK_CONFIG:
            continue
        matched = _match_loopback_sheet(available, config_key)
        if not matched:
            skipped.append(f"{config_key}: 端口表无对应 sheet（导出预置跳过）")
            continue
        cfg = LOOPBACK_CONFIG[config_key]
        keyword = cfg["keyword"]
        network_type = cfg["network_type"]
        web_name = WEB_NETWORK_TYPE_CONFIG.get(config_key)
        if not web_name:
            skipped.append(f"{config_key}: 无 WEB_NETWORK_TYPE 映射")
            continue
        if not _sheet_has_loopback_devices(connect_path, matched, keyword):
            skipped.append(f"{config_key}: sheet {matched!r} 无 {keyword}/spine 设备")
            continue
        sheets.append(
            PlanePlan(
                sheet_connect=matched,
                config_key=config_key,
                keyword=keyword,
                network_type=network_type,
                web_network_type_name=web_name,
                as_range_str="",
            )
        )
    return sheets, skipped


def seed_gateway_from_port_tables(
    connect_path: Path,
    plane_sheets: Sequence[PlanePlan],
    gateway_store: InMemoryGatewayStore,
) -> int:
    """从端口互联表预置各平面交换机设备（ASN 先置空）。"""
    total = 0
    for plan in plane_sheets:
        leafs, spines = get_leaf_spine_data(connect_path, plan.sheet_connect, plan.keyword)
        names = list(leafs) + list(spines)
        before = len(gateway_store.query_all())
        gateway_store.ensure_devices(plan.web_network_type_name, names, default_ebgp_as="")
        after = len(gateway_store.query_all())
        total += after - before
    return total


def load_gateway_snapshot(path: Path) -> InMemoryGatewayStore:
    """可选：从 CSV 导入已有网关（列：scope,name,network_segment,ebgp_as,vlan,extend）。"""
    df = pd.read_csv(path, dtype=str)
    col_map = {c.lower(): c for c in df.columns}
    records: List[GatewayRecord] = []

    def _cell(row, key: str, default: str = "NA") -> str:
        col = col_map.get(key, key)
        val = row.get(col, default)
        if pd.isna(val):
            return default
        s = str(val).strip()
        return s if s else default

    for _, row in df.iterrows():
        ebgp = _cell(row, "ebgp_as", "")
        if ebgp.upper() == "NA":
            ebgp = "NA"
        records.append(
            GatewayRecord(
                scope=_cell(row, "scope", "NA"),
                name=_cell(row, "name", ""),
                network_segment=_cell(row, "network_segment", "NA"),
                ebgp_as=ebgp,
                vlan=_cell(row, "vlan", "NA"),
                extend=_cell(row, "extend", "NA"),
            )
        )
    return InMemoryGatewayStore(records)
