#!/usr/bin/env python3
"""007 + 网络资源需求表 -> output/run_*/A3 L2/L3 地址规划 Excel.

业务来源：
  - a3_l2_ip_address.py：二层接入，统一网段，网关展示到 Spine。
  - a3_ywm_ip_address.py：三层接入，按 Leaf 划分网段，服务器按 Leaf 网关分配地址。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from a3_l2_l3_ip_rules import (
    WEB_NETWORK_TYPE_CONFIG,
    allocate_l2_server_ips,
    allocate_l3_server_ips,
    build_access_plan,
    count_servers_by_leaf,
    generate_l3_leaf_segments,
    infer_bond4_devices,
    l2_spine_gateways,
    read_endpoint_pairs,
    read_network_resource,
    read_server_links,
    switch_gateways_to_dataframe,
)


SHEET_DEFAULT = "计算管理面端口互联"
RESOURCE_SHEET_DEFAULT = "网络资源需求表"


def _resolve_local_only(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()


def _require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = _resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception as exc:
        raise SystemExit(
            f"ERROR: {label} must be located under current working directory.\n"
            f"  resolved: {resolved}\n"
            f"  cwd:      {cwd}"
        ) from exc
    return resolved


def _list_excel_files_in_cwd() -> list[Path]:
    cwd = Path.cwd().resolve()
    files: list[Path] = []
    for ext in (".xlsx", ".xls", ".XLSX", ".XLS"):
        files.extend([p for p in cwd.rglob(f"*{ext}") if p.is_file()])
    uniq: list[Path] = []
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


def _autodetect_007() -> Path:
    for p in _list_excel_files_in_cwd():
        if ("007" in p.name) or ("端口连线" in p.name) or ("端口互联" in p.name):
            return p
    raise SystemExit("ERROR: cannot autodetect 007 excel in current working directory.")


def _autodetect_resource() -> Path:
    for p in _list_excel_files_in_cwd():
        if ("项目信息收集" in p.name) or ("信息收集表" in p.name) or ("资源" in p.name):
            return p
    raise SystemExit("ERROR: cannot autodetect resource excel in current working directory.")


def _sheet_arg(value: str) -> object:
    value = str(value).strip()
    return int(value) if value.isdigit() else value


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def generate_l2_l3_planning_xlsx(
    *,
    mode: str,
    path_007: Optional[Path] = None,
    resource: Optional[Path] = None,
    sheet: str = SHEET_DEFAULT,
    resource_sheet: str = str(RESOURCE_SHEET_DEFAULT),
    out_dir: Path = Path("output"),
    restrict_to_cwd: bool = True,
) -> Path:
    if mode not in {"auto", "l2", "l3"}:
        raise ValueError("--mode must be auto, l2 or l3")

    if path_007 is None:
        path_007 = _autodetect_007()
    if resource is None:
        resource = _autodetect_resource()

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

    web_network_type_name = WEB_NETWORK_TYPE_CONFIG.get(sheet, sheet)
    _skill_root = Path(__file__).resolve().parents[2]
    if str(_skill_root) not in sys.path:
        sys.path.insert(0, str(_skill_root))
    from _runtime_shared.sheet007_resolver import (
        allowed_connect_sheets_for_plane,
        resolve_connect_sheet,
    )

    sheet_obj = resolve_connect_sheet(
        path_007,
        sheet,
        allowed_sheets=allowed_connect_sheets_for_plane(web_network_type_name),
    )
    resource_sheet_obj = _sheet_arg(resource_sheet)

    server_links_all = read_server_links(str(path_007), sheet_obj)
    equipment_info_df = server_links_all.drop_duplicates(subset=["起始端设备"], keep="first")
    endpoint_pairs = read_endpoint_pairs(str(path_007), sheet_obj)
    net_resource = read_network_resource(str(resource), resource_sheet_obj, sheet)

    if mode == "auto":
        gateway_location = str(net_resource.gateway_location).strip().upper()
        if gateway_location == "SPINE":
            mode = "l2"
        elif gateway_location == "LEAF":
            mode = "l3"
        else:
            raise ValueError(
                f"计算管理面网关位置* 必须为 SPINE 或 LEAF，实际为 {net_resource.gateway_location!r}"
            )

    ts = _timestamp()
    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)

    if mode == "l2":
        address_df, network = allocate_l2_server_ips(equipment_info_df, net_resource, web_network_type_name)
        gateway_df = l2_spine_gateways(
            endpoint_pairs,
            equipment_info_df,
            network,
            address_df,
            net_resource,
            web_network_type_name,
        )
        access_df = build_access_plan(
            endpoint_pairs,
            address_df,
            web_network_type_name,
            f"{web_network_type_name}VLAN",
            pvid_from_vlan=True,
        )
        out_file = run_dir / f"A3{web_network_type_name}L2地址规划.xlsx"
        gateway_sheet = f"{web_network_type_name}网段规划"
    else:
        leaf_counts = count_servers_by_leaf(server_links_all)
        leaf_gateways = generate_l3_leaf_segments(leaf_counts, net_resource)
        gateway_df = switch_gateways_to_dataframe(leaf_gateways, first_col="leaf交换机")
        bond4_devices = infer_bond4_devices(server_links_all)
        address_df = allocate_l3_server_ips(
            equipment_info_df,
            leaf_gateways,
            net_resource,
            web_network_type_name,
            bond4_devices=bond4_devices,
        )
        access_df = build_access_plan(
            endpoint_pairs,
            address_df,
            web_network_type_name,
            f"{web_network_type_name}VLAN",
            pvid_from_vlan=False,
        )
        out_file = run_dir / f"A3{web_network_type_name}L3地址规划.xlsx"
        gateway_sheet = f"{web_network_type_name}网段规划"

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        gateway_df.to_excel(writer, sheet_name=gateway_sheet, index=False)
        address_df.to_excel(writer, sheet_name=f"{web_network_type_name}地址规划", index=False)

    _runtime_root = Path(__file__).resolve().parents[2]
    if str(_runtime_root) not in sys.path:
        sys.path.insert(0, str(_runtime_root))
    from _runtime_shared.network_access_plan import merge_access_plan_workbook, resolve_access_plan_workbook

    access_book = resolve_access_plan_workbook(run_dir, [out_dir])
    merge_access_plan_workbook(access_book, web_network_type_name, access_df)

    return out_file


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Offline A3 计算管理面 L2/L3 gateway IP planning pipeline")
    parser.add_argument(
        "--mode",
        choices=["auto", "l2", "l3"],
        default="auto",
        help="auto=按资源表 网关位置* 自动选择；l2=二层接入；l3=三层接入",
    )
    parser.add_argument("--007", dest="path_007", default=None, type=Path, help="007 端口连线表")
    parser.add_argument("--resource", default=None, type=Path, help="项目信息收集表/网络资源需求表")
    parser.add_argument("--sheet", default=SHEET_DEFAULT, help=f"端口互联 sheet 名，默认 {SHEET_DEFAULT!r}")
    parser.add_argument("--resource-sheet", default=str(RESOURCE_SHEET_DEFAULT), help="资源表 sheet，默认 0")
    parser.add_argument("--out-dir", default=Path("output"), type=Path, help="输出目录，默认 ./output")
    args = parser.parse_args(argv)

    try:
        out_file = generate_l2_l3_planning_xlsx(
            mode=args.mode,
            path_007=args.path_007,
            resource=args.resource,
            sheet=args.sheet,
            resource_sheet=args.resource_sheet,
            out_dir=args.out_dir,
            restrict_to_cwd=True,
        )
        print(f"OK: wrote {out_file.name} under {out_file.parent}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
