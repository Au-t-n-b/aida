"""Subprocess LLD conductor plan / run / integrate."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from subprocess_runner import run_l3_subprocess
from registry_loader import load_l3_index


def _step_runnable(step: dict, index: dict) -> tuple[bool, str]:
    status = str(step.get("status", ""))
    if status in {"skipped", "skipped_not_eligible"}:
        return False, status
    if step.get("step_type") == "integrate":
        return True, status
    if step.get("enabled") and step.get("child_skill") and step.get("cli_command"):
        return True, status
    instruction = str(step.get("instruction", ""))
    skill = index.get(instruction)
    if skill and not skill.unsupported and not skill.pending and skill.package:
        return True, status
    if status == "pending_no_handler":
        return False, status
    return False, status


@dataclass
class ConductorStepResult:
    step_id: str
    instruction: str
    status: str
    summary: str
    output_files: tuple[Path, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass
class ConductorRunResult:
    status: str
    mode: str
    step_results: List[ConductorStepResult] = field(default_factory=list)
    output_files: tuple[Path, ...] = ()
    summary: str = ""
    errors: tuple[str, ...] = ()
    plan_path: Optional[Path] = None
    run_dir: Optional[Path] = None


@dataclass(frozen=True)
class IntegrateResult:
    status: str
    output_files: tuple[Path, ...]
    summary: str
    errors: tuple[str, ...] = ()
    sub_skill_name: str = "a3_LLD_generate_code1"


def _conductor_scripts(capability_root: Path) -> Path:
    return capability_root / "a3_LLD_generate_code1" / "scripts"


def _ensure_conductor_import(capability_root: Path) -> None:
    scripts = str(_conductor_scripts(capability_root))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


def plan_conductor(
    *,
    capability_root: Path,
    topology: Path,
    resource: Path,
    out_dir: Path,
    run_id: Optional[str] = None,
    user_id: str = "local",
    project_id: str = "local",
    project_name: str = "project",
) -> dict:
    _ensure_conductor_import(capability_root)
    import pandas as pd
    from lld_path_utils import new_run_dir, sanitize_project_name
    from lld_staging import save_manifest
    from lld_workflow import build_workflow_plan, save_workflow_plan

    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = new_run_dir(out_dir, run_id)
    sheet_names = list(pd.ExcelFile(topology).sheet_names)
    plan = build_workflow_plan(
        topology=topology,
        resource=resource,
        run_dir=run_dir,
        out_dir=out_dir,
        user_id=user_id,
        project_id=project_id,
        project_name=sanitize_project_name(project_name),
        sheet_names=sheet_names,
    )
    save_workflow_plan(plan, run_dir)
    manifest = {"run_id": plan["run_id"], "steps": {s["id"]: {"status": s["status"]} for s in plan["steps"]}}
    save_manifest(run_dir / "manifest.json", manifest)
    plan["_plan_path"] = str(run_dir / "workflow_plan.json")
    plan["_run_dir"] = str(run_dir)
    return plan


def run_conductor_steps(
    plan: dict,
    *,
    skill_root: Path,
    capability_root: Path,
    topology: Path,
    resource: Path,
    on_step_complete: Optional[Callable[[ConductorStepResult], None]] = None,
    keep_going: bool = True,
) -> ConductorRunResult:
    out_dir = Path(str(plan.get("out_dir", plan.get("_run_dir", "."))))
    run_dir = Path(plan.get("_run_dir") or out_dir)
    project_output = skill_root / "ProjectData" / "Output"
    index = load_l3_index(capability_root)
    step_results: List[ConductorStepResult] = []
    all_outputs: list[Path] = []
    errors: list[str] = []
    integrate_ok = False

    for step in plan.get("steps", []):
        step_id = str(step.get("id", ""))
        instruction = str(step.get("instruction", ""))

        if not step.get("eligible"):
            step_results.append(
                ConductorStepResult(
                    step_id=step_id,
                    instruction=instruction,
                    status="skipped",
                    summary="skipped_not_eligible",
                )
            )
            continue

        runnable, plan_status = _step_runnable(step, index)
        if not runnable:
            step_results.append(
                ConductorStepResult(
                    step_id=step_id,
                    instruction=instruction,
                    status="skipped",
                    summary=plan_status or str(step.get("agent_hint", "skipped")),
                )
            )
            continue

        if step.get("step_type") == "integrate" or instruction == "融合完整LLD设计":
            integrate_out = run_dir / "integrate"
            integrate_out.mkdir(parents=True, exist_ok=True)
            # 优先扫描本次 step_out 的新产物，再合并历史 Output
            scan_dirs = [run_dir / "step_out", project_output, out_dir]
            integ = integrate_conductor(
                skill_root=skill_root,
                capability_root=capability_root,
                scan_dirs=[p for p in scan_dirs if p.is_dir()],
                resource=resource,
                topology=topology,
                out_dir=integrate_out,
                project_name=str(plan.get("project_name", "project")),
            )
            integrate_ok = integ.status == "ok"
            sr = ConductorStepResult(
                step_id=step_id,
                instruction=instruction,
                status=integ.status,
                summary=integ.summary,
                output_files=integ.output_files,
                errors=integ.errors,
            )
            step_results.append(sr)
            all_outputs.extend(integ.output_files)
            if on_step_complete:
                on_step_complete(sr)
            if integ.status != "ok":
                errors.extend(integ.errors or (integ.summary,))
            continue

        step_out = run_dir / "step_out" / step_id
        step_out.mkdir(parents=True, exist_ok=True)
        result = run_l3_subprocess(
            instruction,
            capability_root=capability_root,
            skill_root=skill_root,
            topology=topology,
            resource=resource,
            out_dir=step_out,
            scan_dir=run_dir,
        )
        sr = ConductorStepResult(
            step_id=step_id,
            instruction=instruction,
            status=result.status,
            summary=result.summary,
            output_files=result.output_files,
            errors=result.errors,
        )
        step_results.append(sr)
        all_outputs.extend(result.output_files)
        if on_step_complete:
            on_step_complete(sr)
        if result.status != "ok":
            err_msg = (result.errors[0] if result.errors else result.summary) or instruction
            errors.append(f"{instruction}: {err_msg}")
            if not keep_going:
                break

    ok_count = sum(1 for s in step_results if s.status == "ok")
    skipped_count = sum(1 for s in step_results if s.status == "skipped")
    error_count = sum(1 for s in step_results if s.status == "error")
    if integrate_ok:
        rc = "ok"
    elif ok_count > 0:
        rc = "partial"
    else:
        rc = "error"
    summary = (
        f"Conductor 执行完成：成功 {ok_count}，失败 {error_count}，跳过 {skipped_count}。"
        + (" 已生成融合 LLD。" if integrate_ok else "")
    )
    return ConductorRunResult(
        status=rc,
        mode="run",
        step_results=step_results,
        output_files=tuple(dict.fromkeys(all_outputs)),
        summary=summary,
        errors=tuple(errors),
        plan_path=Path(plan["_plan_path"]) if plan.get("_plan_path") else None,
        run_dir=run_dir,
    )


def integrate_conductor(
    *,
    skill_root: Path,
    capability_root: Path,
    scan_dirs: List[Path],
    resource: Optional[Path] = None,
    topology: Optional[Path] = None,
    out_dir: Path,
    project_name: str = "project",
) -> IntegrateResult:
    _ensure_conductor_import(capability_root)
    from lld_path_utils import default_lld_output_path, sanitize_project_name
    from offline_integrate_lld import integrate_lld

    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = default_lld_output_path(out_dir, sanitize_project_name(project_name))
    usable_dirs = [p for p in scan_dirs if p.is_dir()]

    try:
        result_path = integrate_lld(
            project_name=sanitize_project_name(project_name),
            output_path=output_path,
            scan_dirs=usable_dirs,
            resource_path=resource,
        )
        return IntegrateResult(
            status="ok",
            output_files=(Path(result_path),),
            summary=f"LLD 融合完成：{Path(result_path).name}",
        )
    except Exception as exc:
        return IntegrateResult(
            status="error",
            output_files=(),
            summary="LLD 融合失败。",
            errors=(str(exc),),
        )
