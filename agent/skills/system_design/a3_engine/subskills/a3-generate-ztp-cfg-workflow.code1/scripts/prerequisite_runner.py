"""缺失输入时检查并静默运行前置 skill（系统临时目录，不保留 _prereq_output）。"""

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

from ztp_cfg_inputs import (
    LABELS,
    RESOURCE_NAME_KEYWORD,
    ZTP_LLD_OUTPUT_NAMES,
    find_resource,
    find_ztp_lld,
)


@dataclass
class PrereqSession:
    _dirs: list[Path] = field(default_factory=list)

    def new_output_dir(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="ztp_prereq_"))
        self._dirs.append(path)
        return path

    def cleanup(self) -> None:
        for path in self._dirs:
            shutil.rmtree(path, ignore_errors=True)
        self._dirs.clear()


@dataclass(frozen=True)
class PrerequisiteSkill:
    key: str
    skill_dir: Path
    entrypoint: Path
    output_names: tuple[str, ...]


def staging_root_from_skill(skill_root: Path) -> Path:
    return skill_root.parent


def parse_entrypoint(skill_md: Path) -> str | None:
    text = skill_md.read_text(encoding="utf-8")
    match = re.search(r"entrypoint:\s*(\S+)", text)
    return match.group(1).strip() if match else None


def find_latest_output(search_roots: list[Path], output_names: tuple[str, ...]) -> Path | None:
    candidates: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for name in output_names:
            candidates.extend(root.rglob(name))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def find_latest_resource(staging_root: Path) -> Path | None:
    candidates: list[Path] = []
    for path in staging_root.rglob("*.xlsx"):
        if path.name.startswith("~$"):
            continue
        if RESOURCE_NAME_KEYWORD in path.name:
            candidates.append(path)
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
            PrerequisiteSkill(
                key="ztp_lld",
                skill_dir=skill_dir,
                entrypoint=entry,
                output_names=ZTP_LLD_OUTPUT_NAMES,
            )
        )
    if not found:
        return None
    return next((s for s in found if prefer in s.skill_dir.name), found[0])


def run_prerequisite_skill(skill: PrerequisiteSkill, work_cwd: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
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
            f"前置 skill 运行失败: {skill.skill_dir.name}\n"
            f"命令: {' '.join(cmd)}\n"
            f"stderr:\n{result.stderr}"
        )
    produced = find_latest_output([out_dir], skill.output_names)
    if produced is None:
        raise FileNotFoundError(f"前置 skill 未产出 {skill.output_names}，目录: {out_dir}")
    return produced.resolve()


def ensure_ztp_lld(
    scan_dir: Path,
    staging_root: Path,
    session: PrereqSession,
    *,
    allow_run: bool,
) -> Path:
    existing = find_ztp_lld(scan_dir)
    if existing is not None:
        return existing.resolve()

    fallback = find_latest_output([staging_root], ZTP_LLD_OUTPUT_NAMES)

    if not allow_run:
        if fallback is not None:
            return fallback.resolve()
        raise FileNotFoundError(f"未找到必要输入件：{LABELS['ztp_lld']}")

    skill = discover_ztp_lld_skill(staging_root)
    if skill is None:
        if fallback is not None:
            return fallback.resolve()
        raise FileNotFoundError(f"未找到可生成 ZTP_LLD 的前置 skill：{LABELS['ztp_lld']}")

    out_dir = session.new_output_dir()
    try:
        return run_prerequisite_skill(skill, work_cwd=scan_dir, out_dir=out_dir)
    except (RuntimeError, FileNotFoundError):
        if fallback is not None:
            return fallback.resolve()
        raise


def ensure_resource(
    scan_dir: Path,
    staging_root: Path,
    *,
    allow_run: bool,
) -> Path:
    existing = find_resource(scan_dir)
    if existing is not None:
        return existing.resolve()

    fallback = find_latest_resource(staging_root)
    if fallback is not None:
        return fallback.resolve()

    if not allow_run:
        raise FileNotFoundError(f"未找到必要输入件：{LABELS['resource']}")

    raise FileNotFoundError(
        f"未找到必要输入件：{LABELS['resource']}。"
        "项目信息收集表需手动放置（无自动生成 skill）；"
        "请放入当前目录或 _skill_staging 下其它 skill 目录。"
    )


def resolve_all_inputs(
    scan_dir: Path,
    skill_root: Path,
    session: PrereqSession,
    *,
    allow_auto_prereq: bool = True,
) -> tuple[Path, Path]:
    staging = staging_root_from_skill(skill_root)
    allow = allow_auto_prereq
    ztp_lld = ensure_ztp_lld(scan_dir, staging, session, allow_run=allow)
    resource = ensure_resource(scan_dir, staging, allow_run=allow)
    return ztp_lld, resource


@contextmanager
def resolved_inputs(
    scan_dir: Path,
    skill_root: Path,
    *,
    allow_auto_prereq: bool = True,
) -> Iterator[tuple[Path, Path]]:
    session = PrereqSession()
    try:
        yield resolve_all_inputs(
            scan_dir, skill_root, session, allow_auto_prereq=allow_auto_prereq
        )
    finally:
        session.cleanup()
