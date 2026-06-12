#!/usr/bin/env python3
"""LEAF-SPINE 端口互联 + 资源表 → A3网络互连规划.xlsx（L2/L3 自动识别，确定性，无 LLM）。"""

from __future__ import annotations

import argparse
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

from ni_io import (  # noqa: E402
    INTERCONNECTION_INTENTS,
    LEAF_SPINE_CONFIG,
    collect_used_trunks_from_prior,
    detect_ni_layer,
    get_switch_data_l2,
    get_switch_data_l3,
    read_connect_raw,
    read_interconnect_pool_for_plane,
    read_vlan_for_plane,
    resolve_connect_sheet,
    resolve_intent,
)
from ni_l2_allocate import allocate_connection_l2, build_mlag_from_connect_raw  # noqa: E402
from ni_l3_allocate import allocate_ips_l3, validate_network_range  # noqa: E402

SHEET_CONNECT_DEFAULT = "auto"
SHEET_RES_DEFAULT_INDEX = 0
OUTPUT_BASENAME = "A3网络互连规划.xlsx"
OUTPUT_SHEET = "网络互连规划"


def _resolve_local_only(p: Path) -> Path:
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


def _require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = _resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception:
        raise SystemExit(
            f"ERROR: {label} must be under cwd.\n  resolved: {resolved}\n  cwd: {cwd}"
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


def _merge_plane(old_df: pd.DataFrame, new_df: pd.DataFrame, network_type: str) -> pd.DataFrame:
    if old_df.empty:
        return new_df
    if "网络平面" not in old_df.columns:
        return pd.concat([old_df, new_df], axis=0, ignore_index=True)
    kept = old_df[~old_df["网络平面"].astype(str).isin([network_type])]
    return pd.concat([kept, new_df], axis=0, ignore_index=True)


def run_pipeline(
    intent: str,
    connect: Path,
    resource: Path,
    out_dir: Path,
    sheet_connect: object,
    sheet_res_index: int,
    force_layer: Optional[str],
    prior_connect: Optional[Path],
    prior_access: Optional[Path],
) -> Path:
    third_intent, sheet_key, network_type = resolve_intent(intent)
    keyword = LEAF_SPINE_CONFIG[sheet_key]["keyword"]
    resolved_sheet = resolve_connect_sheet(connect, sheet_key, sheet_connect)
    raw = read_connect_raw(connect, resolved_sheet)

    if force_layer in ("L2", "L3"):
        layer = force_layer
        _, gateway_pos, layer_rule = detect_ni_layer(resource, network_type, sheet_res_index)
        if (layer == "L3" and gateway_pos != "LEAF") or (layer == "L2" and gateway_pos == "LEAF"):
            print(
                f"WARN: --force-layer {layer} 与资源表 网关位置*={gateway_pos!r} 不一致",
                flush=True,
            )
        layer_rule = f"forced {layer} (resource would be {gateway_pos})"
    else:
        layer, gateway_pos, layer_rule = detect_ni_layer(
            resource, network_type, sheet_res_index
        )

    run_root = out_dir  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_root.mkdir(parents=True, exist_ok=True)

    output_file = run_root / OUTPUT_BASENAME
    old_df = pd.DataFrame()
    if prior_connect and prior_connect.is_file():
        try:
            old_df = pd.read_excel(prior_connect, sheet_name=0, header=0)
            old_df = old_df[~old_df["网络平面"].astype(str).isin([network_type])]
        except Exception:
            old_df = pd.DataFrame()

    reserved = collect_used_trunks_from_prior(prior_connect) + collect_used_trunks_from_prior(
        prior_access
    )

    if layer == "L3":
        switch_df, link_count = get_switch_data_l3(raw, keyword)
        pool = read_interconnect_pool_for_plane(resource, network_type, sheet_res_index)
        validate_network_range(pool, link_count)
        result_df = allocate_ips_l3(switch_df, pool, network_type)
        source_script = "a3_ni_ip_address.py"
    else:
        switch_df, link_count = get_switch_data_l2(raw, keyword)
        vlan = read_vlan_for_plane(resource, network_type, sheet_res_index)
        mlag_df = build_mlag_from_connect_raw(raw)
        result_df = allocate_connection_l2(
            switch_df, vlan, network_type, mlag_df, old_df, reserved
        )
        source_script = "a3_l2_net_interconnection.py"

    merged = _merge_plane(old_df, result_df, network_type)
    merged.to_excel(output_file, sheet_name=OUTPUT_SHEET, index=False)

    (run_root / "layer_detection.txt").write_text(
        "\n".join(
            [
                f"layer={layer}",
                f"gateway_position={gateway_pos}",
                f"network_plane={network_type}",
                f"connect_sheet={resolved_sheet}",
                f"keyword={keyword}",
                f"link_count={link_count}",
                f"rule={layer_rule}",
                f"source_script={source_script}",
            ]
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "third_intent": third_intent,
                "layer": layer,
                "gateway_position": gateway_pos,
                "network_plane": network_type,
                "connect_sheet": str(resolved_sheet),
                "keyword": keyword,
                "link_count": link_count,
                "source_script": source_script,
                "layer_detection_rule": layer_rule,
            }
        ]
    ).to_csv(run_root / "run_meta.csv", index=False, encoding="utf-8-sig")

    print(f"OK: {output_file}", flush=True)
    print(f"     layer={layer} links={link_count} plane={network_type}", flush=True)
    return output_file


def main() -> None:
    parser = argparse.ArgumentParser(description="A3 LEAF-SPINE 网络互连规划（L2/L3 自动）")
    parser.add_argument(
        "--intent",
        default=None,
        help="三级互联规划指令，如「计算业务面互联规划」（不含 _L2/_L3 后缀）",
    )
    parser.add_argument("--connect", type=Path, help="端口连线表 xlsx")
    parser.add_argument("--resource", type=Path, help="项目信息收集表 xlsx")
    parser.add_argument("--sheet-connect", default=SHEET_CONNECT_DEFAULT)
    parser.add_argument("--sheet-res-index", type=int, default=SHEET_RES_DEFAULT_INDEX)
    parser.add_argument("--out-dir", type=Path, default=Path("output"))
    parser.add_argument("--force-layer", choices=["L2", "L3"], default=None)
    parser.add_argument(
        "--prior-connect",
        type=Path,
        default=None,
        help="已有 A3网络互连规划.xlsx（用于平面覆盖合并与 L2 trunk 占用）",
    )
    parser.add_argument(
        "--prior-access",
        type=Path,
        default=None,
        help="已有 A3网络设备接入规划.xlsx（用于 L2 trunk 占用，对齐 assigned_trunk_list）",
    )
    parser.add_argument(
        "--list-intents",
        action="store_true",
        help="列出支持的互联规划指令并退出",
    )
    args = parser.parse_args()

    if args.list_intents:
        for k in sorted(INTERCONNECTION_INTENTS):
            sheet = INTERCONNECTION_INTENTS[k]
            plane = LEAF_SPINE_CONFIG[sheet]["network_type"]
            print(f"{k}\t→ sheet={sheet}\tplane={plane}")
        return

    if not args.intent:
        parser.error("--intent is required (or use --list-intents)")

    connect = _require_under_cwd(
        args.connect or _autodetect_connect_in_cwd(), "connect"
    )
    resource = _require_under_cwd(
        args.resource or _autodetect_resource_in_cwd(), "resource"
    )
    out_dir = _resolve_local_only(args.out_dir)
    prior_c = (
        _require_under_cwd(args.prior_connect, "prior-connect")
        if args.prior_connect
        else None
    )
    prior_a = (
        _require_under_cwd(args.prior_access, "prior-access")
        if args.prior_access
        else None
    )

    run_pipeline(
        intent=args.intent,
        connect=connect,
        resource=resource,
        out_dir=out_dir,
        sheet_connect=args.sheet_connect,
        sheet_res_index=args.sheet_res_index,
        force_layer=args.force_layer,
        prior_connect=prior_c,
        prior_access=prior_a,
    )


if __name__ == "__main__":
    main()
