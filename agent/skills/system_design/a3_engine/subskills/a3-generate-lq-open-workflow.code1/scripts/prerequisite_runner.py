"""缺失输入时静默运行前置 skill（临时目录，不落地 _prereq_output）。"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ztp_lq_open_inputs import (
    LABELS,
    RESOURCE_KEYWORD,
    ZTP_LLD_OUTPUT_NAMES,
    find_resource,
    find_ztp_lld,
)


@dataclass
class PrereqSession:
    _dirs: list[Path] = field(default_factory=list)

    def new_output_dir(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="lq_open_prereq_"))
        self._dirs.append(path)
        return path

    def cleanup(self) -> None:
        for path in self._dirs:
            shutil.rmtree(path, ignore_errors=True)
        self._dirs.clear()


@dataclass(frozen=True)
class PrerequisiteSkill:
    skill_dir: Path
    entrypoint: Path
    output_names: tuple[str, ...]


def staging_root_from_skill(skill_root: Path) -> Path:
    return skill_root.parent


def parse_entrypoint(skill_md: Path) -> str | None:
    text = skill_md.read_text(encoding="utf-8")
    match = re.search(r"entrypoint:\s*(\S+)", text)
    return match.group(1).strip() if match else None


def find_latest_output(roots: list[Path], names: tuple[str, ...]) -> Path | None:
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for name in names:
            candidates.extend(root.rglob(name))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def find_latest_resource(staging_root: Path) -> Path | None:
    candidates = [
        p
        for p in staging_root.rglob("*.xlsx")
        if not p.name.startswith("~$") and RESOURCE_KEYWORD in p.name
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def discover_ztp_lld_skill(staging_root: Path) -> PrerequisiteSkill | None:
    prefer = "a3-generate-ztp-lld-workflow"
    found: list[PrerequisiteSkill] = []
    for skill_dir in sorted(staging_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8")
        if "generate-ztp-lld" not in text and "generate_ztp_lld_file" not in text:
            if not ("ZTP" in text and "设计文件" in text):
                continue
        entry_rel = parse_entrypoint(skill_md)
        if not entry_rel:
            continue
        entry = skill_dir / entry_rel
        if not entry.is_file():
            continue
        found.append(
            PrerequisiteSkill(entrypoint=entry, skill_dir=skill_dir, output_names=ZTP_LLD_OUTPUT_NAMES)
        )
    if not found:
        return None
    return next((s for s in found if prefer in s.skill_dir.name), found[0])


def run_skill(skill: PrerequisiteSkill, work_cwd: Path, out_dir: Path) -> Path:
    cmd = [
        sys.executable,
        str(skill.entrypoint.resolve()),
        "--scan-dir",
        str(work_cwd.resolve()),
        "--out-dir",
        str(out_dir.resolve()),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(work_cwd.resolve()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"前置 skill 失败: {skill.skill_dir.name}\nstderr:\n{result.stderr}"
        )
    produced = find_latest_output([out_dir], skill.output_names)
    if produced is None:
        raise FileNotFoundError(f"未找到产出 {skill.output_names}")
    return produced.resolve()


def ensure_ztp_lld(scan_dir: Path, staging: Path, session: PrereqSession, *, allow_run: bool) -> Path:
    hit = find_ztp_lld(scan_dir)
    if hit:
        return hit.resolve()
    fallback = find_latest_output([staging], ZTP_LLD_OUTPUT_NAMES)
    if not allow_run:
        if fallback:
            return fallback.resolve()
        raise FileNotFoundError(LABELS["ztp_lld"])
    skill = discover_ztp_lld_skill(staging)
    if skill is None:
        if fallback:
            return fallback.resolve()
        raise FileNotFoundError(LABELS["ztp_lld"])
    try:
        return run_skill(skill, scan_dir, session.new_output_dir())
    except (RuntimeError, FileNotFoundError):
        if fallback:
            return fallback.resolve()
        raise


def ensure_resource(scan_dir: Path, staging: Path, *, allow_run: bool) -> Path:
    hit = find_resource(scan_dir)
    if hit:
        return hit.resolve()
    fallback = find_latest_resource(staging)
    if fallback:
        return fallback.resolve()
    raise FileNotFoundError(
        f"{LABELS['resource']}（需手动放置，无自动生成 skill）"
    )


@contextmanager
def resolved_inputs(
    scan_dir: Path,
    skill_root: Path,
    *,
    allow_auto_prereq: bool = True,
) -> Iterator[tuple[Path, Path]]:
    session = PrereqSession()
    staging = staging_root_from_skill(skill_root)
    try:
        ztp_lld = ensure_ztp_lld(scan_dir, staging, session, allow_run=allow_auto_prereq)
        resource = ensure_resource(scan_dir, staging, allow_run=allow_auto_prereq)
        yield ztp_lld, resource
    finally:
        session.cleanup()
