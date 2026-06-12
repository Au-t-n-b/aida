#!/usr/bin/env python3
"""A3 LLD offline conductor: plan | collect | integrate (no EDM/DB/LLM)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

try:
    import pandas as pd
except ImportError:
    print("ERROR: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2) from None

from lld_path_utils import (
    DEFAULT_OUT_DIR,
    autodetect_resource,
    autodetect_topology,
    default_lld_output_path,
    find_run_dir,
    new_run_dir,
    require_under_cwd,
    resolve_local,
    sanitize_project_name,
)
from lld_staging import collect_step_outputs, save_manifest, scan_latest_by_plane, update_manifest_step
from lld_workflow import build_workflow_plan, get_step_def, save_workflow_plan
from offline_integrate_lld import integrate_lld


def _resolve_inputs(args, cwd: Path) -> tuple[Path, Path]:
    topo = (
        require_under_cwd(args.topology, cwd, "topology")
        if args.topology
        else autodetect_topology(cwd)
    )
    res = (
        require_under_cwd(args.resource, cwd, "resource")
        if args.resource
        else autodetect_resource(cwd)
    )
    if not topo or not topo.is_file():
        raise SystemExit("ERROR: topology not found; pass --topology")
    if not res or not res.is_file():
        raise SystemExit("ERROR: resource not found; pass --resource")
    return resolve_local(topo, cwd), resolve_local(res, cwd)


def _read_sheet_names(topology: Path) -> list[str]:
    return list(pd.ExcelFile(topology).sheet_names)


def _simulation_paths(simulation_dir: Optional[Path], topology: Path) -> dict:
    keys = {
        "设备信息概览": ["001", "设备信息"],
        "设备位置信息": ["004", "设备位置"],
        "端口互联关系": ["007", "端口连线", "端口互联"],
    }
    result = {}
    if simulation_dir and simulation_dir.is_dir():
        for label, tokens in keys.items():
            for p in simulation_dir.rglob("*.xlsx"):
                if any(t in p.name for t in tokens):
                    result[label] = p
                    break
    if "端口互联关系" not in result:
        result["端口互联关系"] = topology
    return result


def _resolve_scan_dirs(args, cwd: Path, out_dir: Path) -> List[Path]:
    dirs: List[Path] = []
    if args.scan_dir:
        dirs.append(require_under_cwd(args.scan_dir, cwd, "scan-dir"))
    elif args.scan_dirs:
        for raw in args.scan_dirs.split(","):
            raw = raw.strip()
            if raw:
                dirs.append(require_under_cwd(Path(raw), cwd, "scan-dir"))
    else:
        dirs.append(out_dir)
    return dirs


def cmd_plan(args) -> int:
    cwd = Path.cwd().resolve()
    topology, resource = _resolve_inputs(args, cwd)
    out_dir = require_under_cwd(args.out_dir or DEFAULT_OUT_DIR, cwd, "out-dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = new_run_dir(out_dir, args.run_id)
    sheet_names = _read_sheet_names(topology)
    plan = build_workflow_plan(
        topology=topology,
        resource=resource,
        run_dir=run_dir,
        out_dir=out_dir,
        user_id=args.user_id,
        project_id=args.project_id,
        project_name=sanitize_project_name(args.project_name),
        sheet_names=sheet_names,
    )
    save_workflow_plan(plan, run_dir)
    manifest = {"run_id": plan["run_id"], "steps": {s["id"]: {"status": s["status"]} for s in plan["steps"]}}
    save_manifest(run_dir / "manifest.json", manifest)
    print(f"OK: plan metadata under {run_dir}")
    print(f"  - workflow_plan.json / steps.md")
    print(f"  - 最终 LLD 将写入: {out_dir}/{{项目名}}-LLD设计-*.xlsx")
    eligible = sum(1 for s in plan["steps"] if s["eligible"])
    pending_handler = sum(1 for s in plan["steps"] if s["status"] == "pending_no_handler")
    print(f"  eligible steps: {eligible}, pending_no_handler: {pending_handler}")
    return 0


def cmd_collect(args) -> int:
    """Optional: copy child skill output into --scan-dir (no step_out / staging)."""
    cwd = Path.cwd().resolve()
    if not args.source_dir:
        raise SystemExit("ERROR: collect requires --source-dir (子 skill 产出目录)")
    out_dir = require_under_cwd(args.out_dir or DEFAULT_OUT_DIR, cwd, "out-dir")
    target_dir = require_under_cwd(args.scan_dir or out_dir, cwd, "scan-dir")
    target_dir.mkdir(parents=True, exist_ok=True)

    step_def = get_step_def(args.step) if args.step else None
    ctx = {
        "user_id": args.user_id,
        "project_id": args.project_id,
        "project_name": sanitize_project_name(args.project_name),
    }
    outputs = []
    if step_def:
        outputs = step_def.outputs
        if not outputs and step_def.expected_output_pattern:
            outputs = [{"pattern": step_def.expected_output_pattern, "source_glob": "*"}]
    if not outputs:
        outputs = [{"pattern": "*A3*.xlsx", "source_glob": "*.xlsx"}]

    source_dir = require_under_cwd(args.source_dir, cwd, "source-dir")
    result = collect_step_outputs(target_dir, source_dir, outputs, ctx, strict=args.strict)

    if args.run_id:
        run_dir = find_run_dir(out_dir, args.run_id)
        update_manifest_step(
            run_dir / "manifest.json",
            args.step or "?",
            "done" if not result.missing else "partial",
            {"copied": result.copied, "missing": result.missing},
        )

    print(f"OK: collect -> {target_dir}")
    for p in result.copied:
        print(f"  - {p}")
    if result.missing:
        print(f"WARN: missing {result.missing}")
        return 1 if args.strict else 0
    return 0


def cmd_integrate(args) -> int:
    cwd = Path.cwd().resolve()
    out_dir = require_under_cwd(args.out_dir or DEFAULT_OUT_DIR, cwd, "out-dir")
    out_dir.mkdir(parents=True, exist_ok=True)

    scan_dirs = _resolve_scan_dirs(args, cwd, out_dir)
    resource = None
    topology = None
    project_name = sanitize_project_name(args.project_name)

    if args.run_id:
        run_dir = find_run_dir(out_dir, args.run_id)
        plan_path = run_dir / "workflow_plan.json"
        if plan_path.is_file():
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            resource = Path(plan["resource"]) if plan.get("resource") else None
            topology = Path(plan["topology"]) if plan.get("topology") else None
            project_name = sanitize_project_name(plan.get("project_name", project_name))

    if args.resource:
        resource = require_under_cwd(args.resource, cwd, "resource")
    if args.topology:
        topology = require_under_cwd(args.topology, cwd, "topology")

    templates_dir = Path(args.templates_dir).resolve() if args.templates_dir else None
    simulation_dir = Path(args.simulation_dir).resolve() if args.simulation_dir else None

    output_path = (
        require_under_cwd(args.output, cwd, "output")
        if args.output
        else default_lld_output_path(out_dir, project_name)
    )

    latest = scan_latest_by_plane(scan_dirs)
    print(f"integrate: {len(latest)} plane(s)")
    for k, p in sorted(latest.items()):
        print(f"  - {k}: {p.name}")

    integrate_lld(
        project_name=project_name,
        output_path=output_path,
        scan_dirs=scan_dirs,
        templates_dir=templates_dir,
        simulation_files=_simulation_paths(simulation_dir, topology) if topology or simulation_dir else None,
        resource_path=resource,
    )

    if args.run_id:
        run_dir = find_run_dir(out_dir, args.run_id)
        update_manifest_step(run_dir / "manifest.json", "23", "done", {"output": str(output_path)})

    print(f"OK: final LLD -> {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="A3 LLD offline conductor (plan | collect | integrate)")
    p.add_argument("--mode", choices=["plan", "collect", "integrate"], default="plan")
    p.add_argument("--topology", type=Path, help="007 端口连线表")
    p.add_argument("--resource", type=Path, help="项目信息收集表")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="最终 LLD 输出目录（默认 output/）")
    p.add_argument("--run-id", help="plan 元数据 run id（integrate 可选）")
    p.add_argument("--user-id", default="offline_user")
    p.add_argument("--project-id", default="offline_project")
    p.add_argument("--project-name", default="LLD项目")
    p.add_argument("--step", help="collect 可选：step id")
    p.add_argument("--source-dir", type=Path, help="collect：子 skill 产出目录")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--scan-dir", type=Path, help="integrate/collect：扫描/写入 A3*.xlsx 的目录")
    p.add_argument(
        "--scan-dirs",
        help="integrate：多个扫描目录，逗号分隔（默认仅 --out-dir）",
    )
    p.add_argument("--templates-dir", type=Path, help="LLD 模板目录")
    p.add_argument("--simulation-dir", type=Path, help="001-007 仿真文件目录")
    p.add_argument("--output", type=Path, help="integrate 输出 xlsx（默认 out-dir/{项目名}-LLD设计-时间戳.xlsx）")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.mode == "plan":
        return cmd_plan(args)
    if args.mode == "collect":
        return cmd_collect(args)
    if args.mode == "integrate":
        return cmd_integrate(args)
    raise SystemExit(f"unknown mode {args.mode}")


if __name__ == "__main__":
    raise SystemExit(main())
