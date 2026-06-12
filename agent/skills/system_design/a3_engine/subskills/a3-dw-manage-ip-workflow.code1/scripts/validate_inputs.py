#!/usr/bin/env python3
"""校验 007 + 资源表。退出码 0/1/2。"""
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


SHEET_007_DEFAULT = "计算带外管理面端口互联"
SHEET_RES_DEFAULT = "网络资源需求表"
SHEET_RES_DEFAULT_INDEX = 0
NET_PLANE = "计算带外管理面"
IP_POOL_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
)


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
    # de-dup by resolved path
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
        or ("项目信息" in f.name and "收集" in f.name)
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
        errors.append("007: need at least 2 columns (server, leaf)")
        return errors
    first_col = data.iloc[:, 0]
    last_col = data.iloc[:, -1]
    empty_first = first_col.isna() | (first_col.astype(str).str.strip() == "")
    empty_last = last_col.isna() | (last_col.astype(str).str.strip() == "")
    if (empty_first | empty_last).all():
        errors.append("007: first/last columns appear empty for all rows")
    elif (empty_first | empty_last).any():
        bad = int((empty_first | empty_last).sum())
        errors.append(f"007: {bad} row(s) have empty first or last column")
    print(f"007: OK — sheet={sheet_name!r}, header_row_idx={h}, data_rows={len(data)}")
    return errors


def validate_resource(path: Path, sheet_name: Optional[str], sheet_index: Optional[int]) -> List[str]:
    errors: List[str] = []
    try:
        if sheet_index is not None:
            df = pd.read_excel(path, sheet_name=sheet_index, header=0)
            sheet_label = f"index={sheet_index}"
        else:
            df = pd.read_excel(path, sheet_name=sheet_name, header=0)
            sheet_label = repr(sheet_name)
    except Exception as e:
        return [f"resource: cannot read sheet {sheet_name!r}: {e}"]
    if "网络平面" not in df.columns:
        errors.append(
            f"resource: column '网络平面' missing. Columns: {list(df.columns)}"
        )
        return errors
    row = df[df["网络平面"].astype(str) == NET_PLANE]
    if row.empty:
        errors.append(
            f"resource: no row with 网络平面 == {NET_PLANE!r}"
        )
        return errors
    r = row.iloc[0]
    pool_col = "地址池*" if "地址池*" in df.columns else None
    if not pool_col:
        errors.append("resource: column '地址池*' missing")
    else:
        pool = str(r[pool_col]).strip() if pd.notna(r[pool_col]) else ""
        if not IP_POOL_PATTERN.match(pool):
            errors.append(
                f"resource: 地址池* must match A.B.C.D - E.F.G.H, got: {pool!r}"
            )
    mask_cols = [c for c in df.columns if "最小规划掩码" in str(c)]
    if not mask_cols:
        errors.append("resource: no column matching '最小规划掩码'")
    else:
        v = r[mask_cols[0]]
        if pd.isna(v):
            errors.append("resource: 最小规划掩码 is empty")
        else:
            try:
                int(v)
            except (TypeError, ValueError):
                errors.append(f"resource: 最小规划掩码 must be integer, got: {v!r}")
    if "网关地址*" not in df.columns:
        errors.append("resource: column '网关地址*' missing")
    if "VLAN*" not in df.columns:
        errors.append("resource: column 'VLAN*' missing")
    if errors:
        return errors
    print(
        f"resource: OK — sheet={sheet_label}, row 网络平面={NET_PLANE!r}, "
        f"地址池*={r.get('地址池*', 'N/A')}, VLAN*={r.get('VLAN*', 'N/A')}"
    )
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Validate A3 DW manage IP inputs")
    p.add_argument("--007", dest="path_007", default=None, type=Path, help="007 port-connectivity Excel (.xlsx). Default: autodetect under cwd.")
    p.add_argument("--resource", default=None, type=Path, help="Project info collection Excel (.xlsx). Default: autodetect under cwd.")
    p.add_argument("--sheet007", default=SHEET_007_DEFAULT, help=f"007 sheet (default: {SHEET_007_DEFAULT})")
    p.add_argument(
        "--sheet-res",
        default=None,
        help="resource sheet name (optional; default: use --sheet-res-index)",
    )
    p.add_argument(
        "--sheet-res-index",
        type=int,
        default=SHEET_RES_DEFAULT_INDEX,
        help=f"resource sheet index (default: {SHEET_RES_DEFAULT_INDEX})",
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
            "ERROR: 007 file not found in current directory scope.\n"
            f"  provided: {args.path_007}\n"
            f"  cwd:      {Path.cwd()}\n"
            "Hint: place the Excel file in the current directory or pass an absolute path.",
            file=sys.stderr,
        )
        return 2
    if not args.resource.is_file():
        print(
            "ERROR: resource file not found in current directory scope.\n"
            f"  provided: {args.resource}\n"
            f"  cwd:      {Path.cwd()}\n"
            "Hint: place the Excel file in the current directory or pass an absolute path.",
            file=sys.stderr,
        )
        return 2
    all_err: List[str] = []
    all_err.extend(validate_007(args.path_007, args.sheet007))
    if args.sheet_res is None:
        all_err.extend(
            validate_resource(args.resource, None, args.sheet_res_index)
        )
    else:
        all_err.extend(validate_resource(args.resource, args.sheet_res, None))
    if all_err:
        print("Validation failed:", file=sys.stderr)
        for e in all_err:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
