"""Fallback ISPR: invoke pipeline main(argv) in-process."""

from __future__ import annotations

import importlib.util
import io
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional

from runtime.job_types import SkillJobRequest, SkillJobResult
from runtime.kwarg_builder import build_argv
from runtime.registry_loader import L3SkillDef, resolve_package_dir


def _import_module(entrypoint: Path):
    module_name = f"_ispr_{entrypoint.stem}_{abs(hash(str(entrypoint.resolve())))}"
    spec = importlib.util.spec_from_file_location(module_name, entrypoint)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {entrypoint}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    scripts_dir = str(entrypoint.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    package_root = str(entrypoint.resolve().parents[1])
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    spec.loader.exec_module(module)
    return module


def _collect_outputs(out_dir: Path) -> tuple[Path, ...]:
    patterns = (".xlsx", ".xls", ".md", ".docx")
    files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.suffix.lower() in patterns)
    return tuple(files)


def _work_cwd(request: SkillJobRequest) -> Path:
    candidates = [request.inputs.get("007"), request.inputs.get("topology"), request.inputs.get("resource")]
    for item in candidates:
        if item is not None:
            return Path(item).resolve().parent
    return request.out_dir.resolve().parent


def run_via_main(
    skill: L3SkillDef,
    intent: str,
    request: SkillJobRequest,
    *,
    agent_skill_root: Path,
    package_name: str,
    pass_prior: Optional[list[str]] = None,
) -> SkillJobResult:
    package_dir = resolve_package_dir(agent_skill_root, skill.package)
    entrypoint = (package_dir / skill.entrypoint).resolve()
    if not entrypoint.is_file():
        return SkillJobResult(
            status="error",
            output_files=(),
            summary=f"未找到 entrypoint：{entrypoint}",
            errors=(f"missing entrypoint: {entrypoint}",),
            sub_skill_name=package_name,
        )

    argv = build_argv(
        skill,
        intent,
        request.out_dir,
        topology=request.inputs.get("topology") or request.inputs.get("007"),
        resource=request.inputs.get("resource"),
        pass_prior=pass_prior,
        scan_dir=request.out_dir.parent,
    )

    try:
        module = _import_module(entrypoint)
    except Exception as exc:
        return SkillJobResult(
            status="error",
            output_files=(),
            summary=f"加载子 Skill 模块失败：{package_name}",
            errors=(str(exc),),
            sub_skill_name=package_name,
        )

    if hasattr(module, "run_job") and callable(module.run_job):
        try:
            return module.run_job(
                intent=intent,
                skill_def=skill,
                topology=request.inputs.get("topology") or request.inputs.get("007"),
                resource=request.inputs.get("resource"),
                out_dir=request.out_dir,
                inputs=request.inputs,
                options=request.options,
            )
        except TypeError:
            return module.run_job(
                intent=intent,
                topology=request.inputs.get("topology") or request.inputs.get("007"),
                resource=request.inputs.get("resource"),
                out_dir=request.out_dir,
                **request.options,
            )

    main_fn = getattr(module, "main", None)
    if not callable(main_fn):
        return SkillJobResult(
            status="error",
            output_files=(),
            summary=f"{package_name} 缺少 run_job() 或 main()",
            errors=("no entry function",),
            sub_skill_name=package_name,
        )

    work_cwd = _work_cwd(request)
    request.out_dir.mkdir(parents=True, exist_ok=True)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    old_cwd = os.getcwd()
    rc = 1
    try:
        os.chdir(str(work_cwd))
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                result = main_fn(argv)
            except TypeError:
                result = main_fn()
            rc = 0 if result is None else int(result)
    except SystemExit as exc:
        rc = int(exc.code) if isinstance(exc.code, int) else (0 if exc.code in (None, 0) else 1)
    except Exception as exc:
        return SkillJobResult(
            status="error",
            output_files=_collect_outputs(request.out_dir),
            summary=f"`{intent}` 执行异常。",
            errors=(str(exc),),
            sub_skill_name=package_name,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )
    finally:
        os.chdir(old_cwd)

    outputs = _collect_outputs(request.out_dir)
    if rc != 0:
        err = stderr_buf.getvalue().strip() or stdout_buf.getvalue().strip() or f"exit code {rc}"
        return SkillJobResult(
            status="error",
            output_files=outputs,
            summary=f"`{intent}` 执行失败。",
            errors=(err,),
            sub_skill_name=package_name,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )

    if not outputs:
        return SkillJobResult(
            status="error",
            output_files=(),
            summary=f"`{intent}` 执行完成但未发现产物。",
            errors=("empty output",),
            sub_skill_name=package_name,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )

    return SkillJobResult(
        status="ok",
        output_files=outputs,
        summary=f"`{intent}` 完成，生成 {len(outputs)} 个产物。",
        sub_skill_name=package_name,
        stdout=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
    )
