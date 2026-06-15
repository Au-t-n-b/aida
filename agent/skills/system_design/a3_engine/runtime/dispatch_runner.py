"""Subprocess L1/L2 dispatch plan + run (Skill-First)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from subprocess_runner import run_l3_subprocess


@dataclass
class DispatchTaskResult:
    seq: int
    intent: str
    status: str
    summary: str
    output_files: tuple[Path, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass
class DispatchRunResult:
    status: str
    anchor_intent: str
    task_results: List[DispatchTaskResult] = field(default_factory=list)
    output_files: tuple[Path, ...] = ()
    summary: str = ""
    errors: tuple[str, ...] = ()
    plan_path: Optional[Path] = None


def _dispatch_scripts(capability_root: Path) -> Path:
    return capability_root / "lld-dispatch-orchestrator.code1" / "scripts"


def _ensure_dispatch_import(capability_root: Path) -> None:
    scripts = str(_dispatch_scripts(capability_root))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


def plan_dispatch(
    intent: str,
    *,
    capability_root: Path,
    topology: Path,
    resource: Path,
    out_dir: Path,
    run_id: Optional[str] = None,
) -> dict:
    _ensure_dispatch_import(capability_root)
    from dispatch_config_loader import load_dispatch_tree, load_l2_policies, load_l2_without_offline
    from dispatch_expander import expand_dispatch
    tree = load_dispatch_tree()
    policies = load_l2_policies()
    without = load_l2_without_offline()
    out_dir.mkdir(parents=True, exist_ok=True)

    anchor, level, phases, skipped, errors = expand_dispatch(
        intent, tree, policies, without, topology, resource, out_dir
    )
    plan = {
        "version": "1.0",
        "runtime": "subprocess",
        "anchor_intent": anchor,
        "anchor_level": level,
        "execution": "serial",
        "inputs": {
            "out_dir": str(out_dir),
            "topology": str(topology),
            "resource": str(resource),
        },
        "phases": [
            {
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
            for phase in phases
        ],
        "skipped": skipped,
        "errors": errors,
    }
    return plan


def run_dispatch_plan(
    plan: dict,
    *,
    skill_root: Path,
    capability_root: Path,
    on_task_complete: Optional[Callable[[DispatchTaskResult], None]] = None,
    keep_going: bool = False,
) -> DispatchRunResult:
    plan_inputs = plan.get("inputs") or {}
    out_dir = Path(str(plan_inputs.get("out_dir", ".")))
    topology = Path(str(plan_inputs["topology"])) if plan_inputs.get("topology") else None
    resource = Path(str(plan_inputs["resource"])) if plan_inputs.get("resource") else None
    anchor = str(plan.get("anchor_intent", ""))

    task_results: List[DispatchTaskResult] = []
    all_outputs: list[Path] = []
    errors: list[str] = []
    rc = "ok"

    for phase in plan.get("phases", []):
        pass_prior = list(phase.get("pass_prior") or [])
        for task in phase.get("tasks", []):
            if task.get("status") != "ready":
                task_results.append(
                    DispatchTaskResult(
                        seq=int(task.get("seq", 0)),
                        intent=str(task.get("intent", "")),
                        status="skipped",
                        summary=str(task.get("note") or task.get("status")),
                    )
                )
                continue

            intent = str(task.get("intent", ""))
            result = run_l3_subprocess(
                intent,
                capability_root=capability_root,
                skill_root=skill_root,
                topology=topology,
                resource=resource,
                out_dir=out_dir,
                pass_prior=pass_prior,
            )
            tr = DispatchTaskResult(
                seq=int(task.get("seq", 0)),
                intent=intent,
                status=result.status,
                summary=result.summary,
                output_files=result.output_files,
                errors=result.errors,
            )
            task_results.append(tr)
            all_outputs.extend(result.output_files)
            if on_task_complete:
                on_task_complete(tr)
            if result.status != "ok":
                errors.extend(result.errors or (result.summary,))
                rc = "error"
                if not keep_going:
                    break
        if rc == "error" and not keep_going:
            break

    unique_outputs = tuple(dict.fromkeys(all_outputs))
    ok_count = sum(1 for t in task_results if t.status == "ok")
    summary = f"批次 `{anchor}` 完成：{ok_count}/{len(task_results)} 步成功。"
    return DispatchRunResult(
        status=rc,
        anchor_intent=anchor,
        task_results=task_results,
        output_files=unique_outputs,
        summary=summary,
        errors=tuple(errors),
        plan_path=None,
    )
