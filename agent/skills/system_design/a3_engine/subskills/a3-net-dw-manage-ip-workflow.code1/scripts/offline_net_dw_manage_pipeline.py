#!/usr/bin/env python3
"""007 + 项目信息收集表 → output/run_*/A3网络带外管理地址规划.xlsx。

业务来源：
  - L2（网关位置*=SPINE）：a3_net_dw_manage_ip_address.py
  - L3（网关位置*=LEAF）：a3_l3_net_dw_manage_ip_address.py
"""

from __future__ import annotations

import argparse
import shutil
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

from net_dw_manage_rules import (
    NET_PLANE_RESOURCE,
    SHEET_DEFAULT,
    allocate_dw_manage_addresses,
    count_leaf_switches,
    generate_l2_leaf_segments,
    generate_l3_leaf_segments,
    get_leaf_spine_mapping,
    get_net_device_data,
    get_wldw_leaf_list,
    read_network_resource,
    read_structured_007,
    transfer_gateways_to_spines,
)

RESOURCE_SHEET_DEFAULT = "网络资源需求表"
# 历史测试目录，不再作为产出路径
_LEGACY_OUT_DIR_NAMES = frozenset({"output_retest"})


def _normalize_out_dir(out_dir: Path) -> Path:
    """统一写入 output/；拒绝将 output_retest 作为产出目录。"""
    parts = {p.lower() for p in out_dir.parts}
    if parts & _LEGACY_OUT_DIR_NAMES:
        print(
            "NOTE: 已弃用 output_retest，结果将写入 output/run_*",
            file=sys.stderr,
        )
        return Path("output")
    return out_dir


def _cleanup_legacy_out_dirs(cwd: Path) -> None:
    """移除 cwd 下遗留的 output_retest（若存在）。"""
    for name in _LEGACY_OUT_DIR_NAMES:
        legacy = (cwd / name).resolve()
        if legacy.is_dir():
            shutil.rmtree(legacy, ignore_errors=True)


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


def generate_net_dw_manage_xlsx(
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

    out_dir = _normalize_out_dir(out_dir)

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
                f"网络带外管理面 网关位置* 必须为 SPINE 或 LEAF，实际为 {net_resource.gateway_location!r}"
            )

    l3_mode = mode == "l3"
    filter_sp = l3_mode

    leaf_counts = count_leaf_switches(str(path_007), sheet_obj, filter_sp_devices=filter_sp)
    switch_to_devices = get_net_device_data(
        str(path_007), sheet_obj, filter_sp_devices=filter_sp
    )
    structured_007 = read_structured_007(str(path_007), sheet_obj)
    wldw_leaf_list = get_wldw_leaf_list(structured_007)

    if l3_mode:
        leaf_gateways = generate_l3_leaf_segments(leaf_counts, net_resource)
    else:
        leaf_gateways = generate_l2_leaf_segments(leaf_counts, net_resource)
        leaf_spine_map = get_leaf_spine_mapping(str(path_007), sheet_obj, leaf_gateways)
        transfer_gateways_to_spines(leaf_spine_map, leaf_gateways)

    address_df = allocate_dw_manage_addresses(
        leaf_gateways,
        switch_to_devices,
        wldw_leaf_list,
        net_resource.ip_pool,
        l3_mode=l3_mode,
    )

    ts = _timestamp()
    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)

    out_address = run_dir / "A3网络带外管理地址规划.xlsx"

    with pd.ExcelWriter(out_address, engine="openpyxl") as writer:
        address_df.to_excel(writer, sheet_name="网络带外管理地址", index=False)

    return out_address


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline A3 网络带外管理地址规划（L2/L3 自动分支）"
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "l2", "l3"],
        default="auto",
        help="auto=按资源表 网关位置* 自动选择；SPINE→L2，LEAF→L3",
    )
    parser.add_argument("--007", dest="path_007", default=None, type=Path, help="007 端口连线表")
    parser.add_argument("--resource", default=None, type=Path, help="项目信息收集表")
    parser.add_argument(
        "--sheet",
        default=SHEET_DEFAULT,
        help=f"007 端口互联 sheet，默认 {SHEET_DEFAULT!r}",
    )
    parser.add_argument(
        "--resource-sheet",
        default=RESOURCE_SHEET_DEFAULT,
        help=f"资源表 sheet，默认 {RESOURCE_SHEET_DEFAULT!r}",
    )
    parser.add_argument(
        "--net-plane",
        default=NET_PLANE_RESOURCE,
        help=f"资源表网络平面行匹配名，默认 {NET_PLANE_RESOURCE!r}",
    )
    parser.add_argument(
        "--out-dir",
        default=Path("output"),
        type=Path,
        help="输出目录（仅 output/，勿使用 output_retest）",
    )
    args = parser.parse_args(argv)
    args.out_dir = _normalize_out_dir(args.out_dir)

    try:
        out_file = generate_net_dw_manage_xlsx(
            mode=args.mode,
            path_007=args.path_007,
            resource=args.resource,
            sheet=args.sheet,
            resource_sheet=args.resource_sheet,
            net_plane=args.net_plane,
            out_dir=args.out_dir,
            restrict_to_cwd=True,
        )
        _cleanup_legacy_out_dirs(Path.cwd().resolve())
        print(f"OK: wrote {out_file.name} under {out_file.parent}")
        print(f"     mode resolved: {args.mode} (auto reads 网关位置* from resource)")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
