#!/usr/bin/env python3
"""007 + 项目信息收集表 -> output/run_*/A3存储带外管理地址规划.xlsx。"""

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

from storage_dw_manage_rules import (
    NET_PLANE_RESOURCE,
    SHEET_DEFAULT,
    allocate_storage_dw_addresses,
    count_storage_ips_by_leaf,
    generate_l2_leaf_segments,
    generate_l3_leaf_segments,
    get_storage_data,
    read_network_resource,
    read_structured_007,
    storage_port_maps,
)

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


def generate_storage_dw_manage_xlsx(
    *,
    mode: str,
    path_007: Optional[Path] = None,
    resource: Optional[Path] = None,
    sheet: str = SHEET_DEFAULT,
    resource_sheet: str = RESOURCE_SHEET_DEFAULT,
    net_plane: str = NET_PLANE_RESOURCE,
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

    sheet_obj = _sheet_arg(sheet)
    resource_sheet_obj = _sheet_arg(resource_sheet)
    net_resource = read_network_resource(str(resource), resource_sheet_obj, net_plane)

    if mode == "auto":
        gateway_location = str(net_resource.gateway_location).strip().upper()
        if gateway_location == "SPINE":
            mode = "l2"
        elif gateway_location == "LEAF":
            mode = "l3"
        else:
            raise ValueError(
                f"{net_plane} 网关位置* 必须为 SPINE 或 LEAF，实际为 {net_resource.gateway_location!r}"
            )

    leaf_counts = count_storage_ips_by_leaf(str(path_007), sheet_obj)
    switch_to_storages = get_storage_data(str(path_007), sheet_obj)
    structured = read_structured_007(str(path_007), sheet_obj)
    port_count_dict, port_dict = storage_port_maps(structured)

    if mode == "l3":
        leaf_gateways = generate_l3_leaf_segments(leaf_counts, net_resource)
    else:
        leaf_gateways = generate_l2_leaf_segments(leaf_counts, net_resource)

    address_df = allocate_storage_dw_addresses(
        leaf_gateways,
        switch_to_storages,
        port_count_dict,
        port_dict,
        net_resource.ip_pool,
    )

    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)
    out_file = run_dir / "A3存储带外管理地址规划.xlsx"
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        address_df.to_excel(writer, sheet_name="存储带外管理地址", index=False)

    _skill_root = Path(__file__).resolve().parents[2]
    if str(_skill_root) not in sys.path:
        sys.path.insert(0, str(_skill_root))
    from _runtime_shared.network_access_plan import emit_for_plane, filter_assignable_address_rows

    emit_for_plane(
        run_dir,
        plane_key=net_plane,
        connect_path=path_007,
        connect_sheet=sheet_obj,
        address_df=filter_assignable_address_rows(address_df),
        search_dirs=[out_dir],
    )
    return out_file


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Offline A3 存储带外管理地址规划（L2/L3 自动分支）")
    parser.add_argument(
        "--mode",
        choices=["auto", "l2", "l3"],
        default="auto",
        help="auto=按资源表 网关位置* 自动选择；SPINE→L2，LEAF→L3",
    )
    parser.add_argument("--007", dest="path_007", default=None, type=Path, help="007 端口连线表")
    parser.add_argument("--resource", default=None, type=Path, help="项目信息收集表")
    parser.add_argument("--sheet", default=SHEET_DEFAULT, help=f"007 sheet，默认 {SHEET_DEFAULT!r}")
    parser.add_argument(
        "--resource-sheet",
        default=RESOURCE_SHEET_DEFAULT,
        help=f"资源表 sheet，默认 {RESOURCE_SHEET_DEFAULT!r}",
    )
    parser.add_argument(
        "--net-plane",
        default=NET_PLANE_RESOURCE,
        help=f"资源表网络平面行名，默认 {NET_PLANE_RESOURCE!r}",
    )
    parser.add_argument("--out-dir", default=Path("output"), type=Path, help="输出目录")
    args = parser.parse_args(argv)

    try:
        out_file = generate_storage_dw_manage_xlsx(
            mode=args.mode,
            path_007=args.path_007,
            resource=args.resource,
            sheet=args.sheet,
            resource_sheet=args.resource_sheet,
            net_plane=args.net_plane,
            out_dir=args.out_dir,
            restrict_to_cwd=True,
        )
        print(f"OK: wrote {out_file.name} under {out_file.parent}")
        print(f"     mode resolved: {args.mode} (auto reads 网关位置* from resource)")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
