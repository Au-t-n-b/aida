"""Offline A3 网络设备接入规划 — 对齐项目 merge_and_save_data + process_switch_mlag_data。

各地址规划 skill 在生成平面地址后，将对应 ``网络平面`` 行合并写入
``A3网络设备接入规划.xlsx``（sheet ``网络设备接入规划``），供
``net-dw-access-ip-workflow`` 按平面查询。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

import pandas as pd

ACCESS_PLAN_FILENAME = "A3网络设备接入规划.xlsx"
ACCESS_PLAN_SHEET = "网络设备接入规划"

ACCESS_COLUMNS = [
    "网络平面",
    "本端设备",
    "本端接口",
    "对端设备",
    "对端接口",
    "ETH-TRUNK",
    "绑定模式",
    "vlan",
    "pvid",
    "端口类型",
    "标签",
]


@dataclass(frozen=True)
class AccessPlanSpec:
    """Per-plane defaults aligned with project ``process_switch_mlag_data`` calls."""

    network_plane: str
    vlan_column: str
    port_type: str = "Access"
    label: str = "SERVER_LINK"
    pvid_from_vlan: bool = False
    merge_plane: Optional[str] = None
    device_column: str = "设备名称"


# 与项目 a3_*_ip_address.py / *_dw_manage_* 中 merge 使用的网络平面一致
PLANE_SPECS: dict[str, AccessPlanSpec] = {
    "计算带外管理面": AccessPlanSpec("计算带外管理面", "带外管理VLAN", label="MGMT_LINK"),
    "存储带外管理面": AccessPlanSpec("存储带外管理面", "带外管理VLAN", label="MGMT_LINK"),
    "灵衢带外管理面": AccessPlanSpec(
        "灵衢带外管理面",
        "带外管理VLAN",
        label="MGMT_LINK",
        merge_plane="灵衢带外管理面",
    ),
    "计算管理面": AccessPlanSpec("计算管理面", "计算管理面VLAN", label="SERVER_LINK"),
    "存储管理面": AccessPlanSpec("存储管理面", "存储管理面VLAN", label="STORAGE_LINK"),
    "计算业务面": AccessPlanSpec("计算业务面", "计算业务面VLAN", label="SERVER_LINK"),
    "存储业务面": AccessPlanSpec(
        "存储业务面",
        "存储业务面VLAN",
        label="STORAGE_LINK",
        pvid_from_vlan=True,
    ),
    "计算参数面": AccessPlanSpec(
        "计算参数面",
        "参数面VLAN",
        label="COMPUTE_LINK",
        pvid_from_vlan=True,
    ),
    "计算样本面": AccessPlanSpec("计算样本面", "计算样本面VLAN", label="COMPUTE_LINK"),
    "存储样本面": AccessPlanSpec("存储样本面", "存储样本面VLAN", label="COMPUTE_LINK"),
}


def resolve_vlan_column(address_df: pd.DataFrame, spec: AccessPlanSpec) -> str:
    if spec.vlan_column in address_df.columns:
        return spec.vlan_column
    plane = spec.network_plane
    for candidate in (f"{plane}VLAN", "带外管理VLAN", "参数面VLAN"):
        if candidate in address_df.columns:
            return candidate
    for col in address_df.columns:
        if str(col).endswith("VLAN"):
            return str(col)
    raise ValueError(
        f"address table missing VLAN column (expected {spec.vlan_column!r}); "
        f"columns={list(address_df.columns)}"
    )


def _find_header_row(raw: pd.DataFrame, needle: str) -> int:
    for i in range(len(raw.index)):
        row = raw.iloc[i].astype(str).tolist()
        if any(needle in (c or "") for c in row):
            return i
    raise ValueError(f"connect sheet: cannot locate header row containing {needle!r}")


def read_connect_dataframe(connect_path: Path, sheet: Union[str, int]) -> pd.DataFrame:
    """Read 007 connect sheet → ``对端设备/对端接口/本端设备/本端接口`` 四列。

    建模仿真双行表头优先走 ``connect_007_structured``（设备命名列，非设备 ID）；
    扁平行/旧表头走 legacy 解析。
    """
    try:
        from _runtime_shared.connect_007_structured import pick_column, try_read_structured
    except ImportError:
        try_read_structured = None  # type: ignore[misc, assignment]
        pick_column = None  # type: ignore[misc, assignment]

    if try_read_structured is not None:
        structured = try_read_structured(connect_path, sheet)
        if structured is not None and not structured.empty:
            src_name = pick_column(structured, "起始端信息-设备命名", "设备命名")
            src_port = pick_column(structured, "起始端信息-接口信息", "接口信息")
            leaf_name = pick_column(structured, "目的端信息-设备命名")
            leaf_port = pick_column(structured, "目的端信息-接口信息", "接口信息")
            out = pd.DataFrame(
                {
                    "对端设备": structured[src_name].astype(str).str.strip(),
                    "对端接口": structured[src_port].astype(str).str.strip(),
                    "本端设备": structured[leaf_name].astype(str).str.strip(),
                    "本端接口": structured[leaf_port].astype(str).str.strip(),
                }
            )
            out = out[
                (out["对端设备"] != "")
                & (out["本端设备"] != "")
                & (out["对端设备"].str.lower() != "nan")
                & (out["本端设备"].str.lower() != "nan")
            ]
            if not out.empty:
                return out.reset_index(drop=True)

    raw = pd.read_excel(connect_path, sheet_name=sheet, header=None, dtype=str).fillna("")
    header_idx = _find_header_row(raw, "起始端信息")
    df = raw.iloc[header_idx:].reset_index(drop=True)

    if df.iloc[0].astype(str).str.contains("起始端信息-设备命名", case=False, na=False).any():
        df = df.iloc[1:].reset_index(drop=True)

    row0 = df.iloc[0].values
    row1 = df.iloc[1].values
    new_columns: List[str] = []
    j = 0
    for i in range(len(row0)):
        if row0[i] == "起始端信息":
            new_columns.append(f"起始端信息-{row1[i]}")
            j = i
        elif row0[i] == "目的端信息":
            new_columns.append(f"目的端信息-{row1[i]}")
            j = i
        elif row0[i] == "线缆信息":
            new_columns.append(f"线缆信息-{row1[i]}")
            j = i
        else:
            new_columns.append(f"{row0[j]}-{row1[i]}")
    data_rows = df.iloc[2:].values.tolist()
    wide = pd.DataFrame(data_rows, columns=new_columns)
    if not wide.empty and pick_column is not None:
        try:
            src_name = pick_column(wide, "起始端信息-设备命名", "设备命名")
            src_port = pick_column(wide, "起始端信息-接口信息", "接口信息")
            leaf_name = pick_column(wide, "目的端信息-设备命名")
            leaf_port = pick_column(wide, "目的端信息-接口信息", "接口信息")
            return pd.DataFrame(
                {
                    "对端设备": wide[src_name].astype(str).str.strip(),
                    "对端接口": wide[src_port].astype(str).str.strip(),
                    "本端设备": wide[leaf_name].astype(str).str.strip(),
                    "本端接口": wide[leaf_port].astype(str).str.strip(),
                }
            ).reset_index(drop=True)
        except Exception:
            pass
    return wide


def _build_mlag_peer_map(mlag_df: pd.DataFrame) -> dict[str, str]:
    peers: dict[str, str] = {}
    if mlag_df is None or mlag_df.empty:
        return peers
    for _, row in mlag_df.iterrows():
        a = str(row.get("设备", "")).strip()
        b = str(row.get("接入交换机", "")).strip()
        if a and b:
            peers[a] = b
            peers[b] = a
    return peers


def get_switch_mlag_data_from_connect(connect_df: pd.DataFrame) -> pd.DataFrame:
    """Align ``utils._get_switch_mlag_data`` (offline, no DB / no trunk renumber)."""
    required = {"对端设备", "对端接口", "本端设备", "本端接口"}
    if required.issubset(connect_df.columns):
        df = connect_df[list(required)].copy()
    else:
        df = connect_df.copy()
        df = df.rename(
            columns={
                df.columns[0]: "设备",
                df.columns[1]: "接口",
                df.columns[-1]: "接入交换机",
            }
        )
        leaf_df = df[df["接入交换机"].astype(str).str.contains("leaf", case=False, na=False)]
        mask = leaf_df["设备"].astype(str).str.contains("leaf", case=False, na=False) & leaf_df[
            "接入交换机"
        ].astype(str).str.contains("leaf", case=False, na=False)
        leaf_df = leaf_df.copy()
        leaf_df["标记"] = ""
        leaf_df.loc[mask, "标记"] = "MLAG"
        switch_mlag_data = leaf_df[["设备", "接入交换机", "标记"]].drop_duplicates()
        switch_mlag_data = switch_mlag_data[switch_mlag_data["标记"] == "MLAG"]

        mlag_switches = set(switch_mlag_data["设备"]).union(set(switch_mlag_data["接入交换机"]))

        df = df.rename(
            columns={
                df.columns[0]: "对端设备",
                df.columns[1]: "对端接口",
                df.columns[-1]: "本端设备",
            }
        )
        if df.shape[1] >= 8:
            df["本端接口"] = df.iloc[:, 5].fillna("").astype(str) + df.iloc[:, 7].fillna("").astype(str)
            df["本端接口"] = df["本端接口"].str.strip()

        device_df = df[~df["对端设备"].astype(str).str.contains(r"leaf", case=False, na=False)]
        device_df = device_df.copy()
        device_df.loc[:, ["ETH-TRUNK", "绑定模式"]] = ["NA", "单独IP"]
        device_df.loc[device_df["本端设备"].isin(mlag_switches), ["ETH-TRUNK", "绑定模式"]] = [
            "NA",
            "bond4",
        ]
        return device_df[
            ["对端设备", "对端接口", "本端设备", "本端接口", "ETH-TRUNK", "绑定模式"]
        ].drop_duplicates()

    leaf_df = df[df["本端设备"].astype(str).str.contains("leaf", case=False, na=False)]
    mask = leaf_df["对端设备"].astype(str).str.contains("leaf", case=False, na=False) & leaf_df[
        "本端设备"
    ].astype(str).str.contains("leaf", case=False, na=False)
    switch_mlag_data = leaf_df[mask][["对端设备", "本端设备"]].drop_duplicates()
    mlag_switches = set(switch_mlag_data["对端设备"]).union(set(switch_mlag_data["本端设备"]))

    device_df = df[~df["对端设备"].astype(str).str.contains(r"leaf", case=False, na=False)].copy()
    device_df.loc[:, ["ETH-TRUNK", "绑定模式"]] = ["NA", "单独IP"]
    device_df.loc[device_df["本端设备"].isin(mlag_switches), ["ETH-TRUNK", "绑定模式"]] = [
        "NA",
        "bond4",
    ]
    return device_df[
        ["对端设备", "对端接口", "本端设备", "本端接口", "ETH-TRUNK", "绑定模式"]
    ].drop_duplicates()


def build_vlan_map_storage_ywm(
    osp_df: Optional[pd.DataFrame],
    osa800_df: Optional[pd.DataFrame],
    network_plane: str,
) -> dict[str, str]:
    """Align ``a3_cc_ywm_ip_address`` OSP + OSA800 VLAN mapping for access plan."""
    mapping: dict[str, str] = {}
    vlan_col = f"{network_plane}VLAN"
    if osp_df is not None and not osp_df.empty and vlan_col in osp_df.columns:
        for _, row in osp_df.iterrows():
            mapping[str(row["设备名称"])] = str(row[vlan_col])
    if osa800_df is not None and not osa800_df.empty and "VLAN1" in osa800_df.columns:
        for _, row in osa800_df.iterrows():
            v1 = str(row.get("VLAN1", ""))
            v2 = str(row.get("VLAN2", ""))
            mapping[str(row["设备名称"])] = f"{v1}、{v2}" if v2 else v1
    return mapping


def build_switch_mlag_access_plan(
    connect_path: Path,
    connect_sheet: Union[str, int],
    address_df: pd.DataFrame,
    spec: AccessPlanSpec,
    *,
    endpoint_device_filter: Optional[str] = None,
    device_vlan_map: Optional[dict[str, str]] = None,
) -> pd.DataFrame:
    """Align ``process_switch_mlag_data`` output columns."""
    if address_df.empty and not device_vlan_map:
        return pd.DataFrame(columns=ACCESS_COLUMNS)

    connect_df = read_connect_dataframe(connect_path, connect_sheet)
    switch_mlag_df = get_switch_mlag_data_from_connect(connect_df)

    if endpoint_device_filter:
        switch_mlag_df = switch_mlag_df[
            switch_mlag_df["本端设备"].astype(str).str.contains(
                endpoint_device_filter, case=False, na=False
            )
        ]

    if device_vlan_map is None:
        vlan_col = resolve_vlan_column(address_df, spec)
        dev_col = spec.device_column
        if dev_col not in address_df.columns:
            raise ValueError(f"address table missing column {dev_col!r}")
        device_vlan_map = dict(
            zip(
                address_df[dev_col].astype(str),
                address_df[vlan_col].astype(str),
            )
        )
    switch_mlag_df = switch_mlag_df.copy()
    switch_mlag_df["vlan"] = switch_mlag_df["对端设备"].map(device_vlan_map)
    switch_mlag_df["pvid"] = switch_mlag_df["vlan"] if spec.pvid_from_vlan else ""
    switch_mlag_df.loc[:, ["网络平面", "端口类型", "标签"]] = [
        spec.network_plane,
        spec.port_type,
        spec.label,
    ]
    return switch_mlag_df.reindex(columns=ACCESS_COLUMNS)


def collect_used_trunk_ids(search_dirs: Iterable[Path]) -> List[int]:
    trunks: List[int] = []
    for base in search_dirs:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.xlsx")):
            try:
                df = pd.read_excel(path, sheet_name=0, header=0)
            except Exception:
                continue
            for col in ("本端ETH-TRUNK", "对端ETH-TRUNK", "ETH-TRUNK"):
                if col not in df.columns:
                    continue
                for v in df[col].dropna().unique():
                    try:
                        trunks.append(int(v))
                    except (TypeError, ValueError):
                        pass
    return trunks


def resolve_access_plan_workbook(run_dir: Path, search_dirs: Sequence[Path] = ()) -> Path:
    for base in (run_dir, *search_dirs):
        if not base.is_dir():
            continue
        for p in sorted(base.rglob(ACCESS_PLAN_FILENAME)):
            if p.is_file():
                return p
    return run_dir / ACCESS_PLAN_FILENAME


def merge_access_plan_workbook(
    workbook_path: Path,
    network_plane: str,
    new_rows: pd.DataFrame,
) -> Path:
    """Align ``utils.merge_and_save_data`` (drop plane rows then append)."""
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    if new_rows is None or new_rows.empty:
        return workbook_path

    if workbook_path.is_file():
        try:
            old_df = pd.read_excel(workbook_path, sheet_name=0, header=0)
        except Exception:
            old_df = pd.DataFrame()
        if "网络平面" in old_df.columns:
            old_df = old_df[~old_df["网络平面"].astype(str).isin([network_plane])]
    else:
        old_df = pd.DataFrame()

    merged = pd.concat([old_df, new_rows], ignore_index=True)
    merged.to_excel(workbook_path, sheet_name=ACCESS_PLAN_SHEET, index=False)
    return workbook_path


def emit_merged_access_plan(
    run_dir: Path,
    *,
    connect_path: Path,
    connect_sheet: Union[str, int],
    address_df: pd.DataFrame,
    spec: AccessPlanSpec,
    search_dirs: Optional[Sequence[Path]] = None,
    prebuilt_rows: Optional[pd.DataFrame] = None,
    endpoint_device_filter: Optional[str] = None,
    device_vlan_map: Optional[dict[str, str]] = None,
) -> Optional[Path]:
    """Write or update ``A3网络设备接入规划.xlsx`` under *run_dir* (and search_dirs)."""
    merge_plane = spec.merge_plane or spec.network_plane
    dirs = [run_dir, *(search_dirs or [])]
    out_path = resolve_access_plan_workbook(run_dir, dirs)

    if prebuilt_rows is not None:
        rows = prebuilt_rows.reindex(columns=ACCESS_COLUMNS)
    else:
        rows = build_switch_mlag_access_plan(
            connect_path,
            connect_sheet,
            address_df,
            spec,
            endpoint_device_filter=endpoint_device_filter,
            device_vlan_map=device_vlan_map,
        )

    if rows.empty:
        return None

    merge_access_plan_workbook(out_path, merge_plane, rows)
    return out_path


def emit_for_plane(
    run_dir: Path,
    *,
    plane_key: str,
    connect_path: Path,
    connect_sheet: Union[str, int],
    address_df: pd.DataFrame,
    search_dirs: Optional[Sequence[Path]] = None,
    **kwargs: object,
) -> Optional[Path]:
    spec = PLANE_SPECS.get(plane_key)
    if spec is None:
        raise ValueError(f"unknown plane for access plan: {plane_key!r}")
    return emit_merged_access_plan(
        run_dir,
        connect_path=connect_path,
        connect_sheet=connect_sheet,
        address_df=address_df,
        spec=spec,
        search_dirs=search_dirs,
        **kwargs,
    )


def filter_assignable_address_rows(address_df: pd.DataFrame) -> pd.DataFrame:
    """Drop planning error rows before building access plan VLAN maps."""
    if address_df.empty:
        return address_df
    addr_cols = [c for c in address_df.columns if str(c).endswith("地址")]
    if not addr_cols:
        return address_df
    col = addr_cols[0]
    bad = address_df[col].astype(str).str.contains("不足", na=False)
    return address_df[~bad].copy()


def add_subskills_to_path(from_file: Path) -> None:
    """Insert ``subskills/`` on sys.path (call from ``*/scripts/*.py``)."""
    import sys

    root = from_file.resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
