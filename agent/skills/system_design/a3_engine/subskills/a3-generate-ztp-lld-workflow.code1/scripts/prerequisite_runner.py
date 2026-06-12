"""缺失规划表时，在 _skill_staging 中定位并静默运行前置 skill（临时目录，不落地 _prereq_output）。"""

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

PREREQUISITE_OUTPUTS: dict[str, list[str]] = {
    "cpm": ["超平面网络规划.xlsx", "A3超平面网络规划.xlsx"],
    "manage": ["A3灵衢带外管理地址规划.xlsx"],
}


@dataclass
class PrereqSession:
    """持有前置 skill 临时输出目录，在会话结束后统一删除。"""

    _dirs: list[Path] = field(default_factory=list)

    def new_output_dir(self, base: Path | None = None) -> Path:
        # 前置子 skill（lq-dw-manage / cpm-lq）带 restrict_to_cwd 守卫：--out-dir 必须落在
        # 运行 cwd（=scan_dir）之下，否则 SystemExit。故临时输出目录建在 base（scan_dir）下，
        # 而非系统临时目录；会话结束统一删除。base 为空时回退系统临时目录（向后兼容）。
        if base is not None:
            base.mkdir(parents=True, exist_ok=True)
            path = Path(tempfile.mkdtemp(prefix="_ztp_prereq_", dir=str(base)))
        else:
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


def _skill_matches(key: str, skill_md_text: str) -> bool:
    if key == "cpm":
        return "超平面" in skill_md_text and "LoopBack" in skill_md_text
    if key == "manage":
        return "灵衢带外管理" in skill_md_text and "地址规划" in skill_md_text
    return False


def discover_prerequisite_skills(staging_root: Path, key: str) -> list[PrerequisiteSkill]:
    skills: list[PrerequisiteSkill] = []
    output_names = tuple(PREREQUISITE_OUTPUTS.get(key, ()))

    for skill_dir in sorted(staging_root.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8")
        if not _skill_matches(key, text):
            continue
        entry_rel = parse_entrypoint(skill_md)
        if not entry_rel:
            continue
        entry = skill_dir / entry_rel
        if not entry.is_file():
            continue
        skills.append(
            PrerequisiteSkill(
                key=key,
                skill_dir=skill_dir,
                entrypoint=entry,
                output_names=output_names,
            )
        )
    return skills


def find_latest_output(
    search_roots: list[Path],
    output_names: tuple[str, ...],
) -> Path | None:
    candidates: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for name in output_names:
            candidates.extend(root.rglob(name))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run_prerequisite_skill(
    skill: PrerequisiteSkill,
    work_cwd: Path,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(skill.entrypoint.resolve()), "--out-dir", str(out_dir.resolve())]
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
        raise FileNotFoundError(
            f"前置 skill 已执行但未找到输出文件 {skill.output_names}，目录: {out_dir}"
        )
    return produced.resolve()


def ensure_prerequisite_file(
    key: str,
    scan_dir: Path,
    staging_root: Path,
    session: PrereqSession,
    *,
    allow_run: bool = True,
) -> Path | None:
    from ztp_lld_inputs import find_excel

    existing = find_excel(key, scan_dir)
    if existing is not None:
        return existing.resolve()

    if not allow_run:
        return None

    skills = discover_prerequisite_skills(staging_root, key)
    if not skills:
        return None

    prefer = {
        "cpm": "a3-cpm-lq-ip-workflow",
        "manage": "a3-lq-dw-manage-ip-workflow",
    }
    prefix = prefer.get(key, "")
    skill = next((s for s in skills if prefix in s.skill_dir.name), skills[0])

    # 输出目录建在 scan_dir 下，满足子 skill 的 restrict_to_cwd 守卫（见 new_output_dir）。
    out_dir = session.new_output_dir(base=scan_dir)
    # 子 skill 失败时不再回退到 staging_root 里的任意旧产物：那会把别的项目/旧 run 的
    # 陈旧规划表（设备命名与当前数据不一致）静默喂给 ZTP，导致 LoopBack 全 nan、报错难定位。
    # 直接抛出真实错误（如「缺少 灵衢带外管理面端口互联 sheet」），由上层清晰反馈。
    return run_prerequisite_skill(skill, work_cwd=scan_dir, out_dir=out_dir)


def resolve_all_inputs(
    scan_dir: Path,
    skill_root: Path,
    session: PrereqSession,
    *,
    allow_auto_prereq: bool = True,
) -> dict[str, Path]:
    from ztp_lld_inputs import LABELS, SCAN_RULES, find_excel

    staging = staging_root_from_skill(skill_root)
    paths: dict[str, Path] = {}
    missing_labels: list[str] = []

    for key in SCAN_RULES:
        if key == "location":
            path = find_excel(key, scan_dir)
            if path is None:
                missing_labels.append(LABELS[key])
            else:
                paths[key] = path.resolve()
            continue

        path = ensure_prerequisite_file(
            key,
            scan_dir,
            staging,
            session,
            allow_run=allow_auto_prereq,
        )
        if path is None:
            missing_labels.append(LABELS[key])
        else:
            paths[key] = path

    if missing_labels:
        hint = ""
        if allow_auto_prereq:
            hint = (
                "（已尝试在 _skill_staging 运行相关 skill；请确认目录含 007 与项目信息收集表）"
            )
        raise FileNotFoundError(f"未找到必要输入件：{', '.join(missing_labels)}{hint}")

    return paths


@contextmanager
def resolved_inputs(
    scan_dir: Path,
    skill_root: Path,
    *,
    allow_auto_prereq: bool = True,
) -> Iterator[dict[str, Path]]:
    """解析输入；退出上下文时删除前置 skill 临时输出。"""
    session = PrereqSession()
    try:
        yield resolve_all_inputs(
            scan_dir, skill_root, session, allow_auto_prereq=allow_auto_prereq
        )
    finally:
        session.cleanup()
