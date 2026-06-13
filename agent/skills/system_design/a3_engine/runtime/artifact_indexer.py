from __future__ import annotations

from pathlib import Path
from typing import Any


KIND_BY_SUFFIX = {
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".docx": "docx",
    ".doc": "docx",
    ".pdf": "pdf",
    ".json": "json",
    ".zip": "zip",
    ".md": "other",
    ".txt": "other",
    ".csv": "other",
}


def artifact_kind(path: Path) -> str:
    return KIND_BY_SUFFIX.get(path.suffix.lower(), "other")


def workspace_path(skill_root: Path, path: Path) -> str:
    try:
        rel = path.resolve().relative_to(skill_root.resolve())
        return f"workspace/skills/a3-intelligent-network-opening/{rel.as_posix()}"
    except Exception:
        return str(path)


def collect_artifacts(
    *,
    skill_root: Path,
    output_dir: Path,
    command: str,
    sub_skill_name: str,
) -> list[dict[str, Any]]:
    if not output_dir.is_dir():
        return []

    artifacts: list[dict[str, Any]] = []
    for index, path in enumerate(sorted(p for p in output_dir.rglob("*") if p.is_file())):
        if path.name.lower() in {"stdout.txt", "stderr.txt", "run_request.json"}:
            continue
        artifacts.append(
            {
                "artifactId": f"{sub_skill_name}:{index}:{path.stem}",
                "label": path.name,
                "path": workspace_path(skill_root, path),
                "kind": artifact_kind(path),
                "status": "ready",
                "sourceSkill": sub_skill_name,
                "command": command,
            }
        )
    return artifacts


def collect_artifacts_from_files(
    *,
    skill_root: Path,
    files: tuple[Path, ...] | list[Path],
    command: str,
    sub_skill_name: str,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for index, path in enumerate(sorted(files), start=1):
        if not path.is_file():
            continue
        artifacts.append(
            {
                "artifactId": f"{sub_skill_name}:{index}:{path.stem}",
                "label": path.name,
                "path": workspace_path(skill_root, path),
                "kind": artifact_kind(path),
                "status": "ready",
                "sourceSkill": sub_skill_name,
                "command": command,
            }
        )
    return artifacts
