#!/usr/bin/env python3
"""参数面端口互联 + 资源表 → 计算参数面地址规划（A2/A3 自动识别，确定性，无 LLM）。"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from ipaddress import IPv4Network
from pathlib import Path
from typing import List, Optional, Sequence

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from csm_io import (  # noqa: E402
    WEB_NETWORK_TYPE_NAME,
    detect_csm_scenario,
    fuzzy_column_value,
    gateway_mode_from_row,
    get_a2_server_leaf_df,
    get_a2_switch_demand_markdown,
    get_a3_topology,
    leaf_order_from_demand_md,
    net_resource_markdown,
    read_resource_row,
)
from csm_ip_allocate import (  # noqa: E402
    allocate_a2_csm_ips,
    generate_a3_ip_assignment_table,
    sort_a3_result_df,
)
from csm_segment_rules import (  # noqa: E402
    SEGMENT_COUNT_INSUFFICIENT,
    SwitchGateway,
    plan_switch_gateways_leaf_i3,
    split_ip_range,
)
from dw_manage_segment_rules import IP_POOL_PATTERN, is_non_assignable_plan_segment  # noqa: E402

SHEET_CONNECT_DEFAULT = "参数面端口互联"
SHEET_RES_DEFAULT = "网络资源需求表"
SHEET_RES_DEFAULT_INDEX = SHEET_RES_DEFAULT

DEFAULT_PROMPT_A2 = Path("switch_network_segment_info.py")
DEFAULT_PROMPT_A3 = Path("a3_i3_network_segment_tools_prompt.py")
PROMPT_A3_MARKERS = ("交接机不能共用网段", "网段个数不足", "vlan不足")


def _resolve_local_only(p: Path) -> Path:
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


def _require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = _resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception:
        raise SystemExit(
            f"ERROR: {label} must be located under current working directory.\n"
            f"  resolved: {resolved}\n  cwd: {cwd}"
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


def _autodetect_connect_in_cwd() -> Path:
    for p in _list_excel_files_in_cwd():
        n = p.name
        if ("007" in n) or ("端口连线" in n) or ("端口互联" in n):
            return p
    raise SystemExit("ERROR: cannot autodetect 端口互联/007 excel in cwd.")


def _autodetect_resource_in_cwd() -> Path:
    for p in _list_excel_files_in_cwd():
        n = p.name
        if ("项目信息收集" in n) or ("资源" in n):
            return p
    raise SystemExit("ERROR: cannot autodetect resource excel in cwd.")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_prompt_file(path_or_name: Path) -> Optional[Path]:
    if path_or_name.is_absolute() and path_or_name.is_file():
        return path_or_name
    for base in (Path.cwd(), _SCRIPTS_DIR.parent, _SCRIPTS_DIR.parent.parent.parent):
        cand = (base / path_or_name.name).resolve()
        if cand.is_file():
            return cand
        repo_src = (
            base
            / "src"
            / "manage_agent"
            / "sub_agents"
            / "LLD_IP"
            / "prompt"
            / path_or_name.name
        ).resolve()
        if repo_src.is_file():
            return repo_src
    return None


def _validate_prompt_markers(path: Path, markers: Sequence[str], label: str) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'"""([\s\S]*?)"""', text)
    body = m.group(1) if m else ""
    missing = [x for x in markers if x not in body]
    if missing:
        raise ValueError(f"{label}: prompt missing phrases {missing} in {path}")


def _network_segment_check(switch_list_md: str, net_resource_md: str, result_md: str) -> None:
    if SEGMENT_COUNT_INSUFFICIENT in result_md:
        sw_n = len([ln for ln in switch_list_md.splitlines() if ln.startswith("|") and "---" not in ln]) - 1
        raise ValueError(
            f"网段个数不足：Leaf 交换机 {sw_n} 台，地址池可切分网段数不足（I3 一机一网段）。"
            f" 请扩大「地址池*」或减小「最小规划掩码」。"
        )
    pool_lines = [ln for ln in net_resource_md.splitlines() if "|" in ln and "---" not in ln]
    if len(pool_lines) < 2:
        return
    parts = [p.strip() for p in pool_lines[1].strip("|").split("|")]
    if len(parts) < 2:
        return
    m = IP_POOL_PATTERN.match(parts[1])
    if not m:
        return
    result_lines = [ln for ln in result_md.splitlines() if ln.startswith("|") and "---" not in ln][1:]
    if not result_lines:
        return
    first_seg = [p.strip() for p in result_lines[0].strip("|").split("|")][1]
    mask_bits = [p.strip() for p in result_lines[0].strip("|").split("|")][-1]
    try:
        mask = int(mask_bits)
    except ValueError:
        return
    start_ip = m.group(1)
    network = IPv4Network(f"{start_ip}/{mask}", strict=False)
    if str(network.network_address) not in first_seg:
        raise ValueError("交换机第一个网段不是地址池的起始网段")
    sw_lines = [ln for ln in switch_list_md.splitlines() if ln.startswith("|") and "---" not in ln]
    res_lines = [ln for ln in result_md.splitlines() if ln.startswith("|") and "---" not in ln]
    if len(sw_lines) - 1 != len(res_lines) - 1:
        raise ValueError("交换机网段分配数量不一致")


def plan_leaf_gateways_i3(
    *,
    leaf_order: List[str],
    resource_row: pd.Series,
    ip_pool: str,
    scenario: str,
) -> List[SwitchGateway]:
    raw_mask = str(fuzzy_column_value(resource_row, "最小规划掩码")).strip()
    mask = int(raw_mask.split(".")[0] if "." in raw_mask else raw_mask)
    gateway_mode = gateway_mode_from_row(resource_row)
    vlan_raw = resource_row.get("VLAN*", "")
    subnets = split_ip_range(ip_pool, target_prefix=mask, max_switch_count=len(leaf_order))
    if not subnets:
        raise ValueError("地址池无法切分出可用子网")
    return plan_switch_gateways_leaf_i3(
        switch_list=leaf_order,
        subnets=subnets,
        mask=mask,
        gateway_mode=gateway_mode,
        vlan_raw=vlan_raw,
    )


def generate_csm_address_xlsx(
    *,
    scenario: Optional[str] = None,
    path_connect: Optional[Path] = None,
    resource: Optional[Path] = None,
    sheet_connect: object = SHEET_CONNECT_DEFAULT,
    sheet_res_index: int = SHEET_RES_DEFAULT_INDEX,
    out_dir: Path = Path("output"),
    restrict_to_cwd: bool = True,
    skip_prompt_check: bool = False,
) -> Path:
    if path_connect is None:
        path_connect = _autodetect_connect_in_cwd()
    if resource is None:
        resource = _autodetect_resource_in_cwd()

    if restrict_to_cwd:
        path_connect = _require_under_cwd(path_connect, "connect")
        resource = _require_under_cwd(resource, "resource")
        out_dir = _require_under_cwd(out_dir, "out-dir")
    else:
        path_connect = _resolve_local_only(path_connect)
        resource = _resolve_local_only(resource)
        out_dir = _resolve_local_only(out_dir)

    if not path_connect.is_file():
        raise ValueError(f"connect file not found: {path_connect}")
    if not resource.is_file():
        raise ValueError(f"resource file not found: {resource}")

    detected, keyword, scenario_rule = detect_csm_scenario(path_connect, sheet_connect)
    if scenario is None or str(scenario).strip().lower() in ("", "auto"):
        scenario = detected
    else:
        scenario = str(scenario).strip().lower()
        if scenario not in ("a2", "a3"):
            raise ValueError("scenario must be a2, a3, or auto")
        if scenario != detected:
            print(
                f"WARN: --force-scenario {scenario} 与端口表推断的 {detected} 不一致，仍按强制场景执行。",
                file=sys.stderr,
            )
            scenario_rule = f"强制 scenario={scenario}（端口表推断 {detected}）"

    if not skip_prompt_check:
        rp = _resolve_prompt_file(DEFAULT_PROMPT_A3 if scenario == "a3" else DEFAULT_PROMPT_A2)
        if rp is not None and scenario == "a3":
            _validate_prompt_markers(rp, PROMPT_A3_MARKERS, "A3/I3")

    resource_row, ip_pool = read_resource_row(resource, sheet_res_index)
    net_md = net_resource_markdown(resource_row, scenario)

    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)

    rail_mode: object = ""
    prefix = "A2" if scenario == "a2" else "A3"
    addr_xlsx = run_dir / f"{prefix}{WEB_NETWORK_TYPE_NAME}地址规划.xlsx"

    if scenario == "a2":
        switch_md, leaf_order = get_a2_switch_demand_markdown(path_connect, sheet_connect)
        if not leaf_order:
            leaf_order = leaf_order_from_demand_md(switch_md)
        leaf_gateways = plan_leaf_gateways_i3(
            leaf_order=leaf_order, resource_row=resource_row, ip_pool=ip_pool, scenario=scenario
        )
        from csm_segment_rules import switch_gateways_to_markdown

        segment_md = switch_gateways_to_markdown(leaf_gateways, "leaf交换机")
        _network_segment_check(switch_md, net_md, segment_md)

        for sg in leaf_gateways:
            if is_non_assignable_plan_segment(sg.network_segment):
                raise ValueError(f"网段规划失败: {sg.name} -> {sg.network_segment}")

        server_leaf_df = get_a2_server_leaf_df(path_connect, sheet_connect)
        ip_df = allocate_a2_csm_ips(
            switch_gateways=leaf_gateways,
            server_leaf_df=server_leaf_df,
            ip_pool=ip_pool,
        )
        sheet_addr = f"{WEB_NETWORK_TYPE_NAME}地址_A2"
    else:
        switch_md, switch_to_servers, leaf_order, rail_mode = get_a3_topology(path_connect, sheet_connect)
        leaf_gateways = plan_leaf_gateways_i3(
            leaf_order=leaf_order, resource_row=resource_row, ip_pool=ip_pool, scenario=scenario
        )
        from csm_segment_rules import switch_gateways_to_markdown

        segment_md = switch_gateways_to_markdown(leaf_gateways, "leaf交换机")
        _network_segment_check(switch_md, net_md, segment_md)

        for sg in leaf_gateways:
            if is_non_assignable_plan_segment(sg.network_segment):
                raise ValueError(f"网段规划失败: {sg.name} -> {sg.network_segment}")

        ip_df = generate_a3_ip_assignment_table(
            leaf_gateways, switch_to_servers, ip_pool, leaf_order, rail_mode
        )
        ip_df = sort_a3_result_df(ip_df)
        sheet_addr = f"{WEB_NETWORK_TYPE_NAME}地址_A3"

    ip_df.to_excel(addr_xlsx, sheet_name=sheet_addr, index=False)

    _skill_root = Path(__file__).resolve().parents[2]
    if str(_skill_root) not in sys.path:
        sys.path.insert(0, str(_skill_root))
    from _runtime_shared.network_access_plan import emit_for_plane, filter_assignable_address_rows

    emit_for_plane(
        run_dir,
        plane_key=WEB_NETWORK_TYPE_NAME,
        connect_path=path_connect,
        connect_sheet=sheet_connect,
        address_df=filter_assignable_address_rows(ip_df),
        search_dirs=[out_dir],
    )

    print(f"OK scenario={scenario} rail_mode={rail_mode if scenario == 'a3' else 'n/a'}")
    print(f"  address: {addr_xlsx}")
    return run_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline 计算参数面地址规划（A2/A3 自动识别）")
    ap.add_argument("--connect", type=Path, default=None, help="参数面端口互联表")
    ap.add_argument("--resource", type=Path, default=None, help="项目信息收集表/资源表")
    ap.add_argument("--sheet-connect", default=SHEET_CONNECT_DEFAULT)
    ap.add_argument("--sheet-res-index", default=SHEET_RES_DEFAULT, help=f"资源表 sheet（默认 {SHEET_RES_DEFAULT!r}）")
    ap.add_argument("--out-dir", type=Path, default=Path("output"))
    ap.add_argument("--force-scenario", choices=["a2", "a3", "auto"], default="auto")
    ap.add_argument("--skip-prompt-check", action="store_true")
    ap.add_argument("--no-cwd-restrict", action="store_true")
    args = ap.parse_args()

    scenario = None if args.force_scenario == "auto" else args.force_scenario
    generate_csm_address_xlsx(
        scenario=scenario,
        path_connect=args.connect,
        resource=args.resource,
        sheet_connect=args.sheet_connect,
        sheet_res_index=args.sheet_res_index,
        out_dir=args.out_dir,
        restrict_to_cwd=not args.no_cwd_restrict,
        skip_prompt_check=args.skip_prompt_check,
    )


if __name__ == "__main__":
    main()
