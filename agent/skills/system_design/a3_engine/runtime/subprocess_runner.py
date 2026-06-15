"""Skill-First subprocess execution for L3 workflows."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from argv_builder import build_argv
from registry_loader import L3SkillDef, load_l3_index, resolve_package_dir


@dataclass(frozen=True)
class SubprocessResult:
    status: str
    output_files: tuple[Path, ...]
    summary: str
    errors: tuple[str, ...] = ()
    sub_skill_name: str = ""
    stdout: str = ""
    stderr: str = ""


_SKIP_OUTPUT_NAMES = frozenset({
    "dispatch_plan.json",
    "workflow_plan.json",
    "manifest.json",
    "steps.md",
    "a3_opening_result.md",
})


def _collect_outputs(out_dir: Path) -> tuple[Path, ...]:
    patterns = (".xlsx", ".xls", ".md", ".docx", ".json", ".zip")
    files = sorted(
        p
        for p in out_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in patterns
        and p.name not in _SKIP_OUTPUT_NAMES
    )
    return tuple(files)


def run_py(
    *,
    skill_root: Path,
    script_path: Path,
    extra_args: Optional[List[str]] = None,
    timeout: int = 900,
) -> Tuple[bool, str, str]:
    cmd = [sys.executable, str(script_path), *(extra_args or [])]
    proc = subprocess.run(
        cmd,
        cwd=str(skill_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    out = proc.stdout or ""
    tail = out[-2000:] if out else ""
    ok = proc.returncode == 0
    return ok, tail, out


def run_l3_subprocess(
    intent: str,
    *,
    capability_root: Path,
    skill_root: Path,
    topology: Optional[Path],
    resource: Optional[Path],
    out_dir: Path,
    pass_prior: Optional[List[str]] = None,
    scan_dir: Optional[Path] = None,
    ztp_lld: Optional[Path] = None,
    name_mapping: Optional[Path] = None,
    device_list: Optional[Path] = None,
    lld_design: Optional[Path] = None,
    location_004: Optional[Path] = None,
    timeout: int = 900,
) -> SubprocessResult:
    index = load_l3_index(capability_root)
    skill = index.get(intent)
    if skill is None:
        return SubprocessResult(
            status="error",
            output_files=(),
            summary=f"未在 l3_skill_index 中找到命令：{intent}",
            errors=(f"unknown intent: {intent}",),
        )
    if skill.unsupported or skill.pending:
        return SubprocessResult(
            status="error",
            output_files=(),
            summary=f"`{intent}` 标记为 pending/unsupported，无法执行。",
            errors=(skill.note or "unsupported",),
            sub_skill_name=skill.package,
        )
    if not skill.package or not skill.entrypoint:
        return SubprocessResult(
            status="error",
            output_files=(),
            summary=f"`{intent}` 缺少 package/entrypoint 配置。",
            errors=("missing package or entrypoint",),
        )

    package_dir = resolve_package_dir(capability_root, skill.package)
    package_name = package_dir.name
    entrypoint = (package_dir / skill.entrypoint).resolve()
    if not entrypoint.is_file():
        return SubprocessResult(
            status="error",
            output_files=(),
            summary=f"未找到 entrypoint：{entrypoint}",
            errors=(f"missing entrypoint: {entrypoint}",),
            sub_skill_name=package_name,
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    argv = build_argv(
        skill,
        intent,
        out_dir,
        topology=topology,
        resource=resource,
        pass_prior=pass_prior,
        scan_dir=scan_dir or out_dir.parent,
        ztp_lld=ztp_lld,
        name_mapping=name_mapping,
        device_list=device_list,
        lld_design=lld_design,
        location_004=location_004,
    )

    ok, tail, full_out = run_py(
        skill_root=skill_root,
        script_path=entrypoint,
        extra_args=argv,
        timeout=timeout,
    )
    outputs = _collect_outputs(out_dir)
    if not ok:
        err = tail.strip() or f"exit code != 0"
        return SubprocessResult(
            status="error",
            output_files=outputs,
            summary=f"`{intent}` 执行失败。",
            errors=(err,),
            sub_skill_name=package_name,
            stdout=full_out,
        )
    if not outputs:
        return SubprocessResult(
            status="error",
            output_files=(),
            summary=f"`{intent}` 执行完成但未发现产物。",
            errors=("empty output",),
            sub_skill_name=package_name,
            stdout=full_out,
        )
    return SubprocessResult(
        status="ok",
        output_files=outputs,
        summary=f"`{intent}` 完成，生成 {len(outputs)} 个产物。",
        sub_skill_name=package_name,
        stdout=full_out,
    )
