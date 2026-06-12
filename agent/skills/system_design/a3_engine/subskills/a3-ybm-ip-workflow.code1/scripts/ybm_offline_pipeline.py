#!/usr/bin/env python3
"""YBM 离线地址规划主流程（确定性，无 LLM）。

输入：007 + 项目信息收集表（资源表）
输出：output/run_*/{网络平面}_地址规划.xlsx

拓扑：
- i2：单网段（所有服务器共用 1 个子网）
- i3：按 007 末列「接入交换机」一机一网段
"""

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
_A3_YBM_DIR = _THIS_FILE.parent.parent
_REPO_ROOT = _A3_YBM_DIR.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

for p in (str(_SCRIPTS_DIR), str(_THIS_FILE.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from ybm_network_planning_rules import (  # type: ignore
    SEGMENT_COUNT_INSUFFICIENT,
    SEGMENT_USABLE_IP_INSUFFICIENT,
    VLAN_INSUFFICIENT,
    SwitchGateway,
    classify_spine_or_leaf,
    determine_gateway,
    enumerate_usable_ips_in_pool,
    is_non_assignable_plan_segment,
    parse_ip_pool_bounds,
    plan_switch_gateways_leaf_i3,
    plan_switch_gateways_with_sharing,
    split_ip_range,
)
from ybm_allocate_i2_flat import allocate_flat_ybm_ips
from ybm_excel_io import (
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

DEFAULT_NETWORK_PLANE = "计算样本面"
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
    if "cannot autodetect 007 excel" in msg or "007 file not found" in msg:
        hints.append("缺少 007 Excel：请上传/放置 007 表到当前目录（cwd）下，或用 --007 显式指定路径。")
    if "cannot autodetect resource excel" in msg or "resource file not found" in msg:
        hints.append("缺少资源表 Excel：请上传/放置 项目信息收集表/资源表 到当前目录（cwd）下，或用 --resource 显式指定路径。")
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
        uniq: List[str] = []
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


def run_ybm_i2(
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

    # i2：在进入分配前做可操作的容量/参数预检（用户体验：直接停止生成并提示改哪里）
    gateway_cfg = str(gateway_mode).strip()
    try:
        start_ip, end_ip = parse_ip_pool_bounds(ip_pool)
    except Exception as e:
        raise ValueError(
            "规划失败：资源表「地址池*」格式不合法。\n"
            f"  - 地址池*: {ip_pool!r}\n"
            "  - 期望格式: 'A.B.C.D - W.X.Y.Z'\n"
            "  - 建议修改资源表：修正「地址池*」起止 IP，确保起止顺序正确。\n"
        ) from e

    num_nodes = len(ordered_unique)
    total_pool_ips = int(end_ip) - int(start_ip) + 1
    if num_nodes == 0:
        return pd.DataFrame()
    if num_nodes > total_pool_ips:
        raise ValueError(
            "规划失败：i2 地址池容量不足，已停止生成（不会在表格内打标记）。\n"
            f"  - 服务器数量: {num_nodes}\n"
            f"  - 地址池 IP 总数: {total_pool_ips}（含网络/广播/网关等不可用地址）\n"
            "建议修改资源表：扩大「地址池*」范围，或减少需要分配的服务器数量。\n"
        )

    raw_mask = str(mask).strip()
    mask_int = int(raw_mask.split(".")[0] if "." in raw_mask else raw_mask)
    try:
        _ = determine_gateway(f"{start_ip}/{mask_int}", gateway_cfg)
    except Exception as e:
        raise ValueError(
            "规划失败：资源表「网关地址*」配置不合法，已停止生成。\n"
            f"  - 网关地址*: {gateway_cfg!r}\n"
            "  - 期望: 网段起始位/网段结束位/显式 IPv4（且必须落在网段内，且不能为网络地址/广播地址）\n"
            "建议修改资源表：修正「网关地址*」。\n"
        ) from e

    try:
        df, _net = allocate_flat_ybm_ips(
            ordered_unique,
            ip_pool=ip_pool,
            gateway_config=gateway_cfg,
            vlan_raw=str(vlan_raw).strip(),
            min_mask_bits=mask,
            plane_label=network_plane,
        )
        return df
    except ValueError as e:
        # 将算法层错误包装成可操作的用户提示（避免仅看到“无法找到合适子网掩码”等抽象描述）
        msg = str(e).strip() or repr(e)
        raise ValueError(
            "规划失败：i2 无法在地址池内完成顺序分配，已停止生成（不会在表格内打标记）。\n"
            f"  - 地址池*: {ip_pool!r}\n"
            f"  - 最小规划掩码: /{mask_int}\n"
            f"  - 网关地址*: {gateway_cfg!r}\n"
            f"  - 服务器数量: {num_nodes}\n"
            f"  - 详细原因: {msg}\n"
            "建议修改资源表：扩大「地址池*」，或调整「最小规划掩码」（让单网段更大以容纳更多节点），必要时检查「网关地址*」。\n"
        ) from e


def run_ybm_i3(
    *,
    path_007: Path,
    resource: Path,
    network_plane: str,
    sheet007: str,
    sheet_res_index: int,
    server_substring: str,
    split_spine_leaf: bool,
    fail_on_insufficient: bool,
) -> pd.DataFrame:
    switch_to_servers = read_007_leaf_to_servers(
        path_007, sheet007, server_substring=server_substring, network_plane=network_plane
    )
    switch_list = list(switch_to_servers.keys())

    res_row = read_resource_row_for_plane(resource, sheet_res_index, network_plane)
    ip_pool = str(res_row.get("地址池*", "")).strip()
    if not ip_pool:
        raise ValueError("resource: 地址池* is empty")
    mask = int(fuzzy_get(res_row, "最小规划掩码"))
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

    if fail_on_insufficient:
        segment_shortage = [sg for sg in switch_gateways if sg.network_segment == SEGMENT_COUNT_INSUFFICIENT]
        vlan_shortage = [sg for sg in switch_gateways if str(sg.vlan).strip() == VLAN_INSUFFICIENT]
        ip_shortage: List[tuple] = []
        for sg in switch_gateways:
            if is_non_assignable_plan_segment(sg.network_segment):
                continue
            servers = switch_to_servers.get(sg.name, [])
            network = IPv4Network(sg.network_segment, strict=False)
            gateway_ip = IPv4Address(sg.gateway)
            usable_ips = enumerate_usable_ips_in_pool(network, gateway_ip, pool_start, pool_end)
            if len(servers) > len(usable_ips):
                ip_shortage.append((sg, len(servers), len(usable_ips)))

        if segment_shortage or vlan_shortage or ip_shortage:
            lines: List[str] = ["规划失败：容量不足，已停止生成（不会在表格内打标记）。", "问题明细："]
            if segment_shortage:
                lines.append(f"  - 网段个数不足: 需要 {len(switch_list)} 个子网，但地址池在 /{mask} 下仅可切出 {len(subnets)} 个")
                preview = [sg.name for sg in segment_shortage[:20]]
                lines.append(f"    受影响接入交换机示例(前{len(preview)}个): {preview}")
                lines.append("    建议修改资源表：扩大「地址池*」范围，或调整「最小规划掩码」（掩码越大单网段越大但可切分数量更少；要更多子网需把 /xx 调小）。")
            if vlan_shortage:
                preview = [sg.name for sg in vlan_shortage[:20]]
                lines.append(f"  - VLAN 不足: VLAN* 无法覆盖所有子网（受影响接入交换机示例(前{len(preview)}个): {preview}）")
                lines.append("    建议修改资源表：扩大「VLAN*」区间（如 100-199），或改为固定 VLAN（单值）。")
            if ip_shortage:
                lines.append("  - 可用 IP 不足（按接入交换机/子网统计）：")
                for sg, need, cap in ip_shortage[:20]:
                    lines.append(f"    - {sg.name}: 子网 {sg.network_segment} 可用IP={cap} < 服务器数={need}")
                if len(ip_shortage) > 20:
                    lines.append(f"    ... 另有 {len(ip_shortage) - 20} 个接入交换机同类问题")
                lines.append("    建议修改资源表：扩大「地址池*」，或让单网段更大（调整「最小规划掩码」），或减少该接入交换机关联服务器数。")
            lines.append("如需仍生成并在表内标记问题，请加参数 --allow-insufficient。")
            raise ValueError("\n".join(lines))

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


def generate_ybm_ip_xlsx(
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
        df = run_ybm_i2(
            path_007=path_007,
            resource=resource,
            network_plane=network_plane,
            sheet007=sheet007,
            sheet_res_index=sheet_res_index,
            server_substring=server_substring,
        )
    elif top == "i3":
        df = run_ybm_i3(
            path_007=path_007,
            resource=resource,
            network_plane=network_plane,
            sheet007=sheet007,
            sheet_res_index=sheet_res_index,
            server_substring=server_substring,
            split_spine_leaf=i3_split_spine_leaf,
            fail_on_insufficient=fail_on_insufficient,
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

    _skill_root = Path(__file__).resolve().parents[2]
    if str(_skill_root) not in sys.path:
        sys.path.insert(0, str(_skill_root))
    from _runtime_shared.network_access_plan import emit_for_plane, filter_assignable_address_rows

    emit_for_plane(
        run_dir,
        plane_key=network_plane,
        connect_path=path_007,
        connect_sheet=sheet007,
        address_df=filter_assignable_address_rows(df),
        search_dirs=[out_dir],
    )

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
                "  i2 — 全项目节点共用同一IPv4子网顺序分配（二层汇聚场景）。",
                "  i3 — 每台接入交换机（末列）独立子网（LEAF 一机一网段）。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return out_final


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Offline A3 YBM IP planning — i2 flat / i3 per-leaf")
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
        "--no-server-filter",
        action="store_true",
        help="禁用 007 首列服务器名过滤（等价于 --server-substring 空字符串；用于 PowerShell 下难以传空值的场景）",
    )
    p.add_argument(
        "--i3-split-spine-leaf",
        action="store_true",
        help="仅在 --topology i3 下生效：接入交换机名单中区分 SPINE/LEAF，"
        "SPINE 可走 i2「多机共享网段」累加，LEAF 走一机一网段",
    )
    p.add_argument(
        "--skip-prompt-check",
        action="store_true",
        help="跳过 prompt .py 的短语对齐检查",
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
    server_substring = "" if args.no_server_filter else (args.server_substring or "")

    try:
        out = generate_ybm_ip_xlsx(
            topology=args.topology,
            path_007=args.path_007,
            resource=args.resource,
            network_plane=args.network_plane,
            sheet007=args.sheet007,
            sheet_res_index=args.sheet_resource,
            out_dir=args.out_dir,
            server_substring=server_substring,
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
    except SystemExit as e:
        # 来自自动探测/路径约束等的退出，补齐“上传缺失文件/如何提供路径”的用户提示
        print(_format_user_facing_error(Exception(str(e))), file=sys.stderr)
        return 2
    except Exception as e:
        print(_format_user_facing_error(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

