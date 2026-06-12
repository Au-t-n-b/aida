#!/usr/bin/env python3
"""端口互联 + 资源表 → 多平面 BGP AS 分配 + A3交换机ASN规划（确定性，无 LLM）。"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from switch_asn_allocate import allocate_all_planes  # noqa: E402
from switch_asn_export import export_asn_dataframe, export_asn_to_excel, markdown_limited  # noqa: E402
from switch_asn_io import (  # noqa: E402
    LOOPBACK_SHEET_ORDER,
    OUTPUT_ASN_XLSX,
    InMemoryGatewayStore,
    build_as_range_override_map,
    detect_plane_plans,
    detect_plane_sheets_for_export,
    format_missing_as_range_help,
    load_gateway_snapshot,
    seed_gateway_from_port_tables,
)

SHEET_RES_DEFAULT_INDEX = 0
PARTIAL_DATA_NOTICE = "仅展示部分数据，完整数据请下载文件查看"


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


def _find_latest_gateway_snapshot(out_dir: Path) -> Optional[Path]:
    root = out_dir if out_dir.is_dir() else out_dir.parent
    if not root.is_dir():
        return None
    candidates = sorted(
        root.rglob("gateway_snapshot.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in candidates:
        try:
            store = load_gateway_snapshot(p)
            if any(tpl[6] not in ("NA", "", None) for tpl in store.query_all()):
                return p
        except Exception:
            continue
    return None


def run_switch_asn_workflow(
    *,
    path_connect: Optional[Path] = None,
    resource: Optional[Path] = None,
    out_dir: Path = Path("output"),
    sheet_res_index: int = SHEET_RES_DEFAULT_INDEX,
    only_plane: Optional[str] = None,
    gateway_snapshot: Optional[Path] = None,
    export_only: bool = False,
    as_range_specs: Optional[List[str]] = None,
    deliverable_dir: Optional[Path] = None,
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

    gateway_store = InMemoryGatewayStore()
    if gateway_snapshot is not None:
        snap_path = _require_under_cwd(gateway_snapshot, "gateway-snapshot") if restrict_to_cwd else _resolve_local_only(
            gateway_snapshot
        )
        gateway_store.merge_snapshot(load_gateway_snapshot(snap_path))

    only_key = None
    if only_plane:
        only_key = only_plane.strip()
        if only_key not in LOOPBACK_SHEET_ORDER:
            raise ValueError(f"--only-plane 必须是 LOOPBACK_CONFIG 键之一，例如：存储管理面端口互联")

    as_range_overrides = build_as_range_override_map(as_range_specs or [])
    export_sheets, seed_skipped = detect_plane_sheets_for_export(
        path_connect, only_config_key=only_key
    )
    if export_sheets and not export_only:
        seeded = seed_gateway_from_port_tables(path_connect, export_sheets, gateway_store)
        print(f"INFO: 从端口表预置 {seeded} 条设备记录（ASN 可为空，对齐线上 gateway 汇总）")

    plans, skipped, override_notes = detect_plane_plans(
        path_connect,
        resource,
        sheet_res_index=sheet_res_index,
        only_config_key=only_key,
        as_range_overrides=as_range_overrides or None,
    )
    skipped = seed_skipped + skipped

    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)

    per_plane: dict = {}
    if not export_only:
        if not plans:
            if not gateway_store.query_all():
                snap_auto = _find_latest_gateway_snapshot(out_dir)
                if snap_auto is not None and gateway_snapshot is None:
                    gateway_store.merge_snapshot(load_gateway_snapshot(snap_auto))
                    print(
                        f"WARN: 无端口预置数据，已从历史快照导入 gateway: {snap_auto}",
                        file=sys.stderr,
                    )
            if not gateway_store.query_all():
                help_text = format_missing_as_range_help(
                    resource_path=resource,
                    skipped=skipped,
                    as_range_overrides=as_range_overrides or None,
                )
                (run_dir / "missing_ebgp_as_help.txt").write_text(help_text + "\n", encoding="utf-8")
                raise ValueError(help_text)
            if not plans:
                print(
                    "WARN: 资源表无 EBGP AS 区间，已仅导出端口表设备列表（ASN 为空，与线上未填 AS 时一致）。",
                    file=sys.stderr,
                )
        if plans:
            per_plane = allocate_all_planes(
                connect_path=path_connect,
                resource_path=resource,
                plans=plans,
                gateway_store=gateway_store,
                sheet_res_index=sheet_res_index,
            )
            detail_path = run_dir / "交换机ASN分配明细.xlsx"
            with pd.ExcelWriter(detail_path, engine="openpyxl") as writer:
                for plane_name, df in per_plane.items():
                    safe = plane_name[:31]
                    df.to_excel(writer, sheet_name=safe, index=False)

    asn_df = export_asn_dataframe(gateway_store)
    if asn_df.empty:
        raise ValueError(
            "交换机 ASN 规划结果为空。请确认端口表含 LOOPBACK 平面设备，"
            "或提供 --gateway-snapshot / 先完成各平面地址规划。"
        )

    asn_xlsx = run_dir / OUTPUT_ASN_XLSX
    export_asn_to_excel(asn_df, asn_xlsx)

    deliverable_targets: List[Path] = [asn_xlsx]
    if deliverable_dir is not None:
        ddir = _resolve_local_only(deliverable_dir)
        ddir.mkdir(parents=True, exist_ok=True)
        deliverable_copy = ddir / OUTPUT_ASN_XLSX
        shutil.copy2(asn_xlsx, deliverable_copy)
        deliverable_targets.append(deliverable_copy)

    md, exceeded = markdown_limited(asn_df)
    notice = PARTIAL_DATA_NOTICE if exceeded else ""
    preview_path = run_dir / "asn_preview.md"
    preview_path.write_text((notice + "\n\n" + md).strip() + "\n", encoding="utf-8")

    det_lines = [
        "mode=export_only" if export_only else "mode=allocate_and_export",
        f"deliverable={OUTPUT_ASN_XLSX}",
        f"export_sheets={len(export_sheets)}",
        f"planes_allocated={len(plans)}",
        "planes=" + ",".join(p.web_network_type_name for p in export_sheets),
        "allocated=" + ",".join(p.web_network_type_name for p in plans),
        "l2_l3=unified（线上网络设备ASN规划_L2/_L3 均调用同一入口，本 skill 不区分）",
    ]
    if override_notes:
        det_lines.append("as_range_override:")
        det_lines.extend(override_notes)
    if skipped:
        det_lines.append("skipped:")
        det_lines.extend(skipped)
    (run_dir / "plane_detection.txt").write_text("\n".join(det_lines) + "\n", encoding="utf-8")

    meta_rows = [
        {
            "deliverable_file": OUTPUT_ASN_XLSX,
            "export_sheet_planes": len(export_sheets),
            "planes_allocated": len(plans),
            "plane_names": "|".join(p.web_network_type_name for p in export_sheets),
            "allocated_planes": "|".join(p.web_network_type_name for p in plans),
            "asn_rows": len(asn_df),
            "source_allocate": "a3_switch_loopback_ip_address.py",
            "source_export": "a3_switch_asn.py",
            "instruction": "网络设备ASN规划",
        }
    ]
    pd.DataFrame(meta_rows).to_csv(run_dir / "run_meta.csv", index=False, encoding="utf-8-sig")

    snap_out = run_dir / "gateway_snapshot.csv"
    gw_rows = []
    for tpl in gateway_store.query_all():
        gw_rows.append(
            {
                "scope": tpl[3],
                "name": tpl[4],
                "network_segment": tpl[5],
                "ebgp_as": tpl[6],
                "vlan": tpl[7],
                "extend": tpl[8],
            }
        )
    pd.DataFrame(gw_rows).to_csv(snap_out, index=False, encoding="utf-8-sig")

    print(f"OK planes_alloc={len(plans)} asn_rows={len(asn_df)}")
    if notice:
        print(f"NOTICE: {notice}")
    for t in deliverable_targets:
        print(f"  deliverable: {t}")
    print(f"  preview: {preview_path}")
    if per_plane:
        print(f"  detail:  {run_dir / '交换机ASN分配明细.xlsx'}")
    print(f"  gateway: {snap_out}")
    return run_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="离线 网络设备ASN规划（多平面自动识别，确定性）")
    ap.add_argument("--connect", type=Path, default=None, help="端口互联表（007）")
    ap.add_argument("--resource", type=Path, default=None, help="项目信息收集表/资源表")
    ap.add_argument("--out-dir", type=Path, default=Path("output"))
    ap.add_argument("--sheet-res-index", type=int, default=SHEET_RES_DEFAULT_INDEX)
    ap.add_argument(
        "--only-plane",
        default=None,
        help="仅处理指定 LOOPBACK_CONFIG 键，如「存储管理面端口互联」",
    )
    ap.add_argument(
        "--gateway-snapshot",
        type=Path,
        default=None,
        help="导入已有网关 CSV 后再分配/导出（列 scope,name,ebgp_as,...）",
    )
    ap.add_argument(
        "--export-only",
        action="store_true",
        help="仅按 gateway-snapshot 导出 ASN（需 --gateway-snapshot）",
    )
    ap.add_argument(
        "--as-range",
        action="append",
        default=[],
        metavar="平面=65001-65099",
        help="覆盖资源表 EBGP AS规划；平面名可为 network_type（如 存储管理面）或 sheet 名",
    )
    ap.add_argument(
        "--deliverable-dir",
        type=Path,
        default=None,
        help="可选：额外复制 A3交换机ASN规划.xlsx 到此目录（默认仅写入 --out-dir/run_*）",
    )
    ap.add_argument("--no-cwd-restrict", action="store_true")
    args = ap.parse_args()

    if args.export_only and args.gateway_snapshot is None:
        raise SystemExit("ERROR: --export-only 需要同时提供 --gateway-snapshot")

    run_switch_asn_workflow(
        path_connect=args.connect,
        resource=args.resource,
        out_dir=args.out_dir,
        sheet_res_index=args.sheet_res_index,
        only_plane=args.only_plane,
        gateway_snapshot=args.gateway_snapshot,
        export_only=args.export_only,
        as_range_specs=args.as_range,
        deliverable_dir=args.deliverable_dir,
        restrict_to_cwd=not args.no_cwd_restrict,
    )


if __name__ == "__main__":
    main()
