#!/usr/bin/env python3
"""007 + 项目信息收集表 → 管存面（GCM）IP 地址规划 Excel（确定性，无 LLM）。i2：单网段；i3：接入交换机（末列）一机一网段。"""

from __future__ import annotations

import argparse
import re
import sys
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

_THIS_FILE = Path(__file__).resolve()
_A3_GCM_DIR = _THIS_FILE.parent.parent
_REPO_ROOT = _A3_GCM_DIR.parent
_DW_RULES_DIR = _REPO_ROOT / "a3-dw-manage-ip-workflow.code1" / "scripts"

for p in (str(_DW_RULES_DIR), str(_THIS_FILE.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from dw_manage_segment_rules import (  # type: ignore
    SEGMENT_COUNT_INSUFFICIENT,
    SEGMENT_USABLE_IP_INSUFFICIENT,
    VLAN_INSUFFICIENT,
    SwitchGateway,
    classify_spine_or_leaf,
    enumerate_usable_ips_in_pool,
    is_non_assignable_plan_segment,
    parse_ip_pool_bounds,
    plan_switch_gateways_leaf_i3,
    plan_switch_gateways_with_sharing,
    split_ip_range,
)
from gcm_i2_allocation import allocate_flat_gcm_ips
from gcm_io_utils import (
    SHEET_007_DEFAULT,
    SHEET_RES_DEFAULT,
    autodetect_007_in_cwd,
    autodetect_resource_in_cwd,
    excel_sheet_title,
    fuzzy_get,
    read_007_leaf_to_servers,
    read_resource_row_for_plane,
    require_under_cwd,
    resolve_local_only,
)

PROMPT_SPINE_MARKERS = ("多个或所有交换机使用同一网段", "顺次累加节点数量")
PROMPT_LEAF_MARKERS = ("交接机不能共用网段", "网段个数不足", "vlan不足")

DEFAULT_NETWORK_PLANE = "计算管存面"
DEFAULT_SERVER_SUBSTRING = "AT800T"

INSUFFICIENT_MARKERS = (SEGMENT_COUNT_INSUFFICIENT, SEGMENT_USABLE_IP_INSUFFICIENT, VLAN_INSUFFICIENT)


def _format_user_facing_error(e: Exception) -> str:
    msg = str(e).strip() or repr(e)

    hints: List[str] = []
    if "007:" in msg or msg.startswith("007"):
        hints.append("检查 007 表是否选对了 sheet（用 --sheet007 指定），以及首列/末列是否分别为服务器名/接入交换机。")
        hints.append("若用了 --server-substring，请确认它能命中首列服务器名；不确定可先不传该参数。")
    if "resource:" in msg or msg.startswith("resource"):
        hints.append("检查资源表列名：网络平面、地址池*、最小规划掩码、网关地址*、VLAN* 是否齐全。")
        hints.append("检查 --network-plane 是否与资源表「网络平面」列取值完全一致；必要时调整 --sheet-res-index。")
    if "地址池" in msg or "VLAN" in msg or "vlan" in msg:
        hints.append("地址池/掩码/VLAN 规划不足时，通常需要扩大地址池范围、调整最小规划掩码(/xx)、或扩大 VLAN 区间。")
    if "网关" in msg and ("不在网段" in msg or "cannot be network/broadcast" in msg):
        hints.append("资源表「网关地址*」应为：网段起始位/网段结束位，或网段内合法 IPv4（不能是网络地址/广播地址）。")

    out = ["失败原因：", f"  - {msg}"]
    if hints:
        out.append("建议排查/修改：")
        for h in hints:
            out.append(f"  - {h}")
    return "\n".join(out)


def _summarize_insufficient_markers(df: "pd.DataFrame") -> Dict[str, List[str]]:
    if df is None or df.empty or "设备名称" not in df.columns:
        return {}
    by_marker: Dict[str, List[str]] = {}
    device_col = df["设备名称"].astype(str)
    for marker in INSUFFICIENT_MARKERS:
        hit_rows = df[df.astype(str).eq(marker).any(axis=1)]
        if hit_rows.empty:
            continue
        names = hit_rows.get("设备名称", device_col).astype(str).tolist()
        by_marker[marker] = [n for n in names if n]
    return by_marker


def _raise_on_insufficient_if_needed(df: "pd.DataFrame", *, fail_on_insufficient: bool) -> None:
    if not fail_on_insufficient:
        return
    hits = _summarize_insufficient_markers(df)
    if not hits:
        return

    lines: List[str] = ["规划结果包含不可分配标记，已按 --fail-on-insufficient 中止生成。"]
    for marker, names in hits.items():
        uniq = []
        seen = set()
        for n in names:
            if n in seen:
                continue
            seen.add(n)
            uniq.append(n)
        preview = uniq[:20]
        lines.append(f"  - {marker}: {len(names)} 行（涉及设备 {len(uniq)} 台），示例: {preview}")
    lines.append("建议修改：扩大 地址池* / 调整 最小规划掩码 / 扩大 VLAN* 区间，或减少对应接入交换机关联服务器数。")
    raise ValueError("\n".join(lines))


def _resolve_prompt_template_file(path_or_name: Path) -> Optional[Path]:
    if path_or_name.is_absolute():
        return path_or_name if path_or_name.is_file() else None
    cwd_candidate = (Path.cwd() / path_or_name).resolve()
    if cwd_candidate.is_file():
        return cwd_candidate
    repo_candidate = (_REPO_ROOT / path_or_name).resolve()
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


def _timestamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_out_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


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


def run_gcm_i2(
    *,
    path_007: Path,
    resource: Path,
    network_plane: str,
    sheet007: str,
    sheet_res_index: int,
    server_substring: str,
) -> pd.DataFrame:
    mapping = read_007_leaf_to_servers(
        path_007, sheet007, server_substring=server_substring, network_plane=network_plane
    )

    equip_df_parts: List[str] = []
    for _leaf, servers in mapping.items():
        for s in servers:
            equip_df_parts.append(s)
    seen = set()
    ordered_unique: List[str] = []
    for s in equip_df_parts:
        if s not in seen:
            seen.add(s)
            ordered_unique.append(s)

    r = read_resource_row_for_plane(resource, sheet_res_index, network_plane)
    ip_pool = str(r.get("地址池*", "")).strip()
    if not ip_pool:
        raise ValueError("resource: 地址池* is empty")
    mask = fuzzy_get(r, "最小规划掩码")
    if mask is None:
        raise ValueError("resource: 最小规划掩码 missing")
    gateway_mode = r.get("网关地址*", "")
    vlan_raw = r.get("VLAN*", "")

    df, _net = allocate_flat_gcm_ips(
        ordered_unique,
        ip_pool=ip_pool,
        gateway_config=str(gateway_mode).strip(),
        vlan_raw=str(vlan_raw).strip(),
        min_mask_bits=mask,
        plane_label=network_plane,
    )
    return df


def run_gcm_i3(
    *,
    path_007: Path,
    resource: Path,
    network_plane: str,
    sheet007: str,
    sheet_res_index: int,
    server_substring: str,
    split_spine_leaf: bool,
) -> pd.DataFrame:
    switch_to_servers = read_007_leaf_to_servers(
        path_007, sheet007, server_substring=server_substring, network_plane=network_plane
    )
    switch_list = list(switch_to_servers.keys())

    res_row = read_resource_row_for_plane(resource, sheet_res_index, network_plane)
    ip_pool = str(res_row.get("地址池*", "")).strip()
    if not ip_pool:
        raise ValueError("resource: 地址池* is empty")
    raw_mask = str(fuzzy_get(res_row, "最小规划掩码")).strip()
    mask = int(raw_mask.split(".")[0] if "." in raw_mask else raw_mask)
    gateway_mode = res_row.get("网关地址*", "")
    vlan_raw = res_row.get("VLAN*", "")

    pool_start, pool_end = parse_ip_pool_bounds(ip_pool)

    subnets = split_ip_range(ip_pool, target_prefix=mask, max_switch_count=len(switch_list))
    if not subnets:
        raise ValueError(
            "规划失败：地址池无法切出满足最小规划掩码的子网。\n"
            f"  - 地址池*: {ip_pool!r}\n"
            f"  - 最小规划掩码: /{mask}\n"
            f"  - 需要至少 {len(switch_list)} 个子网（与接入交换机数量一致）\n"
            "  - 建议: 扩大地址池范围，或把「最小规划掩码」调大（例如 /26 → /25，单个子网更大但可切分数量更少；"
            "若要更多子网需调小如 /26 → /27）"
        )

    switch_gateways: List[SwitchGateway]
    if split_spine_leaf:
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
    else:
        switch_gateways = plan_switch_gateways_leaf_i3(
            switch_list=switch_list,
            subnets=subnets,
            mask=mask,
            gateway_mode=gateway_mode,
            vlan_raw=vlan_raw,
            vlan_subnet_offset=0,
        )

    plane = network_plane
    rows_final: List[dict] = []

    for sg in switch_gateways:
        leaf_name = sg.name
        servers = switch_to_servers.get(leaf_name, [])

        if is_non_assignable_plan_segment(sg.network_segment):
            marker = sg.network_segment
            for srv in servers:
                rows_final.append(
                    {
                        "设备名称": srv,
                        f"{plane}地址": marker,
                        f"{plane}掩码": str(sg.mask),
                        f"{plane}网关": "",
                        f"{plane}VLAN": str(sg.vlan),
                        "绑定模式": "bond1",
                    }
                )
            continue

        network = IPv4Network(sg.network_segment, strict=False)
        gateway_ip = IPv4Address(sg.gateway)
        usable_ips = enumerate_usable_ips_in_pool(network, gateway_ip, pool_start, pool_end)

        for i, srv in enumerate(servers):
            if i < len(usable_ips):
                addr = str(usable_ips[i])
                gw_cell = str(gateway_ip)
            else:
                addr = SEGMENT_USABLE_IP_INSUFFICIENT
                gw_cell = ""
            rows_final.append(
                {
                    "设备名称": srv,
                    f"{plane}地址": addr,
                    f"{plane}掩码": str(sg.mask),
                    f"{plane}网关": gw_cell,
                    f"{plane}VLAN": str(sg.vlan),
                    "绑定模式": "bond1",
                }
            )

    return pd.DataFrame(rows_final)


def generate_gcm_ip_xlsx(
    *,
    topology: str,
    path_007: Optional[Path] = None,
    resource: Optional[Path] = None,
    network_plane: str = DEFAULT_NETWORK_PLANE,
    sheet007: str = SHEET_007_DEFAULT,
    sheet_res_index: object = SHEET_RES_DEFAULT,
    out_dir: Path = Path("output"),
    server_substring: str = DEFAULT_SERVER_SUBSTRING,
    i3_split_spine_leaf: bool = False,
    prompt_spine_file: Optional[Path] = None,
    prompt_leaf_file: Optional[Path] = None,
    restrict_to_cwd: bool = True,
    fail_on_insufficient: bool = True,
) -> Path:
    if path_007 is None:
        path_007 = autodetect_007_in_cwd()
    if resource is None:
        resource = autodetect_resource_in_cwd()

    if restrict_to_cwd:
        path_007 = require_under_cwd(path_007, "007")
        resource = require_under_cwd(resource, "resource")
        out_dir = require_under_cwd(out_dir, "out-dir")
    else:
        path_007 = resolve_local_only(path_007)
        resource = resolve_local_only(resource)
        out_dir = resolve_local_only(out_dir)

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

    top = topology.strip().lower()
    if top == "i2":
        df = run_gcm_i2(
            path_007=path_007,
            resource=resource,
            network_plane=network_plane,
            sheet007=sheet007,
            sheet_res_index=sheet_res_index,
            server_substring=server_substring,
        )
    elif top == "i3":
        df = run_gcm_i3(
            path_007=path_007,
            resource=resource,
            network_plane=network_plane,
            sheet007=sheet007,
            sheet_res_index=sheet_res_index,
            server_substring=server_substring,
            split_spine_leaf=i3_split_spine_leaf,
        )
    else:
        raise ValueError("topology must be i2 or i3")

    _raise_on_insufficient_if_needed(df, fail_on_insufficient=fail_on_insufficient)

    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    _ensure_out_dir(run_dir)

    outfile_name = f"{network_plane}_地址规划.xlsx"
    out_final = run_dir / outfile_name
    sheet_nm = excel_sheet_title(f"{network_plane}地址规划")

    with pd.ExcelWriter(out_final, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=sheet_nm)

    meta_path = run_dir / "README_run.txt"
    meta_path.write_text(
        "\n".join(
            [
                f"topology={topology}",
                f"network_plane={network_plane}",
                f"sheet007={sheet007}",
                f"sheet_res_index={sheet_res_index}",
                f"server_substring={server_substring!r}",
                f"i3_split_spine_leaf={i3_split_spine_leaf}",
                "",
                "语义说明：",
                "  i2 — 等价于离线化 a3_l2_ip_address：全项目节点共用同一IPv4子网顺序分配（二层汇聚场景）。",
                "  i3 — 等价于离线化 a3_ywm_ip_address 网段诉求：每台接入交换机（末列）独立子网，"
                "与 a3_i3_network_segment_tools_prompt 的规则一致（LEAF 一机一网段）。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return out_final


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Offline A3 GCM（管存面）IP planning — i2 flat / i3 per-leaf")
    p.add_argument(
        "--topology",
        choices=("i2", "i3"),
        required=True,
        help="i2=单网段全节点分配（二层）；i3=按007末列交换机一机一网段（三层LEAF接入）",
    )
    p.add_argument(
        "--network-plane",
        default=DEFAULT_NETWORK_PLANE,
        help=f"资源表 网络平面 列取值（默认 {DEFAULT_NETWORK_PLANE!r}）",
    )
    p.add_argument("--007", dest="path_007", default=None, type=Path)
    p.add_argument("--resource", default=None, type=Path)
    p.add_argument("--sheet007", default=SHEET_007_DEFAULT, help=f"007 sheet（默认 {SHEET_007_DEFAULT!r}）")
    p.add_argument(
        "--sheet-res-index",
        "--sheet-resource",
        dest="sheet_resource",
        default=SHEET_RES_DEFAULT,
        help=f"资源表 sheet（默认 {SHEET_RES_DEFAULT!r}）",
    )
    p.add_argument("--out-dir", default=Path("output"), type=Path)
    p.add_argument(
        "--server-substring",
        default=DEFAULT_SERVER_SUBSTRING,
        help="仅保留服务器名包含该子串的行（默认 AT800T；空字符串表示不过滤）",
    )
    p.add_argument(
        "--i3-split-spine-leaf",
        action="store_true",
        help="仅在 --topology i3 下生效：接入交换机名单中区分 SPINE/LEAF，"
        "SPINE 可走 i2「多机共享网段」累加，LEAF 走一机一网段（与离线带外流水线一致）",
    )
    p.add_argument(
        "--skip-prompt-check",
        action="store_true",
        help="跳过 a3_gcm 下 i2/i3 prompt .py 的短语对齐检查",
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--allow-insufficient",
        action="store_true",
        help="允许容量不足时继续生成 Excel，并在表内标记 网段个数不足/可用IP不足/vlan不足（默认：发现这些标记即停止生成并打印汇总）",
    )
    g.add_argument(
        "--fail-on-insufficient",
        action="store_true",
        help="发现 网段个数不足/可用IP不足/vlan不足 即停止生成并打印汇总（默认行为；仅用于显式声明）",
    )
    p.add_argument(
        "--prompt-spine-file",
        default=None,
        type=Path,
        help="（可选）启用 prompt 短语对齐检查：指定 i2/SPINE prompt 模板文件路径",
    )
    p.add_argument(
        "--prompt-leaf-file",
        default=None,
        type=Path,
        help="（可选）启用 prompt 短语对齐检查：指定 i3/LEAF prompt 模板文件路径",
    )
    args = p.parse_args(argv)

    try:
        out = generate_gcm_ip_xlsx(
            topology=args.topology,
            path_007=args.path_007,
            resource=args.resource,
            network_plane=args.network_plane,
            sheet007=args.sheet007,
            sheet_res_index=args.sheet_resource,
            out_dir=args.out_dir,
            server_substring=args.server_substring or "",
            i3_split_spine_leaf=args.i3_split_spine_leaf,
            prompt_spine_file=None
            if args.skip_prompt_check
            else (args.prompt_spine_file if args.prompt_spine_file else None),
            prompt_leaf_file=None if args.skip_prompt_check else (args.prompt_leaf_file if args.prompt_leaf_file else None),
            restrict_to_cwd=True,
            fail_on_insufficient=(not args.allow_insufficient),
        )
        print(f"OK: wrote {out.name} under {out.parent}")
        return 0
    except Exception as e:
        print(_format_user_facing_error(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
