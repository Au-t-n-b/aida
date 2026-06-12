"""Expand L1/L2 intents to executable task phases."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from dispatch_cli_builder import build_cli, entrypoint_path
from dispatch_config_loader import DispatchTree, L2Policy, load_l3_index
from dispatch_path_utils import SKILL_ROOT


@dataclass
class TaskItem:
    seq: int
    intent: str
    child_skill: str = ""
    child_package: str = ""
    status: str = "ready"
    cli: str = ""
    note: Optional[str] = None


@dataclass
class PhaseItem:
    l2_intent: str
    l2_strategy: str = ""
    pass_prior: List[str] = field(default_factory=list)
    tasks: List[TaskItem] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "ready"
    note: Optional[str] = None


def _py() -> str:
    return sys.executable or "python"


def _build_task(
    seq: int,
    intent: str,
    topology_path: Optional[Path],
    resource_path: Optional[Path],
    out_dir: Path,
) -> TaskItem:
    l3_index = load_l3_index()
    skill_def = l3_index.get(intent)
    if not skill_def:
        return TaskItem(seq=seq, intent=intent, status="missing_index")

    if skill_def.unsupported:
        return TaskItem(seq=seq, intent=intent, status="unsupported", note=skill_def.note)
    if skill_def.pending:
        return TaskItem(seq=seq, intent=intent, status="pending", note=skill_def.note)

    ep = entrypoint_path(skill_def)
    if not ep.is_file():
        return TaskItem(seq=seq, intent=intent, status="missing_entrypoint")

    cli = build_cli(
        skill_def,
        intent,
        out_dir,
        topology=topology_path,
        resource=resource_path,
        prior_flags="",
    )
    pkg_name = Path(skill_def.package).name.strip("/")
    return TaskItem(
        seq=seq,
        intent=intent,
        child_skill=pkg_name,
        child_package=skill_def.package,
        status="ready",
        cli=cli,
        note=skill_def.note,
    )


def _expand_children(
    l2: str,
    pol: L2Policy,
    children: List[str],
    topology_path: Optional[Path],
    resource_path: Optional[Path],
    out_dir: Path,
) -> PhaseItem:
    if not children:
        return PhaseItem(l2_intent=l2, l2_strategy=pol.strategy, status="error", errors=[f"no children in tree: {l2}"])

    tasks: List[TaskItem] = []
    errors: List[str] = []
    skipped: List[str] = []

    for seq, intent in enumerate(children, start=1):
        task = _build_task(seq, intent, topology_path, resource_path, out_dir)
        if task.status == "missing_index":
            errors.append(f"no l3_skill_index for: {intent}")
        elif task.status in ("unsupported", "pending"):
            skipped.append(intent)
        elif task.status == "missing_entrypoint":
            errors.append(f"entrypoint missing for: {intent}")
        tasks.append(task)

    return PhaseItem(
        l2_intent=l2,
        l2_strategy=pol.strategy,
        pass_prior=list(pol.pass_prior),
        tasks=tasks,
        skipped=skipped,
        errors=errors,
        status="ready" if any(t.status == "ready" for t in tasks) else "skipped",
        note=pol.note,
    )


def _expand_direct(
    l2: str,
    pol: L2Policy,
    topology_path: Optional[Path],
    resource_path: Optional[Path],
    out_dir: Path,
) -> PhaseItem:
    l3_index = load_l3_index()
    third = pol.third_intent or l2
    skill_def = l3_index.get(third)
    cs = pol.child_skill or {}
    pkg = skill_def.package if skill_def and skill_def.package else cs.get("package", "")
    if skill_def and skill_def.entrypoint:
        ep = entrypoint_path(skill_def)
    else:
        ep = (SKILL_ROOT / pkg / cs.get("entrypoint", "")).resolve()

    status = "ready" if ep.is_file() else "missing_entrypoint"
    cli = ""
    if status == "ready" and skill_def:
        cli = build_cli(skill_def, third, out_dir, topology=topology_path, resource=resource_path)
    elif status == "ready":
        parts = [_py(), str(ep), "--out-dir", str(out_dir)]
        if topology_path is not None:
            parts += ["--connect", str(topology_path)]
        if resource_path is not None:
            parts += ["--resource", str(resource_path)]
        cli = " ".join(parts)

    errors = [] if status == "ready" else [f"missing: {ep}"]
    return PhaseItem(
        l2_intent=l2,
        l2_strategy=pol.strategy,
        pass_prior=list(pol.pass_prior),
        tasks=[
            TaskItem(
                seq=1,
                intent=third,
                child_skill=Path(pkg).name if pkg else "",
                child_package=pkg,
                status=status,
                cli=cli,
            )
        ],
        errors=errors,
        status=status,
    )


def _expand_nested(
    l2: str,
    pol: L2Policy,
    topology_path: Optional[Path],
    resource_path: Optional[Path],
    out_dir: Path,
) -> PhaseItem:
    cond = pol.conductor or {}
    pkg = cond.get("package", "")
    ep = (SKILL_ROOT / pkg / cond.get("entrypoint", "")).resolve()
    mode = cond.get("default_mode", "plan")
    status = "ready" if ep.is_file() else "missing_entrypoint"
    parts = [_py(), str(ep), "--mode", mode, "--out-dir", str(out_dir)]
    if topology_path is not None:
        parts += ["--topology", str(topology_path)]
    if resource_path is not None:
        parts += ["--resource", str(resource_path)]
    cli = " ".join(parts)
    errors = [] if status == "ready" else [f"missing: {ep}"]
    child = Path(pkg).name if pkg else ""
    return PhaseItem(
        l2_intent=l2,
        l2_strategy=pol.strategy,
        pass_prior=list(pol.pass_prior),
        tasks=[
            TaskItem(
                seq=1,
                intent=l2,
                child_skill=child,
                child_package=pkg,
                status=status,
                cli=cli if status == "ready" else "",
            )
        ],
        errors=errors,
        status=status,
    )


def expand_l2(
    l2: str,
    tree: DispatchTree,
    policies: Dict[str, L2Policy],
    topology_path: Optional[Path],
    resource_path: Optional[Path],
    out_dir: Path,
) -> PhaseItem:
    pol = policies.get(l2)
    if not pol:
        return PhaseItem(l2_intent=l2, status="error", errors=[f"no l2 policy: {l2}"])
    if pol.strategy == "unsupported":
        return PhaseItem(l2_intent=l2, l2_strategy="unsupported", status="skipped", note=pol.note)

    children = tree.l2_children.get(l2, [])

    if pol.strategy in ("children", "sheet_expand", "multi_direct"):
        if not children:
            return _expand_direct(l2, pol, topology_path, resource_path, out_dir)
        return _expand_children(l2, pol, children, topology_path, resource_path, out_dir)
    if pol.strategy == "direct":
        return _expand_direct(l2, pol, topology_path, resource_path, out_dir)
    if pol.strategy == "nested_workflow":
        return _expand_nested(l2, pol, topology_path, resource_path, out_dir)

    return PhaseItem(l2_intent=l2, status="error", errors=[f"unknown strategy: {pol.strategy}"])


def _should_schedule_l2_at_l1(
    l2: str,
    policies: Dict[str, L2Policy],
    without_offline: Set[str],
) -> tuple[bool, str]:
    if l2 in without_offline:
        return False, "unsupported_offline"
    pol = policies.get(l2)
    if not pol:
        return False, "no_l2_policy"
    if pol.strategy == "unsupported":
        return False, "l2_unsupported"
    return True, "ready"


def expand_dispatch(
    intent: str,
    tree: DispatchTree,
    policies: Dict[str, L2Policy],
    without_offline: Set[str],
    topology_path: Optional[Path],
    resource_path: Optional[Path],
    out_dir: Path,
) -> tuple[str, str, List[PhaseItem], List[str], List[str]]:
    phases: List[PhaseItem] = []
    skipped: List[str] = []
    errors: List[str] = []

    if intent in tree.l1_to_l2:
        anchor_level = "L1"
        for l2 in tree.l1_to_l2[intent]:
            ok, reason = _should_schedule_l2_at_l1(l2, policies, without_offline)
            if not ok:
                skipped.append(f"{l2}({reason})")
                continue
            phase = expand_l2(l2, tree, policies, topology_path, resource_path, out_dir)
            if phase.status == "skipped" and phase.note:
                skipped.append(f"{l2}({phase.note})")
                continue
            phases.append(phase)
            errors.extend(phase.errors)
        return intent, anchor_level, phases, skipped, errors

    if intent in tree.l2_children:
        anchor_level = "L2"
        phase = expand_l2(intent, tree, policies, topology_path, resource_path, out_dir)
        phases.append(phase)
        errors.extend(phase.errors)
        return intent, anchor_level, phases, skipped, errors

    raise ValueError(f"unknown intent: {intent}")
