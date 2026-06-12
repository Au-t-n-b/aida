#!/usr/bin/env python3
"""存储管理面端口互联 + 资源表 → 存储管理面地址规划.xlsx（L2/L3 确定性，无 LLM）。"""

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

from cc_glm_io import (  # noqa: E402
    NET_PLANE,
    WEB_NETWORK_TYPE_NAME,
    detect_cc_glm_layer,
    fuzzy_column_value,
    get_node_info,
    get_switch_to_nodes,
    net_resource_markdown,
    read_resource_row,
    resolve_connect_sheet,
    resolve_leaf_spine_mapping,
    switch_demand_markdown,
)
from cc_glm_ip_allocate import allocate_storage_manage_ips  # noqa: E402
from cc_glm_segment_rules import (  # noqa: E402
    SEGMENT_COUNT_INSUFFICIENT,
    SwitchGateway,
    plan_switch_gateways_glm_i2,
    plan_switch_gateways_leaf_i3,
    split_ip_range,
    switch_gateways_to_dataframe,
    switch_gateways_to_markdown,
    transfer_gateways_to_spines,
)

SHEET_CONNECT_DEFAULT = "存储管理面端口互联"
SHEET_RES_DEFAULT = "网络资源需求表"
SHEET_RES_DEFAULT_INDEX = SHEET_RES_DEFAULT
FALLBACK_SHEET_HINT = "计算管理面端口互联"

DEFAULT_PROMPT_I2 = Path("a3_i2_network_segment_tools_prompt.py")
DEFAULT_PROMPT_I3 = Path("a3_i3_network_segment_tools_prompt.py")
PROMPT_I2_MARKERS = ("多个或所有交换机使用同一网段", "顺次累加节点数量")
PROMPT_I3_MARKERS = ("交接机不能共用网段", "网段个数不足", "vlan不足")

IP_POOL_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
)


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
    cwd_c = (Path.cwd() / path_or_name).resolve()
    if cwd_c.is_file():
        return cwd_c
    repo_c = (_SCRIPTS_DIR.parent / path_or_name.name).resolve()
    if repo_c.is_file():
        return repo_c
    repo_src = (
        _SCRIPTS_DIR.parent.parent.parent
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


def _network_segment_check(
    switch_list_md: str,
    net_resource_md: str,
    result_md: str,
    layer: str,
) -> None:
    """对齐 utils.network_segment_check 的关键硬校验。"""
    if SEGMENT_COUNT_INSUFFICIENT in result_md:
        sw_n = (
            len([ln for ln in switch_list_md.splitlines() if ln.startswith("|") and "---" not in ln])
            - 1
        )
        if layer == "L3":
            raise ValueError(
                f"网段个数不足：Leaf 交换机 {sw_n} 台，地址池可切分网段数不足（I3 一机一网段）。"
                f" 请扩大「地址池*」或减小「最小规划掩码」。"
            )
        raise ValueError(
            f"网段个数不足：Leaf 交换机 {sw_n} 台，I2 共用网段时单网段容量或地址池子网数不足"
            f"（常见原因：节点数×8 超过单网段可用 IP）。请扩大地址池/调整掩码。"
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
    from cc_glm_io import SHEET_COMPUTE_MANAGE_FALLBACK

    if SHEET_COMPUTE_MANAGE_FALLBACK in xf.sheet_names:
        return SHEET_COMPUTE_MANAGE_FALLBACK
    if isinstance(primary_sheet, str) and "存储" in primary_sheet:
        candidate = primary_sheet.replace("存储", "计算")
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
        header = "leaf交换机"
    elif layer.upper() == "L3":
        leaf_rows = plan_switch_gateways_leaf_i3(
            switch_list=switch_list,
            subnets=subnets,
            mask=mask,
            gateway_mode=gateway_mode,
            vlan_raw=vlan_raw,
        )
        header = "leaf交换机"
    else:
        raise ValueError("layer must be L2 or L3")

    md = switch_gateways_to_markdown(leaf_rows, header_switch=header)
    return leaf_rows, md


def generate_cc_glm_ip_address_xlsx(
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

    if not path_connect.is_file():
        raise ValueError(f"connect file not found: {path_connect}")
    if not resource.is_file():
        raise ValueError(f"resource file not found: {resource}")

    gateway_pos = ""
    layer_rule = ""
    if layer is None or str(layer).strip().lower() in ("", "auto"):
        layer, gateway_pos, layer_rule = detect_cc_glm_layer(resource, sheet_res_index)
    else:
        layer = str(layer).upper()
        if layer not in ("L2", "L3"):
            raise ValueError("layer must be L2, L3, or auto")
        _, gateway_pos, layer_rule = detect_cc_glm_layer(resource, sheet_res_index)
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

    original_df = get_node_info(path_connect, sheet_connect)
    equipment_info_df = original_df.drop_duplicates(subset=["节点名称"], keep="first")
    switch_to_nodes = get_switch_to_nodes(path_connect, sheet_connect)

    resource_row, ip_pool = read_resource_row(resource, sheet_res_index)
    net_md = net_resource_markdown(resource_row)
    sw_header = "交换机" if layer == "L2" else "leaf交换机"
    switch_md = switch_demand_markdown(switch_to_nodes, sw_header)

    leaf_gateways, segment_md = plan_leaf_gateways(
        layer=layer,
        switch_to_nodes=switch_to_nodes,
        resource_row=resource_row,
        ip_pool=ip_pool,
    )
    _network_segment_check(switch_md, net_md, segment_md, layer)

    spine_gateways: List[SwitchGateway] = []
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

    # 对齐 display_message("0-6", f"{web_network_type_name}网段规划", ...)
    # L2：展示 Spine 网段；L3：展示 Leaf 网段
    segment_display_rows = spine_gateways if layer == "L2" else leaf_gateways
    segment_switch_col = "spine交换机" if layer == "L2" else "leaf交换机"
    segment_df = switch_gateways_to_dataframe(segment_display_rows, segment_switch_col)
    out_segment_xlsx = run_dir / f"A3{WEB_NETWORK_TYPE_NAME}网段规划.xlsx"
    with pd.ExcelWriter(out_segment_xlsx, engine="openpyxl") as writer:
        segment_df.to_excel(
            writer,
            sheet_name=f"{WEB_NETWORK_TYPE_NAME}网段规划",
            index=False,
        )
        if layer == "L2":
            switch_gateways_to_dataframe(leaf_gateways, "leaf交换机").to_excel(
                writer,
                sheet_name="Leaf网段",
                index=False,
            )

    result_df, a800_df = allocate_storage_manage_ips(
        original_df=original_df,
        equipment_info_df=equipment_info_df,
        switch_network_segment_info=leaf_gateways,
        ip_pool=ip_pool,
        web_network_type_name=WEB_NETWORK_TYPE_NAME,
    )

    if result_df.empty and a800_df.empty:
        raise ValueError("没有生成任何分配结果")

    # 对齐 display_message("0-7/0-8", f"{web_network_type_name}IP地址规划", ...)
    out_ip_xlsx = run_dir / f"A3{WEB_NETWORK_TYPE_NAME}IP地址规划.xlsx"
    with pd.ExcelWriter(out_ip_xlsx, engine="openpyxl") as writer:
        if not result_df.empty:
            result_df.to_excel(
                writer,
                sheet_name=f"{WEB_NETWORK_TYPE_NAME}IP地址规划",
                index=False,
            )
        if not a800_df.empty:
            a800_sheet = (
                f"{WEB_NETWORK_TYPE_NAME}IP地址规划(A800)"
                if not result_df.empty
                else f"{WEB_NETWORK_TYPE_NAME}IP地址规划"
            )
            a800_df.to_excel(writer, sheet_name=a800_sheet, index=False)

    # 对齐 get_file_path(..., f"A3{web_network_type_name}地址规划.xlsx") / upload_to_edm
    out_addr_xlsx = run_dir / f"A3{WEB_NETWORK_TYPE_NAME}地址规划.xlsx"
    with pd.ExcelWriter(out_addr_xlsx, engine="openpyxl") as writer:
        if not result_df.empty:
            result_df.to_excel(
                writer, sheet_name=f"{WEB_NETWORK_TYPE_NAME}地址规划", index=False
            )
        if not a800_df.empty:
            sheet_a800 = (
                f"{WEB_NETWORK_TYPE_NAME}地址规划(A800)"
                if not result_df.empty
                else f"{WEB_NETWORK_TYPE_NAME}地址规划"
            )
            a800_df.to_excel(writer, sheet_name=sheet_a800, index=False)

    meta = {
        "layer": layer,
        "gateway_position": gateway_pos,
        "layer_detection_rule": layer_rule,
        "source_script": (
            "a3_cc_glm_ip_address.py"
            if layer == "L3"
            else "a3_l2_cc_glm_ip_address.py"
        ),
        "network_plane": NET_PLANE,
        "ip_pool": ip_pool,
        "switch_count": len(switch_to_nodes),
        "node_count": len(equipment_info_df),
    }
    pd.DataFrame([meta]).to_csv(run_dir / "run_meta.csv", index=False, encoding="utf-8-sig")
    (run_dir / "layer_detection.txt").write_text(
        f"layer={layer}\ngateway_position={gateway_pos}\n{layer_rule}\n",
        encoding="utf-8",
    )

    _skill_root = Path(__file__).resolve().parents[2]
    if str(_skill_root) not in sys.path:
        sys.path.insert(0, str(_skill_root))
    from _runtime_shared.network_access_plan import emit_for_plane, filter_assignable_address_rows

    addr_for_access = filter_assignable_address_rows(
        pd.concat([x for x in (result_df, a800_df) if not x.empty], ignore_index=True)
        if not result_df.empty or not a800_df.empty
        else pd.DataFrame()
    )
    emit_for_plane(
        run_dir,
        plane_key=NET_PLANE,
        connect_path=path_connect,
        connect_sheet=sheet_connect,
        address_df=addr_for_access,
        search_dirs=[out_dir],
    )

    return out_ip_xlsx


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Offline A3 存储管理面 IP planning（自动识别 L2/L3）"
    )
    p.add_argument(
        "--force-layer",
        default=None,
        choices=["L2", "L3", "l2", "l3"],
        help="可选：强制层级；默认按资源表 网关位置* 自动识别",
    )
    p.add_argument(
        "--connect",
        dest="path_connect",
        default=None,
        type=Path,
        help="存储管理面端口互联 Excel（默认 cwd 自动探测）",
    )
    p.add_argument("--resource", default=None, type=Path, help="项目信息收集表（默认 cwd 自动探测）")
    p.add_argument(
        "--sheet-connect",
        default=SHEET_CONNECT_DEFAULT,
        help=f"端口互联 sheet（默认 {SHEET_CONNECT_DEFAULT}）",
    )
    p.add_argument(
        "--sheet-res-index",
        default=SHEET_RES_DEFAULT,
        help=f"资源表 sheet（默认 {SHEET_RES_DEFAULT!r}）",
    )
    p.add_argument("--out-dir", default=Path("output"), type=Path)
    p.add_argument("--skip-prompt-check", action="store_true")
    args = p.parse_args(argv)

    try:
        out = generate_cc_glm_ip_address_xlsx(
            layer=args.force_layer,
            path_connect=args.path_connect,
            resource=args.resource,
            sheet_connect=args.sheet_connect,
            sheet_res_index=args.sheet_res_index,
            out_dir=args.out_dir,
            prompt_i2_file=None if args.skip_prompt_check else DEFAULT_PROMPT_I2,
            prompt_i3_file=None if args.skip_prompt_check else DEFAULT_PROMPT_I3,
        )
        meta_path = out.parent / "layer_detection.txt"
        if meta_path.is_file():
            print(meta_path.read_text(encoding="utf-8").strip())
        print(f"OK: wrote 网段规划={out.parent / ('A3' + WEB_NETWORK_TYPE_NAME + '网段规划.xlsx')}")
        print(f"     IP地址规划={out.name}")
        print(f"     地址规划={out.parent / ('A3' + WEB_NETWORK_TYPE_NAME + '地址规划.xlsx')}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
