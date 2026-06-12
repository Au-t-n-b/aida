"""In-process L3 skill execution (ISPR)."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Callable, List, Optional

from runtime.generic_runner import run_via_main
from runtime.job_types import SkillJobRequest, SkillJobResult
from runtime.registry_loader import L3SkillDef, load_l3_index, resolve_package_dir


def resolve_agent_skill_root(start: Optional[Path] = None) -> Path:
    """Return the agent-skill_full1 directory."""
    candidates: list[Path] = []
    env_root = os.environ.get("A3_AGENT_SKILL_ROOT") or os.environ.get("AGENT_SKILL_ROOT")
    if env_root:
        p = Path(env_root).expanduser()
        candidates.append(p if p.name == "agent-skill_full1" else p / "agent-skill_full1")

    if start is not None:
        candidates.extend([start.resolve(), *start.resolve().parents])

    candidates.extend([Path.cwd(), *Path.cwd().parents])

    seen: set[str] = set()
    for parent in candidates:
        try:
            resolved = parent.resolve()
        except OSError:
            resolved = parent
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.name == "agent-skill_full1" and resolved.is_dir():
            return resolved
        nested = resolved / "agent-skill_full1"
        if nested.is_dir():
            return nested.resolve()

    raise FileNotFoundError(
        "未找到 agent-skill_full1；可设置 AGENT_SKILL_ROOT 指向 agent-skill_full1 或其父目录"
    )


def _import_run_job(entrypoint: Path) -> Optional[Callable[..., SkillJobResult]]:
    if not entrypoint.is_file():
        return None
    module_name = f"_ispr_{entrypoint.stem}_{abs(hash(str(entrypoint.resolve())))}"
    spec = importlib.util.spec_from_file_location(module_name, entrypoint)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    scripts_dir = str(entrypoint.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    package_root = str(entrypoint.resolve().parents[1])
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    spec.loader.exec_module(module)
    fn = getattr(module, "run_job", None)
    return fn if callable(fn) else None


def _collect_output_files(out_dir: Path) -> tuple[Path, ...]:
    files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".xlsx", ".xls", ".md"})
    return tuple(files)


def run_l3_job(
    intent: str,
    request: SkillJobRequest,
    *,
    agent_skill_root: Optional[Path] = None,
    pass_prior: Optional[List[str]] = None,
) -> SkillJobResult:
    root = agent_skill_root or resolve_agent_skill_root()
    index = load_l3_index(root)
    skill = index.get(intent)
    if skill is None:
        return SkillJobResult(
            status="error",
            output_files=(),
            summary=f"未在 l3_skill_index 中找到命令：{intent}",
            errors=(f"unknown intent: {intent}",),
        )
    if skill.unsupported or skill.pending:
        return SkillJobResult(
            status="error",
            output_files=(),
            summary=f"`{intent}` 标记为 pending/unsupported，无法执行。",
            errors=(skill.note or "unsupported",),
            sub_skill_name=skill.package,
        )
    if not skill.package or not skill.entrypoint:
        return SkillJobResult(
            status="error",
            output_files=(),
            summary=f"`{intent}` 缺少 package/entrypoint 配置。",
            errors=("missing package or entrypoint",),
        )

    package_dir = resolve_package_dir(root, skill.package)
    package_name = package_dir.name
    entrypoint = (package_dir / skill.entrypoint).resolve()
    request.out_dir.mkdir(parents=True, exist_ok=True)

    run_job_fn = _import_run_job(entrypoint)
    if run_job_fn is not None:
        try:
            result = run_job_fn(
                intent=intent,
                skill_def=skill,
                topology=request.inputs.get("topology") or request.inputs.get("007"),
                resource=request.inputs.get("resource"),
                out_dir=request.out_dir,
                inputs=request.inputs,
                options=request.options,
            )
        except TypeError:
            try:
                result = run_job_fn(
                    intent=intent,
                    topology=request.inputs.get("topology") or request.inputs.get("007"),
                    resource=request.inputs.get("resource"),
                    out_dir=request.out_dir,
                    **request.options,
                )
            except Exception as exc:
                return SkillJobResult(
                    status="error",
                    output_files=_collect_output_files(request.out_dir),
                    summary=f"`{intent}` 执行异常。",
                    errors=(str(exc),),
                    sub_skill_name=package_name,
                )
        except Exception as exc:
            return SkillJobResult(
                status="error",
                output_files=_collect_output_files(request.out_dir),
                summary=f"`{intent}` 执行异常。",
                errors=(str(exc),),
                sub_skill_name=package_name,
            )

        if isinstance(result, SkillJobResult):
            if result.sub_skill_name == "":
                return SkillJobResult(
                    status=result.status,
                    output_files=result.output_files,
                    summary=result.summary,
                    errors=result.errors,
                    sub_skill_name=package_name,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
            return result

    prior = pass_prior or list(request.options.get("pass_prior") or [])
    return run_via_main(
        skill,
        intent,
        request,
        agent_skill_root=root,
        package_name=package_name,
        pass_prior=prior,
    )
