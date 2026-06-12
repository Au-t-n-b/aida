#!/usr/bin/env python3
"""007 + 资源表 → output/run_*/计算带外管理地址.xlsx。依赖 pandas、openpyxl。"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dw_manage_segment_rules import (
    SEGMENT_USABLE_IP_INSUFFICIENT,
    SwitchGateway,
    classify_spine_or_leaf,
    enumerate_usable_ips_in_pool,
    is_non_assignable_plan_segment,
    parse_ip_pool_bounds,
    plan_switch_gateways_leaf_i3,
    plan_switch_gateways_with_sharing,
    split_ip_range,
)

NET_PLANE = "计算带外管理面"
SHEET_007_DEFAULT = "计算带外管理面端口互联"
CONNECT_SHEETS_ALLOWED = (SHEET_007_DEFAULT,)
SHEET_RES_DEFAULT = "网络资源需求表"
SHEET_RES_DEFAULT_INDEX = 0

DEFAULT_PROMPT_SPINE = Path("a3_i2_network_segment_tools_prompt.py")
DEFAULT_PROMPT_LEAF = Path("a3_i3_network_segment_tools_prompt.py")

PROMPT_SPINE_MARKERS = ("多个或所有交换机使用同一网段", "顺次累加节点数量")
PROMPT_LEAF_MARKERS = ("交接机不能共用网段", "网段个数不足", "vlan不足")

# 0 起：0–47；1 起：1–48（均表示至多 48 台）
_MAX_COMPUTE_NODE_ID_INCLUSIVE = 48
_HAS_SP_AT_SUFFIX_RE = re.compile(r"(?i)-SP\d+-AT")


@dataclass(frozen=True)
class IpAssignmentRequestItem:
    leaf: str
    network_segment: str
    gateway: str
    mask: int
    vlan: str


def _resolve_local_only(p: Path) -> Path:
    if p.is_absolute():
        return p
    return (Path.cwd() / p).resolve()


def _require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = _resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception:
        raise SystemExit(
            f"ERROR: {label} must be located under current working directory.\n"
            f"  resolved: {resolved}\n"
            f"  cwd:      {cwd}"
        )
    return resolved


def _list_excel_files_in_cwd() -> List[Path]:
    cwd = Path.cwd().resolve()
    files: List[Path] = []
    for ext in (".xlsx", ".xls", ".XLSX", ".XLS"):
        files.extend([p for p in cwd.rglob(f"*{ext}") if p.is_file()])
    uniq: List[Path] = []
    seen = set()
    for p in files:
        if p.name.startswith("~$"):
            continue
        rp = str(p.resolve())
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)
    return uniq


def _autodetect_007_in_cwd() -> Path:
    cands = _list_excel_files_in_cwd()
    for p in cands:
        n = p.name
        if ("007" in n) or ("端口连线" in n):
            return p
    raise SystemExit("ERROR: cannot autodetect 007 excel in current working directory.")


def _autodetect_resource_in_cwd() -> Path:
    cands = _list_excel_files_in_cwd()
    for p in cands:
        n = p.name
        if ("项目信息收集" in n) or ("资源" in n):
            return p
    raise SystemExit("ERROR: cannot autodetect resource excel in current working directory.")


def _find_header_row(df: "pd.DataFrame", needle: str = "设备命名") -> int:
    for i in range(len(df.index)):
        row = df.iloc[i].astype(str).tolist()
        if any(needle in (c or "") for c in row):
            return i
    raise ValueError(f"cannot locate header row by {needle!r}")


def _read_007_switch_to_servers(path_007: Path, sheet_name: str) -> Dict[str, List[str]]:
    def _read_one(sheet: object) -> Dict[str, List[str]]:
        raw = pd.read_excel(path_007, sheet_name=sheet, header=None, dtype=str).fillna("")
        header_idx = _find_header_row(raw, "设备命名")
        data = raw.iloc[header_idx + 1 :].copy()
        if data.shape[1] < 2:
            raise ValueError("007 sheet: expected at least 2 columns (server, leaf)")

        server_col = data.columns[0]
        leaf_col = data.columns[data.shape[1] - 1]
        data = data[[server_col, leaf_col]]
        data.columns = ["计算服务器", "接入交换机"]
        data["计算服务器"] = data["计算服务器"].astype(str).str.strip()
        data["接入交换机"] = data["接入交换机"].astype(str).str.strip()
        data = data[(data["计算服务器"] != "") & (data["接入交换机"] != "")]

        # Filter out rows where server column is actually a switch name
        data = data[~data["计算服务器"].str.contains(r"LEAF|SPINE", case=False, regex=True)]

        out: Dict[str, List[str]] = {}
        for leaf, g in data.groupby("接入交换机", sort=False):
            servers = [s for s in g["计算服务器"].tolist() if s]
            if servers:
                out[str(leaf)] = servers
        if not out:
            raise ValueError("007 sheet: no (leaf -> servers) data found after filtering")
        return out

    _skill_root = Path(__file__).resolve().parents[2]
    if str(_skill_root) not in sys.path:
        sys.path.insert(0, str(_skill_root))
    from _runtime_shared.sheet007_resolver import resolve_connect_sheet

    resolved = resolve_connect_sheet(
        path_007,
        sheet_name,
        allowed_sheets=CONNECT_SHEETS_ALLOWED,
    )
    return _read_one(resolved)


def _read_resource_row(path_resource: Path, sheet_spec: object) -> "pd.Series":
    _skill_root = Path(__file__).resolve().parents[2]
    if str(_skill_root) not in sys.path:
        sys.path.insert(0, str(_skill_root))
    from _runtime_shared.sheet007_resolver import resolve_resource_sheet

    resolved = resolve_resource_sheet(path_resource, sheet_spec)
    df = pd.read_excel(path_resource, sheet_name=resolved, header=0)
    if "网络平面" not in df.columns:
        raise ValueError("resource: missing column '网络平面'")
    rows = df[df["网络平面"] == NET_PLANE]
    if rows.empty:
        raise ValueError(f"resource: no row where 网络平面 == {NET_PLANE!r} in sheet {resolved!r}")
    return rows.iloc[0]


def _fuzzy_get(row: "pd.Series", needle: str) -> Optional[object]:
    for k in row.index:
        if needle in str(k):
            return row.get(k)
    return None


def _resolve_prompt_template_file(path_or_name: Path) -> Optional[Path]:
    if path_or_name.is_absolute():
        return path_or_name if path_or_name.is_file() else None
    cwd_candidate = (Path.cwd() / path_or_name).resolve()
    if cwd_candidate.is_file():
        return cwd_candidate
    repo_candidate = (_SCRIPTS_DIR.parent / path_or_name.name).resolve()
    if repo_candidate.is_file():
        return repo_candidate
    return None


def _extract_first_triple_quoted_block(py_text: str) -> str:
    m = re.search(r'"""([\s\S]*?)"""', py_text)
    return m.group(1) if m else ""


def _validate_prompt_markers(path: Path, markers: Sequence[str], label: str) -> None:
    body = _extract_first_triple_quoted_block(path.read_text(encoding="utf-8", errors="ignore"))
    missing = [x for x in markers if x not in body]
    if missing:
        raise ValueError(f"{label}: prompt template missing phrases {missing} in {path}")


def _partition_spine_leaf_switches(switch_list: List[str]) -> Tuple[List[str], List[str]]:
    spine: List[str] = []
    leaf: List[str] = []
    for sw in switch_list:
        if classify_spine_or_leaf(sw) == "spine":
            spine.append(sw)
        else:
            leaf.append(sw)
    return spine, leaf


def _merge_switch_gateways_in_switch_order(
    switch_list: List[str], spine_rows: List[SwitchGateway], leaf_rows: List[SwitchGateway]
) -> List[SwitchGateway]:
    by_name: Dict[str, SwitchGateway] = {}
    for sg in spine_rows:
        by_name[sg.name] = sg
    for sg in leaf_rows:
        by_name[sg.name] = sg
    return [by_name[s] for s in switch_list]


def _assignment_group_key(it: IpAssignmentRequestItem) -> str:
    if is_non_assignable_plan_segment(it.network_segment):
        return f"__plan_err__:{it.leaf}:{it.network_segment}"
    return it.network_segment


def build_ip_assignment_request(
    *,
    switch_gateways: List[SwitchGateway],
    switch_to_servers: Dict[str, List[str]],
    pool_start: IPv4Address,
    pool_end: IPv4Address,
) -> List[IpAssignmentRequestItem]:
    items: List[IpAssignmentRequestItem] = []
    for sg in switch_gateways:
        if is_non_assignable_plan_segment(sg.network_segment):
            items.append(
                IpAssignmentRequestItem(
                    leaf=sg.name,
                    network_segment=sg.network_segment,
                    gateway="",
                    mask=sg.mask,
                    vlan=sg.vlan,
                )
            )
            continue
        network = IPv4Network(sg.network_segment, strict=False)
        gateway_ip = IPv4Address(sg.gateway)
        _ = enumerate_usable_ips_in_pool(network, gateway_ip, pool_start, pool_end)
        items.append(
            IpAssignmentRequestItem(
                leaf=sg.name,
                network_segment=sg.network_segment,
                gateway=str(sg.gateway),
                mask=sg.mask,
                vlan=sg.vlan,
            )
        )
    return items


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_out_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def _recalculate_scale(rows: List[dict]) -> None:
    counts: Dict[int, int] = {}
    for r in rows:
        sp_id = r.get("超节点ID")
        if isinstance(sp_id, int):
            counts[sp_id] = counts.get(sp_id, 0) + 1
    for r in rows:
        sp_id = r.get("超节点ID")
        if isinstance(sp_id, int):
            r["超节点规模"] = counts.get(sp_id, 0) * 8


def _extract_sp_id_from_server_name(server: object) -> Optional[int]:
    s = str(server).strip()
    if not s:
        return None
    m = re.search(r"(?i)-SP(\d+)-AT", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(?i)-SP(\d+)-", s)
    if m:
        return int(m.group(1))
    return None


def _parse_tail_ints_desc(parts: Sequence[str]) -> Optional[int]:
    for cand in reversed(list(parts)):
        if not str(cand).strip():
            continue
        try:
            return int(str(cand).strip())
        except ValueError:
            continue
    return None


def _compute_sp_and_compute_node_cell(server: object) -> Tuple[object, object]:
    s = str(server).strip()
    sp_num = _extract_sp_id_from_server_name(server)
    sp_cell: object = int(sp_num) if sp_num is not None else ""

    server_id_int: Optional[int] = None
    m_rest = re.search(r"(?i)-SP\d+-(.*)$", s)
    if m_rest:
        rest = (m_rest.group(1) or "").strip()
        if rest.casefold().endswith("-at"):
            rest = rest[:-3].strip("-")
        if rest:
            server_id_int = _parse_tail_ints_desc(rest.split("-"))

    if server_id_int is None and s:
        parts = s.split("-")
        tail: List[str] = [parts[-1]]
        if len(parts) >= 2 and str(parts[-1]).strip().upper() == "AT":
            tail.append(parts[-2])
        for cand in tail:
            try:
                server_id_int = int(str(cand).strip())
                break
            except ValueError:
                continue

    has_sp_at = bool(_HAS_SP_AT_SUFFIX_RE.search(s))
    if has_sp_at and server_id_int is None:
        raise ValueError(
            f"设备名称匹配 -SP*-AT 但无法解析计算节点ID: {s!r}，请检查007端口连线数据表后重试"
        )

    if server_id_int is not None:
        if server_id_int < 0:
            raise ValueError(
                f"计算节点ID不能为负: {s!r}，请检查007端口连线数据表后重试"
            )
        if server_id_int > _MAX_COMPUTE_NODE_ID_INCLUSIVE:
            raise ValueError(
                "计算节点ID须在0-47或1-48（至多48台），超出请修正007设备命名后重试"
                f"（设备: {s!r}，解析值: {server_id_int}）"
            )

    node_cell: object = server_id_int if server_id_int is not None else ""
    return sp_cell, node_cell


def _count_sp_pattern(data_list: List[str]) -> Dict[str, int]:
    sp_count_map: Dict[str, int] = {}
    for s in data_list:
        sp = _extract_sp_id_from_server_name(s)
        if sp is None:
            continue
        key = str(sp)
        sp_count_map[key] = sp_count_map.get(key, 0) + 1
    return sp_count_map


def generate_dw_manage_ip_address_xlsx(
    *,
    path_007: Optional[Path] = None,
    resource: Optional[Path] = None,
    sheet007: str = SHEET_007_DEFAULT,
    sheet_res_index: int = SHEET_RES_DEFAULT_INDEX,
    out_dir: Path = Path("output"),
    prompt_spine_file: Optional[Path] = DEFAULT_PROMPT_SPINE,
    prompt_leaf_file: Optional[Path] = DEFAULT_PROMPT_LEAF,
    restrict_to_cwd: bool = True,
) -> Path:
    if path_007 is None:
        path_007 = _autodetect_007_in_cwd()
    if resource is None:
        resource = _autodetect_resource_in_cwd()

    if restrict_to_cwd:
        path_007 = _require_under_cwd(path_007, "007")
        resource = _require_under_cwd(resource, "resource")
        out_dir = _require_under_cwd(out_dir, "out-dir")
    else:
        path_007 = _resolve_local_only(path_007)
        resource = _resolve_local_only(resource)
        out_dir = _resolve_local_only(out_dir)

    if not path_007.is_file():
        raise ValueError(f"007 file not found: {path_007}")
    if not resource.is_file():
        raise ValueError(f"resource file not found: {resource}")

    if prompt_spine_file is not None:
        rp = _resolve_prompt_template_file(prompt_spine_file)
        if rp is not None:
            _validate_prompt_markers(rp, PROMPT_SPINE_MARKERS, "SPINE/i2")
    if prompt_leaf_file is not None:
        rp = _resolve_prompt_template_file(prompt_leaf_file)
        if rp is not None:
            _validate_prompt_markers(rp, PROMPT_LEAF_MARKERS, "LEAF/i3")

    ts = _timestamp()
    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    _ensure_out_dir(run_dir)

    switch_to_servers = _read_007_switch_to_servers(path_007, sheet007)
    switch_list = list(switch_to_servers.keys())
    max_switch_count = len(switch_list)

    r = _read_resource_row(resource, sheet_res_index)
    ip_pool = str(r.get("地址池*", "")).strip()
    if not ip_pool:
        raise ValueError("resource: 地址池* is empty")
    mask = int(_fuzzy_get(r, "最小规划掩码"))
    gateway_mode = r.get("网关地址*", "")
    vlan_raw = r.get("VLAN*", "")

    pool_start, pool_end = parse_ip_pool_bounds(ip_pool)

    subnets = split_ip_range(ip_pool, target_prefix=mask, max_switch_count=max_switch_count)
    if not subnets:
        raise ValueError(f"地址池* cannot yield any /{mask} subnet for planning")

    spine_names, leaf_names = _partition_spine_leaf_switches(switch_list)

    spine_rows: List[SwitchGateway] = []
    subnets_consumed_spine = 0
    vlan_next_for_leaf = 0
    if spine_names:
        spine_rows, subnets_consumed_spine, vlan_next_for_leaf = plan_switch_gateways_with_sharing(
            switch_list=spine_names,
            switch_to_servers=switch_to_servers,
            subnets=subnets,
            mask=mask,
            gateway_mode=gateway_mode,
            vlan_raw=vlan_raw,
        )

    leaf_subnets = subnets[subnets_consumed_spine:]
    leaf_rows = (
        plan_switch_gateways_leaf_i3(
            switch_list=leaf_names,
            subnets=leaf_subnets,
            mask=mask,
            gateway_mode=gateway_mode,
            vlan_raw=vlan_raw,
            vlan_subnet_offset=vlan_next_for_leaf,
        )
        if leaf_names
        else []
    )

    switch_gateways = _merge_switch_gateways_in_switch_order(switch_list, spine_rows, leaf_rows)

    req_items = build_ip_assignment_request(
        switch_gateways=switch_gateways,
        switch_to_servers=switch_to_servers,
        pool_start=pool_start,
        pool_end=pool_end,
    )

    network_segment_to_switches: Dict[str, List[str]] = {}
    for it in req_items:
        network_segment_to_switches.setdefault(_assignment_group_key(it), []).append(it.leaf)

    switch_name_to_item: Dict[str, IpAssignmentRequestItem] = {it.leaf: it for it in req_items}

    rows_final: List[dict] = []

    for net_seg, switches in network_segment_to_switches.items():
        all_servers: List[str] = []
        for sw in switches:
            all_servers.extend(switch_to_servers.get(sw, []))
        if not all_servers:
            continue

        example_switch = switches[0]
        gateway_info = switch_name_to_item.get(example_switch)
        if gateway_info is None:
            raise ValueError(f"missing planning info for switch: {example_switch}")

        if is_non_assignable_plan_segment(gateway_info.network_segment):
            scale_value = _count_sp_pattern(all_servers)
            addr_marker = gateway_info.network_segment
            for server in all_servers:
                sp_id, server_id = _compute_sp_and_compute_node_cell(server)
                rows_final.append(
                    {
                        "设备名称": str(server),
                        "带外管理地址": addr_marker,
                        "带外管理掩码": f"{gateway_info.mask}",
                        "带外管理网关": "",
                        "带外管理VLAN": str(gateway_info.vlan),
                        "接口名称": "MGMT",
                        "超节点ID": sp_id,
                        "超节点规模": (scale_value.get(str(sp_id), 0) * 8) if sp_id != "" else "",
                        "计算节点ID": server_id,
                    }
                )
            continue

        gateway_ip = IPv4Address(gateway_info.gateway)
        network = IPv4Network(net_seg, strict=False)
        usable_ips = enumerate_usable_ips_in_pool(
            subnet=network,
            gateway=gateway_ip,
            pool_start=pool_start,
            pool_end=pool_end,
        )

        scale_value = _count_sp_pattern(all_servers)

        for i, server in enumerate(all_servers):
            if i < len(usable_ips):
                chosen = str(usable_ips[i])
            else:
                chosen = SEGMENT_USABLE_IP_INSUFFICIENT
            sp_id, server_id = _compute_sp_and_compute_node_cell(server)

            gw_cell = "" if chosen == SEGMENT_USABLE_IP_INSUFFICIENT else f"{gateway_ip}"
            rows_final.append(
                {
                    "设备名称": str(server),
                    "带外管理地址": chosen,
                    "带外管理掩码": f"{gateway_info.mask}",
                    "带外管理网关": gw_cell,
                    "带外管理VLAN": str(gateway_info.vlan),
                    "接口名称": "MGMT",
                    "超节点ID": sp_id,
                    "超节点规模": (scale_value.get(str(sp_id), 0) * 8) if sp_id != "" else "",
                    "计算节点ID": server_id,
                }
            )

    _recalculate_scale(rows_final)
    df_final = pd.DataFrame(rows_final)

    out_final = run_dir / "计算带外管理地址.xlsx"
    with pd.ExcelWriter(out_final, engine="openpyxl") as w:
        df_final.to_excel(w, index=False, sheet_name="计算带外管理地址")

    _skill_root = Path(__file__).resolve().parents[2]
    if str(_skill_root) not in sys.path:
        sys.path.insert(0, str(_skill_root))
    from _runtime_shared.network_access_plan import emit_for_plane, filter_assignable_address_rows

    emit_for_plane(
        run_dir,
        plane_key=NET_PLANE,
        connect_path=path_007,
        connect_sheet=sheet007,
        address_df=filter_assignable_address_rows(df_final),
        search_dirs=[out_dir],
    )

    return out_final


def run_job(
    *,
    intent: str,
    topology: Optional[Path] = None,
    resource: Optional[Path] = None,
    out_dir: Path,
    skill_def: object = None,
    inputs: Optional[dict] = None,
    options: Optional[dict] = None,
    **kwargs: object,
) -> "SkillJobResult":
    """In-process entry for ISPR (agent-skill_full1/runtime/executor.py)."""
    _runtime_root = Path(__file__).resolve().parents[2]
    if str(_runtime_root) not in sys.path:
        sys.path.insert(0, str(_runtime_root))
    from runtime.job_types import SkillJobResult

    opts = dict(options or {})
    opts.update({k: v for k, v in kwargs.items() if k not in ("intent", "topology", "resource", "out_dir")})
    path_007 = topology or (inputs or {}).get("007") or (inputs or {}).get("topology")
    res = resource or (inputs or {}).get("resource")
    if path_007 is None or res is None:
        return SkillJobResult(
            status="error",
            output_files=(),
            summary="计算带外管理地址规划缺少 007 或资源表输入。",
            errors=("missing topology or resource",),
            sub_skill_name="a3-dw-manage-ip-workflow.code1",
        )
    try:
        out_final = generate_dw_manage_ip_address_xlsx(
            path_007=Path(path_007),
            resource=Path(res),
            sheet007=str(opts.pop("sheet007", SHEET_007_DEFAULT)),
            sheet_res_index=int(opts.pop("sheet_res_index", SHEET_RES_DEFAULT_INDEX)),
            out_dir=Path(out_dir),
            prompt_spine_file=None,
            prompt_leaf_file=None,
            restrict_to_cwd=False,
        )
        run_dir = out_final.parent
        outputs = tuple(sorted(p for p in run_dir.rglob("*.xlsx") if p.is_file()))
        if not outputs:
            outputs = (out_final,)
        return SkillJobResult(
            status="ok",
            output_files=outputs,
            summary=f"计算带外管理地址规划完成，生成 {len(outputs)} 个产物。",
            sub_skill_name="a3-dw-manage-ip-workflow.code1",
        )
    except Exception as exc:
        return SkillJobResult(
            status="error",
            output_files=(),
            summary="计算带外管理地址规划失败。",
            errors=(str(exc),),
            sub_skill_name="a3-dw-manage-ip-workflow.code1",
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Offline A3 DW manage IP planning pipeline (final Excel only)")
    p.add_argument("--007", dest="path_007", default=None, type=Path, help="007 port-connectivity Excel (.xlsx). Default: autodetect under cwd.")
    p.add_argument("--resource", default=None, type=Path, help="Project info collection Excel (.xlsx). Default: autodetect under cwd.")
    p.add_argument("--sheet007", default=SHEET_007_DEFAULT, help=f"007 sheet (default: {SHEET_007_DEFAULT})")
    p.add_argument(
        "--sheet-res-index",
        type=int,
        default=SHEET_RES_DEFAULT_INDEX,
        help=f"resource sheet index (default: {SHEET_RES_DEFAULT_INDEX})",
    )
    p.add_argument("--out-dir", default=Path("output"), type=Path, help="output directory under cwd (default: ./output)")
    p.add_argument(
        "--skip-prompt-check",
        action="store_true",
        help="skip loading a3_i2 / a3_i3 prompt .py files for phrase parity checks",
    )
    args = p.parse_args(argv)

    try:
        out_final = generate_dw_manage_ip_address_xlsx(
            path_007=args.path_007,
            resource=args.resource,
            sheet007=args.sheet007,
            sheet_res_index=args.sheet_res_index,
            out_dir=args.out_dir,
            prompt_spine_file=None if args.skip_prompt_check else DEFAULT_PROMPT_SPINE,
            prompt_leaf_file=None if args.skip_prompt_check else DEFAULT_PROMPT_LEAF,
            restrict_to_cwd=True,
        )
        print(f"OK: wrote {out_final.name} under {out_final.parent}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
