"""In-process LLD conductor plan / run / integrate."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from runtime.executor import run_l3_job
from runtime.job_types import SkillJobRequest, SkillJobResult


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


def _conductor_scripts(agent_skill_root: Path) -> Path:
    return agent_skill_root / "a3_LLD_generate_code1" / "scripts"


def _ensure_conductor_import(agent_skill_root: Path) -> None:
    scripts = str(_conductor_scripts(agent_skill_root))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


def plan_conductor(
    *,
    agent_skill_root: Path,
    topology: Path,
    resource: Path,
    out_dir: Path,
    run_id: Optional[str] = None,
    user_id: str = "local",
    project_id: str = "local",
    project_name: str = "project",
) -> dict:
    _ensure_conductor_import(agent_skill_root)
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
    agent_skill_root: Path,
    topology: Path,
    resource: Path,
    on_step_complete: Optional[Callable[[ConductorStepResult], None]] = None,
    keep_going: bool = True,
) -> ConductorRunResult:
    out_dir = Path(str(plan.get("out_dir", plan.get("_run_dir", "."))))
    run_dir = Path(plan.get("_run_dir") or out_dir)
    step_results: List[ConductorStepResult] = []
    all_outputs: list[Path] = []
    errors: list[str] = []
    rc = "ok"

    for step in plan.get("steps", []):
        if not step.get("eligible") or step.get("status") in {"pending_no_handler", "skipped"}:
            step_results.append(
                ConductorStepResult(
                    step_id=str(step.get("id", "")),
                    instruction=str(step.get("instruction", "")),
                    status="skipped",
                    summary=str(step.get("status", "skipped")),
                )
            )
            continue

        instruction = str(step.get("instruction", ""))
        child = step.get("child_skill") or {}
        package = str(child.get("package", "")).lstrip("./").lstrip("../")
        if not package:
            step_results.append(
                ConductorStepResult(
                    step_id=str(step.get("id", "")),
                    instruction=instruction,
                    status="skipped",
                    summary="无 child_skill",
                )
            )
            continue

        step_out = run_dir / "step_out" / str(step.get("id", "step"))
        step_out.mkdir(parents=True, exist_ok=True)
        request = SkillJobRequest(
            intent=instruction,
            inputs={"007": topology, "topology": topology, "resource": resource},
            out_dir=step_out,
        )
        result = run_l3_job(instruction, request, agent_skill_root=agent_skill_root)
        sr = ConductorStepResult(
            step_id=str(step.get("id", "")),
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
            errors.extend(result.errors or (result.summary,))
            rc = "error"
            if not keep_going:
                break

    ok_count = sum(1 for s in step_results if s.status == "ok")
    summary = f"Conductor 执行完成：{ok_count}/{len(step_results)} 步成功。"
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
    agent_skill_root: Path,
    scan_dirs: List[Path],
    resource: Optional[Path] = None,
    topology: Optional[Path] = None,
    out_dir: Path,
    project_name: str = "project",
    templates_dir: Optional[Path] = None,
) -> SkillJobResult:
    _ensure_conductor_import(agent_skill_root)
    from lld_path_utils import default_lld_output_path, sanitize_project_name
    from offline_integrate_lld import integrate_lld

    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = default_lld_output_path(out_dir, sanitize_project_name(project_name))
    try:
        result_path = integrate_lld(
            project_name=sanitize_project_name(project_name),
            output_path=output_path,
            scan_dirs=[p for p in scan_dirs if p.is_dir()],
            resource_path=resource,
        )
        return SkillJobResult(
            status="ok",
            output_files=(Path(result_path),),
            summary=f"LLD 融合完成：{Path(result_path).name}",
            sub_skill_name="a3_LLD_generate_code1",
        )
    except Exception as exc:
        return SkillJobResult(
            status="error",
            output_files=(),
            summary="LLD 融合失败。",
            errors=(str(exc),),
            sub_skill_name="a3_LLD_generate_code1",
        )
