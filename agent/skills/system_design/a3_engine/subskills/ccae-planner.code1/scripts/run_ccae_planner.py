#!/usr/bin/env python3
"""离线 CCAE 部署规划：007 + 资源表 [+ MLAG 列表] -> A3CCAE部署规划.xlsx。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ccae_planner import PlannerInputs, run_planner, write_ccae_excel
from ccae_topology_parser import DEFAULT_SHEET

DEFAULT_OUT = "A3CCAE部署规划.xlsx"


def _resolve_local(p: Path) -> Path:
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


def _require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = _resolve_local(file_path)
    try:
        resolved.relative_to(cwd)
    except ValueError:
        raise SystemExit(
            f"ERROR: {label} must be under current working directory.\n"
            f"  path: {resolved}\n  cwd:  {cwd}"
        )
    return resolved


def _list_excel_in_cwd() -> List[Path]:
    cwd = Path.cwd().resolve()
    files: List[Path] = []
    for ext in (".xlsx", ".xls"):
        files.extend(cwd.rglob(f"*{ext}"))
    uniq: List[Path] = []
    seen = set()
    for p in files:
        if p.name.startswith("~$"):
            continue
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _pick(candidates: Sequence[Path], label: str) -> Path:
    if not candidates:
        raise SystemExit(f"ERROR: cannot auto-detect {label} in cwd")
    if len(candidates) > 1:
        names = "\n".join(f"  - {c.name}" for c in candidates[:10])
        raise SystemExit(f"ERROR: multiple {label} candidates:\n{names}")
    return candidates[0]


def _auto_topology() -> Path:
    cands = [
        p
        for p in _list_excel_in_cwd()
        if "007" in p.name or "端口连线" in p.name or "端口互联" in p.name
    ]
    return _pick(cands, "007 topology")


def _auto_resource() -> Path:
    cands = [
        p
        for p in _list_excel_in_cwd()
        if "项目信息收集" in p.name or "资源" in p.name
    ]
    return _pick(cands, "resource table")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Offline CCAE deployment IP planner")
    parser.add_argument("--topology", type=Path, help="007 端口连线/互联表 xlsx")
    parser.add_argument("--resource", type=Path, help="项目信息收集表 / 网络资源表 xlsx")
    parser.add_argument("--mlag-list", type=Path, help="MLAG 对端设备名列表（每行一个，可选）")
    parser.add_argument("--sheet", default=DEFAULT_SHEET, help="007 sheet 名")
    parser.add_argument("--resource-sheet-index", type=int, default=0)
    parser.add_argument("--out", type=Path, default=Path(DEFAULT_OUT))
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="若指定，则写入 out-dir/run_YYYYMMDD_HHMMSS/<out name>",
    )
    parser.add_argument("--print-markdown", action="store_true")
    args = parser.parse_args(argv)

    topo = _require_under_cwd(args.topology or _auto_topology(), "topology")
    resource = _require_under_cwd(args.resource or _auto_resource(), "resource")
    mlag: Optional[Path] = None
    if args.mlag_list:
        mlag = _require_under_cwd(args.mlag_list, "mlag-list")

    out_path = args.out
    if args.out_dir:
        run_dir = _resolve_local(args.out_dir)  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
        run_dir.mkdir(parents=True, exist_ok=True)
        out_path = run_dir / out_path.name

    inputs = PlannerInputs(
        topology_path=str(topo),
        resource_path=str(resource),
        sheet_topology=args.sheet,
        resource_sheet_index=args.resource_sheet_index,
        mlag_list_path=str(mlag) if mlag else None,
    )

    try:
        result = run_planner(inputs)
        written = write_ccae_excel(result, str(_resolve_local(out_path)))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"OK: wrote {written}")
    print(f"  nodes: {len(result.module1)} rows, VIPs: {len(result.module2)} rows")
    print(f"  switch_mlag_flag: {result.switch_mlag_flag}")

    if args.print_markdown:
        print("\n### 模块一\n")
        print(result.module1.to_markdown(index=False))
        if not result.module2.empty:
            print("\n### 模块二\n")
            print(result.module2.to_markdown(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
