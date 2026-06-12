#!/usr/bin/env python3
"""校验 007 + 网络资源需求表（L1/L2 两行：地址池* + EBGP AS 规划）。退出码 0/1/2。"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    sys.exit(2)


SHEET_007_DEFAULT = "超平面端口互联"
SHEET_RES_DEFAULT_NAME = "网络资源需求表"
NET_PLANE_L1_DEFAULT = "L1交换机LoopBack地址"
NET_PLANE_L2_DEFAULT = "L2交换机LoopBack地址"

IP_POOL_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*(?:-\s*\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})?$"
)
AS_RANGE_PATTERN = re.compile(r"^\s*\d+\s*-\s*\d+\s*$")
AS_SINGLE_PATTERN = re.compile(r"^\s*\d+\s*$")
SP_DEVICE_PATTERN = re.compile(r"(?i)-SP\d+-")


def resolve_local_only(p: Path) -> Path:
    if p.is_absolute():
        return p
    return (Path.cwd() / p).resolve()


def require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception:
        raise SystemExit(
            f"ERROR: {label} must be located under current working directory.\n"
            f"  resolved: {resolved}\n"
            f"  cwd:      {cwd}"
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


def _pick_single(candidates: Sequence[Path], label: str) -> Path:
    if not candidates:
        raise SystemExit(
            f"ERROR: cannot auto-detect {label} in current directory.\n"
            f"  cwd: {Path.cwd().resolve()}\n"
            "Hint: put the Excel file in cwd or pass --007/--resource explicitly."
        )
    if len(candidates) > 1:
        formatted = "\n".join([f"  - {c.name}" for c in candidates])
        raise SystemExit(
            f"ERROR: multiple candidates found for {label} in current directory.\n"
            f"{formatted}\n"
            f"Hint: pass --{label} with an exact filename."
        )
    return candidates[0]


def autodetect_007_in_cwd() -> Path:
    files = _list_excel_files_in_cwd()
    cand = [
        f
        for f in files
        if ("007" in f.name)
        or ("端口连线" in f.name)
        or ("端口互联" in f.name)
    ]
    return _pick_single(cand, "007")


def autodetect_resource_in_cwd() -> Path:
    files = _list_excel_files_in_cwd()
    cand = [
        f
        for f in files
        if ("项目信息收集" in f.name)
        or ("信息收集表" in f.name)
        or ("资源" in f.name)
    ]
    return _pick_single(cand, "resource")


def find_header_row_007(df_raw: pd.DataFrame) -> Optional[int]:
    for idx, row in df_raw.iterrows():
        if row.astype(str).str.contains("设备命名", case=False, na=False).any():
            return int(idx)
    return None


def validate_007(path: Path, sheet_name: str) -> List[str]:
    errors: List[str] = []
    try:
        xls = pd.ExcelFile(path)
    except Exception as e:
        return [f"007: cannot open file: {e}"]
    sheet_spec = str(sheet_name).strip()
    if sheet_spec.isdigit():
        sheet_idx = int(sheet_spec)
        if sheet_idx < 0 or sheet_idx >= len(xls.sheet_names):
            errors.append(
                f"007: sheet index {sheet_idx} out of range. Available: {xls.sheet_names}"
            )
            return errors
        sheet: object = sheet_idx
        sheet_label = f"index={sheet_idx} name={xls.sheet_names[sheet_idx]!r}"
    else:
        if sheet_spec not in xls.sheet_names:
            errors.append(
                f"007: sheet '{sheet_spec}' not found. Available: {xls.sheet_names}"
            )
            return errors
        sheet = sheet_spec
        sheet_label = f"name={sheet_spec!r}"

    df_raw = pd.read_excel(path, sheet_name=sheet, header=None)
    h = find_header_row_007(df_raw)
    if h is None:
        errors.append(f"007: no row containing '设备命名' in target sheet ({sheet_label})")
        return errors
    data = df_raw.iloc[h + 1 :]
    if data.empty:
        errors.append("007: no data rows after header row")
        return errors
    ncols = data.shape[1]
    if ncols < 2:
        errors.append("007: need at least 2 columns (L1, L2)")
        return errors

    first_col = data.iloc[:, 0].astype(str).str.strip()
    last_col = data.iloc[:, -1].astype(str).str.strip()
    l1_with_sp = [v for v in first_col.tolist() if v and SP_DEVICE_PATTERN.search(v)]
    l2_with_sp = [v for v in last_col.tolist() if v and SP_DEVICE_PATTERN.search(v)]
    if not l1_with_sp and not l2_with_sp:
        errors.append("007: no -SP<n>- pattern found in either first or last column")

    print(
        f"007: OK — sheet={sheet_name!r}, header_row_idx={h}, data_rows={len(data)}, "
        f"L1_with_sp={len(l1_with_sp)}, L2_with_sp={len(l2_with_sp)}"
    )
    return errors


def _read_resource_df(path: Path, sheet_name: Optional[str]) -> pd.DataFrame:
    sn = sheet_name
    if isinstance(sn, str) and sn.strip().isdigit():
        return pd.read_excel(path, sheet_name=int(sn.strip()), header=0)
    return pd.read_excel(path, sheet_name=sn, header=0)


def validate_resource_plane(
    df: pd.DataFrame,
    plane_name: str,
    label: str,
    expected_as_kind: str,
) -> List[str]:
    """expected_as_kind: 'range' (L1) 或 'single' (L2)。"""
    errors: List[str] = []
    if "网络平面" not in df.columns:
        errors.append(
            f"resource[{label}]: column '网络平面' missing. Columns: {list(df.columns)}"
        )
        return errors
    row = df[df["网络平面"].astype(str) == plane_name]
    if row.empty:
        errors.append(f"resource[{label}]: no row with 网络平面 == {plane_name!r}")
        return errors
    r = row.iloc[0]
    pool_col = "地址池*" if "地址池*" in df.columns else None
    if not pool_col:
        # 模糊匹配
        cand = [c for c in df.columns if "地址池" in str(c)]
        if not cand:
            errors.append(f"resource[{label}]: column '地址池*' missing")
            return errors
        pool_col = cand[0]
    pool = str(r[pool_col]).strip() if pd.notna(r[pool_col]) else ""
    if not IP_POOL_PATTERN.match(pool):
        errors.append(
            f"resource[{label}]: 地址池* must be 'A.B.C.D' or 'A.B.C.D-E.F.G.H', got: {pool!r}"
        )

    as_cols = [c for c in df.columns if "EBGP AS" in str(c) or "AS规划" in str(c)]
    if not as_cols:
        errors.append(f"resource[{label}]: no column matching 'EBGP AS 规划' / 'AS规划'")
        return errors
    as_val = r[as_cols[0]]
    if pd.isna(as_val) or str(as_val).strip() == "":
        errors.append(f"resource[{label}]: AS 规划为空")
        return errors
    as_s = str(as_val).strip()
    if expected_as_kind == "range":
        if not AS_RANGE_PATTERN.match(as_s):
            errors.append(
                f"resource[{label}]: L1 EBGP AS 规划须为 'start-end'，实际: {as_s!r}"
            )
    elif expected_as_kind == "single":
        if not AS_SINGLE_PATTERN.match(as_s):
            errors.append(
                f"resource[{label}]: L2 EBGP AS 规划须为单个整数，实际: {as_s!r}"
            )

    if not errors:
        print(
            f"resource[{label}]: OK — 网络平面={plane_name!r}, "
            f"地址池*={pool!r}, AS={as_s!r}"
        )
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Validate A3 CPM/LQ (超平面) inputs")
    p.add_argument(
        "--007",
        dest="path_007",
        default=None,
        type=Path,
        help="007 port-connectivity Excel (.xlsx). Default: autodetect under cwd.",
    )
    p.add_argument(
        "--resource",
        default=None,
        type=Path,
        help="Project info collection Excel (.xlsx). Default: autodetect under cwd.",
    )
    p.add_argument("--sheet007", default=SHEET_007_DEFAULT, help=f"007 sheet (default: {SHEET_007_DEFAULT})")
    p.add_argument(
        "--sheet-resource",
        default=SHEET_RES_DEFAULT_NAME,
        help=f"resource sheet name (default: {SHEET_RES_DEFAULT_NAME!r}; pure digit => sheet index)",
    )
    p.add_argument(
        "--net-plane-l1",
        default=NET_PLANE_L1_DEFAULT,
        help=f"L1 network plane name (default: {NET_PLANE_L1_DEFAULT!r})",
    )
    p.add_argument(
        "--net-plane-l2",
        default=NET_PLANE_L2_DEFAULT,
        help=f"L2 network plane name (default: {NET_PLANE_L2_DEFAULT!r})",
    )
    args = p.parse_args()

    try:
        print(f"cwd: {Path.cwd().resolve()}")
        if args.path_007 is None:
            args.path_007 = autodetect_007_in_cwd()
        args.path_007 = require_under_cwd(args.path_007, "007")

        if args.resource is None:
            args.resource = autodetect_resource_in_cwd()
        args.resource = require_under_cwd(args.resource, "resource")

        print(f"input.007: {args.path_007.name}")
        print(f"input.resource: {args.resource.name}")
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2

    if not args.path_007.is_file():
        print(
            f"ERROR: 007 file not found: {args.path_007}",
            file=sys.stderr,
        )
        return 2
    if not args.resource.is_file():
        print(
            f"ERROR: resource file not found: {args.resource}",
            file=sys.stderr,
        )
        return 2

    all_err: List[str] = []
    all_err.extend(validate_007(args.path_007, args.sheet007))

    try:
        df_res = _read_resource_df(args.resource, args.sheet_resource)
    except Exception as e:
        all_err.append(f"resource: cannot read sheet {args.sheet_resource!r}: {e}")
        df_res = None

    if df_res is not None:
        all_err.extend(validate_resource_plane(df_res, args.net_plane_l1, "L1", "range"))
        all_err.extend(validate_resource_plane(df_res, args.net_plane_l2, "L2", "single"))

    if all_err:
        print("Validation failed:", file=sys.stderr)
        for e in all_err:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
