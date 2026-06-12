#!/usr/bin/env python3
"""LLD dispatch orchestrator: list | plan | run (L1/L2 entry)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

try:
    import yaml  # noqa: F401
except ImportError:
    print("ERROR: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2) from None

from dispatch_config_loader import load_dispatch_tree, load_l2_policies, load_l2_without_offline
from dispatch_expander import expand_dispatch
from dispatch_path_utils import DEFAULT_OUT_DIR, PACKAGE_ROOT, require_under_cwd, resolve_local


def _phase_to_dict(phase) -> dict:
    return {
        "l2_intent": phase.l2_intent,
        "l2_strategy": phase.l2_strategy,
        "pass_prior": phase.pass_prior,
        "status": phase.status,
        "note": phase.note,
        "skipped": phase.skipped,
        "errors": phase.errors,
        "tasks": [
            {
                "seq": t.seq,
                "intent": t.intent,
                "child_skill": t.child_skill,
                "child_package": t.child_package,
                "status": t.status,
                "cli": t.cli,
                "note": t.note,
            }
            for t in phase.tasks
        ],
    }


def _build_plan(
    *,
    intent: str,
    topo: Path | None,
    res: Path | None,
    out_dir: Path,
) -> dict:
    tree = load_dispatch_tree()
    policies = load_l2_policies()
    without = load_l2_without_offline()
    out_dir.mkdir(parents=True, exist_ok=True)
    anchor, level, phases, skipped, errors = expand_dispatch(
        intent, tree, policies, without, topo, res, out_dir
    )
    return {
        "version": "1.0",
        "runtime": "standalone_offline",
        "anchor_intent": anchor,
        "anchor_level": level,
        "execution": "serial",
        "inputs": {
            "out_dir": str(out_dir),
            **({"topology": str(topo)} if topo else {}),
            **({"resource": str(res)} if res else {}),
        },
        "phases": [_phase_to_dict(p) for p in phases],
        "skipped": skipped,
        "errors": errors,
    }


def _resolve_inputs(args: argparse.Namespace, cwd: Path) -> tuple[Path | None, Path | None, Path]:
    topo: Path | None = None
    res: Path | None = None
    if args.topology:
        topo_raw = args.topology
        if not topo_raw.is_file():
            raise SystemExit("ERROR: topology file not found")
        topo = require_under_cwd(topo_raw, cwd, "topology")
    if args.resource:
        res_raw = args.resource
        if not res_raw.is_file():
            raise SystemExit("ERROR: resource file not found")
        res = require_under_cwd(res_raw, cwd, "resource")
    out_dir = resolve_local(args.out_dir or DEFAULT_OUT_DIR, cwd)
    return topo, res, out_dir


def cmd_list(_args: argparse.Namespace, _cwd: Path) -> int:
    tree = load_dispatch_tree()
    for l1, l2_list in sorted(tree.l1_to_l2.items()):
        print(f"{l1}\t{len(l2_list)} L2")
        for l2 in l2_list:
            children = tree.l2_children.get(l2, [])
            print(f"  {l2}\t{len(children)} children")
    return 0


def cmd_plan(args: argparse.Namespace, cwd: Path) -> int:
    try:
        topo, res, out_dir = _resolve_inputs(args, cwd)
        plan = _build_plan(intent=args.intent, topo=topo, res=res, out_dir=out_dir)
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if plan.get("errors"):
        print("WARN: plan has errors:", plan["errors"], file=sys.stderr)
    return 0


def cmd_run(args: argparse.Namespace, cwd: Path) -> int:
    dry = args.dry_run

    capability_root = PACKAGE_ROOT.resolve()
    skill_root = capability_root.parent
    runtime_root = str(skill_root / "runtime")
    if runtime_root not in sys.path:
        sys.path.insert(0, runtime_root)

    if args.intent:
        try:
            topo, res, out_dir = _resolve_inputs(args, cwd)
            plan = _build_plan(intent=args.intent, topo=topo, res=res, out_dir=out_dir)
        except ValueError as exc:
            raise SystemExit(f"ERROR: {exc}") from exc
    elif args.plan:
        plan_path = require_under_cwd(Path(args.plan), cwd, "plan")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    else:
        raise SystemExit("ERROR: run requires --intent or --plan")

    if dry:
        for phase in plan.get("phases", []):
            for t in phase.get("tasks", []):
                if t.get("status") == "ready":
                    print(f"DRY seq={t.get('seq')}: {t.get('intent', '')}")
        return 0

    from dispatch_runner import run_dispatch_plan

    result = run_dispatch_plan(
        plan,
        skill_root=skill_root,
        capability_root=capability_root,
        keep_going=args.keep_going,
    )
    if result.status != "ok":
        for err in result.errors:
            print(err, file=sys.stderr)
        return 1
    print(result.summary)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LLD dispatch orchestrator (offline)")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_plan = sub.add_parser("plan", help="Preview dispatch plan JSON on stdout")
    p_plan.add_argument("--intent", required=True, help="L1 or L2 standard command")
    p_plan.add_argument(
        "--topology",
        type=Path,
        default=None,
        help="optional pass-through to child skill CLI",
    )
    p_plan.add_argument(
        "--resource",
        type=Path,
        default=None,
        help="optional pass-through to child skill CLI",
    )
    p_plan.add_argument("--out-dir", type=Path, default=None)

    sub.add_parser("list", help="List dispatch tree")

    p_run = sub.add_parser("run", help="Execute dispatch plan")
    p_run.add_argument("--intent", help="L1 or L2 standard command (in-memory plan)")
    p_run.add_argument("--plan", type=Path, help="optional legacy plan JSON path")
    p_run.add_argument(
        "--topology",
        type=Path,
        default=None,
        help="required with --intent when child skills need topology",
    )
    p_run.add_argument(
        "--resource",
        type=Path,
        default=None,
        help="required with --intent when child skills need resource",
    )
    p_run.add_argument("--out-dir", type=Path, default=None)
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--keep-going", action="store_true")

    args = parser.parse_args()
    cwd = Path.cwd()

    if args.mode == "plan":
        return cmd_plan(args, cwd)
    if args.mode == "list":
        return cmd_list(args, cwd)
    if args.mode == "run":
        return cmd_run(args, cwd)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
