from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dispatch_runner import plan_dispatch, run_dispatch_plan
from skill_root import resolve_capability_root


@dataclass(frozen=True)
class DispatchExecutionResult:
    status: str
    command: str
    sub_skill_name: str
    run_dir: Path
    output_files: tuple[Path, ...]
    summary: str
    errors: tuple[str, ...] = ()
    task_count: int = 0
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


def execute_dispatch(
    *,
    skill_root: Path,
    run_id: str,
    command: str,
    input_007: Path,
    input_resource: Path,
    keep_going: bool = False,
) -> DispatchExecutionResult:
    capability_root = resolve_capability_root(skill_root)
    work_dir = skill_root / "ProjectData" / "Work" / run_id / "dispatch"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir = skill_root / "ProjectData" / "Output"

    try:
        plan = plan_dispatch(
            command,
            capability_root=capability_root,
            topology=input_007,
            resource=input_resource,
            out_dir=work_dir,
            run_id=run_id,
        )
        result = run_dispatch_plan(
            plan,
            skill_root=skill_root,
            capability_root=capability_root,
            keep_going=keep_going,
        )
    except Exception as exc:
        return DispatchExecutionResult(
            status="error",
            command=command,
            sub_skill_name="lld-dispatch-orchestrator.code1",
            run_dir=output_dir,
            output_files=(),
            summary=f"批次调度 `{command}` 失败。",
            errors=(str(exc),),
        )

    outputs = _copy_products(result.output_files, output_dir)
    ok_count = sum(1 for t in result.task_results if t.status == "ok")
    return DispatchExecutionResult(
        status=result.status,
        command=command,
        sub_skill_name="lld-dispatch-orchestrator.code1",
        run_dir=output_dir,
        output_files=outputs,
        summary=result.summary,
        errors=result.errors,
        task_count=len(result.task_results),
        ok_count=ok_count,
    )
