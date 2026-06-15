from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from conductor_runner import integrate_conductor, plan_conductor, run_conductor_steps
from skill_root import resolve_capability_root


@dataclass(frozen=True)
class ConductorExecutionResult:
    status: str
    command: str
    sub_skill_name: str
    run_dir: Path
    output_files: tuple[Path, ...]
    summary: str
    errors: tuple[str, ...] = ()
    step_count: int = 0
    ok_count: int = 0


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _copy_products(files: tuple[Path, ...], output_dir: Path) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    copied: list[Path] = []
    for src in files:
        dst = output_dir / f"{src.stem}_{ts}{src.suffix}"
        shutil.copy2(src, dst)
        copied.append(dst)
    return tuple(copied)


def execute_conductor(
    *,
    skill_root: Path,
    run_id: str,
    command: str,
    mode: str,
    input_007: Path,
    input_resource: Path,
) -> ConductorExecutionResult:
    capability_root = resolve_capability_root(skill_root)
    work_base = skill_root / "ProjectData" / "Work" / run_id / "conductor"
    work_base.mkdir(parents=True, exist_ok=True)
    output_dir = skill_root / "ProjectData" / "Output"
    scan_dirs = [skill_root / "ProjectData" / "Output", work_base]

    try:
        if mode == "integrate":
            result = integrate_conductor(
                skill_root=skill_root,
                capability_root=capability_root,
                scan_dirs=scan_dirs,
                resource=input_resource,
                topology=input_007,
                out_dir=work_base,
            )
            outputs = _copy_products(result.output_files, output_dir)
            return ConductorExecutionResult(
                status=result.status,
                command=command,
                sub_skill_name="a3_LLD_generate_code1",
                run_dir=output_dir,
                output_files=outputs,
                summary=result.summary,
                errors=result.errors,
            )

        if mode == "plan_run":
            plan = plan_conductor(
                capability_root=capability_root,
                topology=input_007,
                resource=input_resource,
                out_dir=work_base,
                run_id=run_id,
            )
            run_result = run_conductor_steps(
                plan,
                skill_root=skill_root,
                capability_root=capability_root,
                topology=input_007,
                resource=input_resource,
                keep_going=True,
            )
            outputs = _copy_products(run_result.output_files, output_dir)
            ok_count = sum(1 for s in run_result.step_results if s.status == "ok")
            return ConductorExecutionResult(
                status=run_result.status,
                command=command,
                sub_skill_name="a3_LLD_generate_code1",
                run_dir=output_dir,
                output_files=outputs,
                summary=run_result.summary,
                errors=run_result.errors,
                step_count=len(run_result.step_results),
                ok_count=ok_count,
            )

        plan = plan_conductor(
            capability_root=capability_root,
            topology=input_007,
            resource=input_resource,
            out_dir=work_base,
            run_id=run_id,
        )
        if mode == "plan":
            plan_file = Path(plan.get("_plan_path", work_base / "workflow_plan.json"))
            outputs = (plan_file,) if plan_file.is_file() else ()
            eligible = sum(1 for s in plan.get("steps", []) if s.get("eligible"))
            return ConductorExecutionResult(
                status="ok",
                command=command,
                sub_skill_name="a3_LLD_generate_code1",
                run_dir=output_dir,
                output_files=outputs,
                summary=f"Conductor 计划已生成，{eligible} 步可执行。",
                step_count=len(plan.get("steps", [])),
                ok_count=eligible,
            )

        run_result = run_conductor_steps(
            plan,
            skill_root=skill_root,
            capability_root=capability_root,
            topology=input_007,
            resource=input_resource,
            keep_going=True,
        )
        outputs = _copy_products(run_result.output_files, output_dir)
        ok_count = sum(1 for s in run_result.step_results if s.status == "ok")
        return ConductorExecutionResult(
            status=run_result.status,
            command=command,
            sub_skill_name="a3_LLD_generate_code1",
            run_dir=output_dir,
            output_files=outputs,
            summary=run_result.summary,
            errors=run_result.errors,
            step_count=len(run_result.step_results),
            ok_count=ok_count,
        )
    except Exception as exc:
        return ConductorExecutionResult(
            status="error",
            command=command,
            sub_skill_name="a3_LLD_generate_code1",
            run_dir=output_dir,
            output_files=(),
            summary=f"Conductor `{command}` 执行失败。",
            errors=(str(exc),),
        )
