"""Staging helpers: plane_key extraction, scan latest A3*.xlsx, collect from child outputs."""

from __future__ import annotations

import fnmatch
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from lld_config import (
    INTEGRATE_EXCLUDE_FILENAMES,
    INTEGRATE_EXCLUDE_PLANE_KEYS,
    INTEGRATE_PLANE_FILENAME_ALIASES,
)


def extract_plane_key(filename: str) -> Optional[str]:
    name = Path(filename).name
    if name.startswith("~$") or not name.lower().endswith(".xlsx"):
        return None
    alias = INTEGRATE_PLANE_FILENAME_ALIASES.get(name)
    if alias:
        if alias in INTEGRATE_EXCLUDE_PLANE_KEYS or name in INTEGRATE_EXCLUDE_FILENAMES:
            return None
        return alias
    idx = name.find("A3")
    if idx < 0:
        return None
    core = name[idx:-5]
    if core in INTEGRATE_EXCLUDE_PLANE_KEYS or name in INTEGRATE_EXCLUDE_FILENAMES:
        return None
    return core


def is_integrate_candidate(path: Path) -> bool:
    if path.name.startswith("~$"):
        return False
    if path.name in INTEGRATE_EXCLUDE_FILENAMES:
        return False
    return extract_plane_key(path.name) is not None


def scan_latest_by_plane(dirs: Sequence[Path]) -> Dict[str, Path]:
    latest: Dict[str, tuple[float, Path]] = {}
    for directory in dirs:
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.xlsx"):
            if not is_integrate_candidate(path):
                continue
            key = extract_plane_key(path.name)
            if not key:
                continue
            mtime = path.stat().st_mtime
            prev = latest.get(key)
            if prev is None or mtime > prev[0]:
                latest[key] = (mtime, path)
    return {k: v[1] for k, v in latest.items()}


def render_pattern(pattern: str, ctx: dict) -> str:
    out = pattern
    for key, val in ctx.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def glob_match(name: str, pattern: str) -> bool:
    return fnmatch.fnmatch(name, pattern)


@dataclass
class CollectResult:
    copied: List[str]
    missing: List[str]


def collect_step_outputs(
    staging_dir: Path,
    source_dir: Path,
    outputs: Sequence[dict],
    ctx: dict,
    strict: bool = False,
) -> CollectResult:
    staging_dir.mkdir(parents=True, exist_ok=True)
    copied: List[str] = []
    missing: List[str] = []

    for spec in outputs:
        pattern = render_pattern(spec.get("pattern", ""), ctx)
        source_glob = spec.get("source_glob", "")
        matches = list(source_dir.glob(source_glob)) if source_glob else []
        if not matches and source_glob:
            missing.append(source_glob)
            continue
        if matches:
            src = max(matches, key=lambda p: p.stat().st_mtime)
        elif source_dir.is_file():
            src = source_dir
        else:
            missing.append(source_glob or pattern)
            continue
        dest_name = Path(pattern).name if pattern else src.name
        dest = staging_dir / dest_name
        shutil.copy2(src, dest)
        copied.append(str(dest))

    if strict and missing:
        raise FileNotFoundError(f"collect missing outputs: {missing}")
    return CollectResult(copied=copied, missing=missing)


def load_manifest(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"steps": {}}


def save_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def update_manifest_step(
    manifest_path: Path,
    step_id: str,
    status: str,
    extra: Optional[dict] = None,
) -> dict:
    manifest = load_manifest(manifest_path)
    steps = manifest.setdefault("steps", {})
    entry = steps.setdefault(step_id, {})
    entry["status"] = status
    if extra:
        entry.update(extra)
    save_manifest(manifest_path, manifest)
    return manifest
