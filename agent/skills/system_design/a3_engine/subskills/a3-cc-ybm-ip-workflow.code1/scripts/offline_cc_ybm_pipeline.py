#!/usr/bin/env python3
"""样本面端口互联 | 数据面端口互联 + 资源表 → 存储样本面地址规划.xlsx（L2/L3 与设备场景自动识别，确定性，无 LLM）。"""

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

from cc_ybm_io import (  # noqa: E402
    NET_PLANE,
    WEB_NETWORK_TYPE_NAME,
    classify_device_scenario,
    detect_cc_ybm_layer,
    fuzzy_column_value,
    get_node_info,
    get_server_info_od1600t,
    get_switch_to_nodes,
    net_resource_markdown,
    read_od1600t_resource_row,
    read_resource_row,
    resolve_connect_sheet,
    resolve_leaf_spine_mapping,
    switch_demand_markdown,
)
from cc_ybm_ip_allocate import (  # noqa: E402
    allocate_od1600t_ips,
    allocate_osa800_independent_ips,
    allocate_osp_ybm_ips,
)
from cc_ybm_segment_rules import (  # noqa: E402
    SEGMENT_COUNT_INSUFFICIENT,
    SwitchGateway,
    plan_switch_gateways_glm_i2,
    plan_switch_gateways_leaf_i3,
    split_ip_range,
    switch_gateways_to_dataframe,
    transfer_gateways_to_spines,
)
from dw_manage_segment_rules import IP_POOL_PATTERN  # noqa: E402

SHEET_CONNECT_DEFAULT = "样本面端口互联 | 数据面端口互联"
SHEET_RES_DEFAULT = "网络资源需求表"
SHEET_RES_DEFAULT_INDEX = SHEET_RES_DEFAULT
FALLBACK_SHEET_HINT = "计算管理面端口互联"

DEFAULT_PROMPT_I2 = Path("a3_i2_network_segment_tools_prompt.py")
DEFAULT_PROMPT_I3 = Path("a3_i3_network_segment_tools_prompt.py")
PROMPT_I2_MARKERS = ("多个或所有交换机使用同一网段", "顺次累加节点数量")
PROMPT_I3_MARKERS = ("交接机不能共用网段", "网段个数不足", "vlan不足")


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
        if ("项目信息收集" in n) or ("资源" in p.name):
            return p
    raise SystemExit("ERROR: cannot autodetect resource excel in cwd.")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_prompt_file(path_or_name: Path) -> Optional[Path]:
    if path_or_name.is_absolute() and path_or_name.is_file():
        return path_or_name
    for candidate in (
        (Path.cwd() / path_or_name).resolve(),
        (_SCRIPTS_DIR.parent / path_or_name.name).resolve(),
        (
            _SCRIPTS_DIR.parent.parent.parent
            / "src"
            / "manage_agent"
            / "sub_agents"
            / "LLD_IP"
            / "prompt"
            / path_or_name.name
        ).resolve(),
    ):
        if candidate.is_file():
            return candidate
    return None


def _validate_prompt_markers(path: Path, markers: Sequence[str], label: str) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'"""([\s\S]*?)"""', text)
    body = m.group(1) if m else ""
    missing = [x for x in markers if x not in body]
    if missing:
        raise ValueError(f"{label}: prompt missing phrases {missing} in {path}")


def _network_segment_check(
    switch_list_md: str,
    net_resource_md: str,
    result_md: str,
    layer: str,
) -> None:
    if SEGMENT_COUNT_INSUFFICIENT in result_md:
        sw_n = (
            len([ln for ln in switch_list_md.splitlines() if ln.startswith("|") and "---" not in ln])
            - 1
        )
        if layer == "L3":
            raise ValueError(
                f"网段个数不足：Leaf 交换机 {sw_n} 台，地址池可切分网段数不足（I3 一机一网段）。"
            )
        raise ValueError(
            f"网段个数不足：Leaf 交换机 {sw_n} 台，I2 共用网段时单网段容量或地址池子网数不足。"
        )
    pool_line = [ln for ln in net_resource_md.splitlines() if "|" in ln and "---" not in ln]
    if len(pool_line) < 2:
        return
    parts = [p.strip() for p in pool_line[1].strip("|").split("|")]
    if len(parts) < 2:
        return
    ip_pool = parts[1]
    m = IP_POOL_PATTERN.match(ip_pool)
    if not m:
        return
    result_lines = [
        ln
        for ln in result_md.splitlines()
        if ln.startswith("|") and "---" not in ln and "leaf" not in ln.lower()
    ]
    if not result_lines:
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
    check_ip = str(network.network_address)
    if check_ip not in first_seg:
        raise ValueError("交换机第一个网段不是地址池的起始网段")
    sw_lines = [ln for ln in switch_list_md.splitlines() if ln.startswith("|") and "---" not in ln]
    res_lines = [ln for ln in result_md.splitlines() if ln.startswith("|") and "---" not in ln]
    if len(sw_lines) - 1 != len(res_lines) - 1:
        raise ValueError("交换机网段分配数量不一致")


def _pick_fallback_sheet(xf: pd.ExcelFile, primary_sheet: object) -> Optional[object]:
    if SHEET_COMPUTE_MANAGE_FALLBACK in xf.sheet_names:
        return SHEET_COMPUTE_MANAGE_FALLBACK
    if isinstance(primary_sheet, str) and "样本面" in primary_sheet:
        candidate = primary_sheet.replace("样本面", "计算管理面").replace("数据面", "管理面")
        if candidate in xf.sheet_names:
            return candidate
    for name in xf.sheet_names:
        if FALLBACK_SHEET_HINT in name or ("计算" in name and "管理面" in name):
            return name
    return None


def plan_leaf_gateways(
    *,
    layer: str,
    switch_to_nodes: dict,
    resource_row: pd.Series,
    ip_pool: str,
) -> tuple[List[SwitchGateway], str]:
    switch_list = list(switch_to_nodes.keys())
    raw_mask = str(fuzzy_column_value(resource_row, "最小规划掩码")).strip()
    mask = int(raw_mask.split(".")[0] if "." in raw_mask else raw_mask)
    gateway_mode = resource_row.get("网关地址*", "")
    vlan_raw = resource_row.get("VLAN*", "")
    subnets = split_ip_range(ip_pool, target_prefix=mask, max_switch_count=len(switch_list))
    if not subnets:
        raise ValueError("地址池无法切分出可用子网")

    if layer.upper() == "L2":
        leaf_rows, _, _ = plan_switch_gateways_glm_i2(
            switch_list=switch_list,
            switch_to_nodes=switch_to_nodes,
            subnets=subnets,
            mask=mask,
            gateway_mode=gateway_mode,
            vlan_raw=vlan_raw,
        )
    else:
        leaf_rows = plan_switch_gateways_leaf_i3(
            switch_list=switch_list,
            subnets=subnets,
            mask=mask,
            gateway_mode=gateway_mode,
            vlan_raw=vlan_raw,
        )

    from cc_ybm_segment_rules import switch_gateways_to_markdown

    md = switch_gateways_to_markdown(leaf_rows, header_switch="leaf交换机")
    return leaf_rows, md


def _write_outputs(
    run_dir: Path,
    *,
    layer: str,
    leaf_gateways: List[SwitchGateway],
    spine_gateways: List[SwitchGateway],
    address_df: pd.DataFrame,
    scenario: str,
    write_segment: bool,
) -> Path:
    if write_segment:
        segment_display = spine_gateways if layer == "L2" else leaf_gateways
        segment_col = "spine交换机" if layer == "L2" else "leaf交换机"
        out_segment = run_dir / f"A3{WEB_NETWORK_TYPE_NAME}网段规划.xlsx"
        with pd.ExcelWriter(out_segment, engine="openpyxl") as writer:
            switch_gateways_to_dataframe(segment_display, segment_col).to_excel(
                writer, sheet_name=f"{WEB_NETWORK_TYPE_NAME}网段规划", index=False
            )
            if layer == "L2":
                switch_gateways_to_dataframe(leaf_gateways, "leaf交换机").to_excel(
                    writer, sheet_name="Leaf网段", index=False
                )

    sheet_addr = (
        f"{WEB_NETWORK_TYPE_NAME}地址规划"
        if scenario != "od1600t"
        else f"{WEB_NETWORK_TYPE_NAME}地址规划"
    )
    out_addr = run_dir / f"A3{WEB_NETWORK_TYPE_NAME}地址规划.xlsx"
    with pd.ExcelWriter(out_addr, engine="openpyxl") as writer:
        address_df.to_excel(writer, sheet_name=sheet_addr, index=False)

    out_ip = run_dir / f"A3{WEB_NETWORK_TYPE_NAME}IP地址规划.xlsx"
    with pd.ExcelWriter(out_ip, engine="openpyxl") as writer:
        address_df.to_excel(writer, sheet_name=f"{WEB_NETWORK_TYPE_NAME}IP地址规划", index=False)

    return out_ip


def generate_cc_ybm_ip_address_xlsx(
    *,
    layer: Optional[str] = None,
    path_connect: Optional[Path] = None,
    resource: Optional[Path] = None,
    sheet_connect: object = SHEET_CONNECT_DEFAULT,
    sheet_res_index: int = SHEET_RES_DEFAULT_INDEX,
    out_dir: Path = Path("output"),
    prompt_i2_file: Optional[Path] = DEFAULT_PROMPT_I2,
    prompt_i3_file: Optional[Path] = DEFAULT_PROMPT_I3,
    restrict_to_cwd: bool = True,
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

    gateway_pos = ""
    layer_rule = ""
    if layer is None or str(layer).strip().lower() in ("", "auto"):
        layer, gateway_pos, layer_rule = detect_cc_ybm_layer(resource, sheet_res_index)
    else:
        layer = str(layer).upper()
        if layer not in ("L2", "L3"):
            raise ValueError("layer must be L2, L3, or auto")
        _, gateway_pos, layer_rule = detect_cc_ybm_layer(resource, sheet_res_index)
        expected = "L3" if gateway_pos == "LEAF" else "L2"
        if layer != expected:
            print(
                f"WARN: --force-layer {layer} 与资源表网关位置*={gateway_pos!r} "
                f"推断的 {expected} 不一致，仍按强制层级执行。",
                file=sys.stderr,
            )
            layer_rule = f"强制 layer={layer}（资源表网关位置*={gateway_pos!r}）"

    if prompt_i2_file is not None:
        rp = _resolve_prompt_file(prompt_i2_file)
        if rp is not None:
            _validate_prompt_markers(rp, PROMPT_I2_MARKERS, "I2/L2")
    if prompt_i3_file is not None:
        rp = _resolve_prompt_file(prompt_i3_file)
        if rp is not None:
            _validate_prompt_markers(rp, PROMPT_I3_MARKERS, "I3/L3")

    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)

    node_df = get_node_info(path_connect, sheet_connect)
    scenario = classify_device_scenario(node_df)

    leaf_gateways: List[SwitchGateway] = []
    spine_gateways: List[SwitchGateway] = []
    address_df: pd.DataFrame

    if scenario == "od1600t":
        equip_df = get_server_info_od1600t(path_connect, sheet_connect)
        od_row, ip_pool_od = read_od1600t_resource_row(resource, sheet_res_index)
        mask_od = fuzzy_column_value(od_row, "最小规划掩码") or "30"
        vlan_pool = str(od_row.get("VLAN*", "")).strip()
        address_df = allocate_od1600t_ips(equip_df, ip_pool_od, str(mask_od), vlan_pool)
        write_segment = False
    else:
        switch_to_nodes = get_switch_to_nodes(path_connect, sheet_connect)
        resource_row, ip_pool = read_resource_row(resource, sheet_res_index)
        net_md = net_resource_markdown(resource_row)
        sw_header = "交换机" if layer == "L2" else "leaf交换机"
        switch_md = switch_demand_markdown(switch_to_nodes, sw_header)
        gateway_info = str(resource_row.get("网关地址*", "")).strip()
        vlan_raw = str(resource_row.get("VLAN*", "")).strip()

        leaf_gateways, segment_md = plan_leaf_gateways(
            layer=layer,
            switch_to_nodes=switch_to_nodes,
            resource_row=resource_row,
            ip_pool=ip_pool,
        )
        _network_segment_check(switch_md, net_md, segment_md, layer)

        if layer == "L2":
            resolved_sheet = resolve_connect_sheet(path_connect, sheet_connect)
            xf = pd.ExcelFile(path_connect)
            fb = _pick_fallback_sheet(xf, resolved_sheet)
            leaf_spine = resolve_leaf_spine_mapping(
                path_connect,
                resolved_sheet,
                [sg.name for sg in leaf_gateways],
                fallback_sheet=fb,
            )
            spine_gateways = [
                sg
                for sg in transfer_gateways_to_spines(leaf_spine, leaf_gateways)
                if "spine" in sg.name.lower()
            ]

        if scenario == "osa800_only":
            osa800_df = node_df[node_df["节点名称"].str.contains("OSA800", case=False, na=False)]
            address_df = allocate_osa800_independent_ips(
                osa800_df, ip_pool, gateway_info, vlan_raw
            )
        else:
            address_df = allocate_osp_ybm_ips(
                original_df=node_df,
                switch_network_segment_info=leaf_gateways,
                ip_pool=ip_pool,
            )
        write_segment = True

    if address_df.empty:
        raise ValueError("没有生成任何分配结果")

    out_ip = _write_outputs(
        run_dir,
        layer=layer,
        leaf_gateways=leaf_gateways,
        spine_gateways=spine_gateways,
        address_df=address_df,
        scenario=scenario,
        write_segment=write_segment,
    )

    source_script = "a3_cc_ybm_ip_address.py"
    meta = {
        "layer": layer,
        "gateway_position": gateway_pos,
        "layer_detection_rule": layer_rule,
        "source_script": source_script,
        "device_scenario": scenario,
        "network_plane": NET_PLANE if scenario != "od1600t" else "OceanDisk样本面",
    }
    pd.DataFrame([meta]).to_csv(run_dir / "run_meta.csv", index=False, encoding="utf-8-sig")
    det_path = run_dir / "scenario_detection.txt"
    det_path.write_text(
        f"layer={layer}\n"
        f"gateway_position={gateway_pos}\n"
        f"device_scenario={scenario}\n"
        f"{layer_rule}\n",
        encoding="utf-8",
    )
    (run_dir / "layer_detection.txt").write_text(det_path.read_text(encoding="utf-8"), encoding="utf-8")

    _skill_root = Path(__file__).resolve().parents[2]
    if str(_skill_root) not in sys.path:
        sys.path.insert(0, str(_skill_root))
    from _runtime_shared.network_access_plan import emit_for_plane, filter_assignable_address_rows

    plane_key = NET_PLANE
    emit_for_plane(
        run_dir,
        plane_key=plane_key,
        connect_path=path_connect,
        connect_sheet=sheet_connect,
        address_df=filter_assignable_address_rows(address_df),
        search_dirs=[out_dir],
    )
    return out_ip


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Offline A3 存储样本面 IP planning（自动识别 L2/L3 与设备场景，统一指令）"
    )
    p.add_argument(
        "--force-layer",
        default=None,
        choices=["L2", "L3", "l2", "l3"],
        help="可选：强制层级；默认按资源表 网关位置* 自动识别",
    )
    p.add_argument("--connect", dest="path_connect", default=None, type=Path)
    p.add_argument("--resource", default=None, type=Path)
    p.add_argument("--sheet-connect", default=SHEET_CONNECT_DEFAULT)
    p.add_argument("--sheet-res-index", default=SHEET_RES_DEFAULT, help=f"资源表 sheet（默认 {SHEET_RES_DEFAULT!r}）")
    p.add_argument("--out-dir", default=Path("output"), type=Path)
    p.add_argument("--skip-prompt-check", action="store_true")
    args = p.parse_args(argv)

    try:
        out = generate_cc_ybm_ip_address_xlsx(
            layer=args.force_layer,
            path_connect=args.path_connect,
            resource=args.resource,
            sheet_connect=args.sheet_connect,
            sheet_res_index=args.sheet_res_index,
            out_dir=args.out_dir,
            prompt_i2_file=None if args.skip_prompt_check else DEFAULT_PROMPT_I2,
            prompt_i3_file=None if args.skip_prompt_check else DEFAULT_PROMPT_I3,
        )
        meta_path = out.parent / "scenario_detection.txt"
        if meta_path.is_file():
            print(meta_path.read_text(encoding="utf-8").strip())
        print(f"OK: wrote 地址规划={out.parent / ('A3' + WEB_NETWORK_TYPE_NAME + '地址规划.xlsx')}")
        print(f"     IP地址规划={out.name}")
        seg = out.parent / f"A3{WEB_NETWORK_TYPE_NAME}网段规划.xlsx"
        if seg.is_file():
            print(f"     网段规划={seg.name}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
