# -*- coding: utf-8 -*-
"""Active input registry for skill-local uploaded files.

The first consumer is LLD: keep one active file with a stable path, archive the
previous active copy, and record enough metadata for future data-center wiring.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any


def _registry_path(skill_root: Path) -> Path:
    return skill_root / "ProjectData" / "input" / "input_registry.json"


def _load(skill_root: Path) -> dict[str, Any]:
    p = _registry_path(skill_root)
    if not p.is_file():
        return {"schemaVersion": 1, "slots": {}}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw.setdefault("schemaVersion", 1)
            raw.setdefault("slots", {})
            return raw
    except Exception:
        pass
    return {"schemaVersion": 1, "slots": {}}


def _save(skill_root: Path, data: dict[str, Any]) -> None:
    p = _registry_path(skill_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(skill_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(skill_root.resolve()).as_posix()
    except Exception:
        return str(path)


def _abs(skill_root: Path, path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return skill_root / p


def active_lld_path(skill_root: Path) -> Path:
    return skill_root / "ProjectData" / "input" / "plan_dispatch" / "active" / "LLD设计_latest.xlsx"


def get_active_file(skill_root: Path, slot_id: str) -> dict[str, Any]:
    data = _load(skill_root)
    slots = data.get("slots") if isinstance(data.get("slots"), dict) else {}
    slot = slots.get(slot_id) if isinstance(slots.get(slot_id), dict) else {}
    active = slot.get("active") if isinstance(slot.get("active"), dict) else {}
    path = str(active.get("path") or "").strip()
    if not path:
        return {}
    ap = _abs(skill_root, path)
    if not ap.is_file():
        return {}
    out = dict(active)
    out["absPath"] = str(ap)
    return out


def find_new_lld_candidate(skill_root: Path) -> Path | None:
    """Find a newly uploaded raw LLD outside active/archive.

    This is a compatibility bridge until uploads write through the registry
    directly. Existing active/archive files are ignored.
    """
    base = skill_root / "ProjectData" / "input" / "plan_dispatch"
    if not base.is_dir():
        return None
    active_dir = base / "active"
    archive_dir = base / "archive"
    candidates: list[Path] = []
    for pat in ("*LLD*设计*.xlsx", "*LLD设计*.xlsx", "*系统设计*LLD*.xlsx", "*LLD*.xlsx", "lld/*LLD*设计*.xlsx"):
        for p in base.glob(pat):
            if not p.is_file():
                continue
            try:
                rp = p.resolve()
                if active_dir in rp.parents or archive_dir in rp.parents:
                    continue
            except Exception:
                pass
            low = p.name.lower()
            if "cloudops" in low or "task_params" in low or "完工清单" in p.name:
                continue
            candidates.append(p)
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: (x.stat().st_mtime, x.name), reverse=True)[0]


def promote_lld(skill_root: Path, source_path: str | Path, *, source: str = "local_upload") -> dict[str, Any]:
    """Make source_path the active LLD and archive the previous active file."""
    root = skill_root.resolve()
    src = Path(source_path).resolve()
    if not src.is_file():
        return {"changed": False, "reason": "source_missing", "sourcePath": str(src)}

    active_path = active_lld_path(root)
    active_path.parent.mkdir(parents=True, exist_ok=True)
    archive_dir = active_path.parent.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    new_hash = _sha256(src)
    data = _load(root)
    slots = data.setdefault("slots", {})
    slot = slots.setdefault("lld_design", {})
    history = slot.setdefault("history", [])
    if not isinstance(history, list):
        history = []
        slot["history"] = history
    old_active = slot.get("active") if isinstance(slot.get("active"), dict) else {}
    old_hash = str(old_active.get("sha256") or "")

    if active_path.is_file() and old_hash == new_hash and src.resolve() == active_path.resolve():
        return {"changed": False, "active": old_active, "reason": "same_active"}

    version = int(old_active.get("version") or 0) + 1
    archived_path = ""
    if active_path.is_file():
        old_original = str(old_active.get("originalName") or active_path.name)
        safe_original = old_original.replace("\\", "_").replace("/", "_")
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        dst = archive_dir / f"v{version - 1:03d}_{stamp}_{safe_original}"
        shutil.move(str(active_path), str(dst))
        archived_path = _rel(root, dst)
        old_record = dict(old_active)
        old_record["path"] = archived_path
        old_record["archivedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        history.append(old_record)

    if src.resolve() == active_path.resolve():
        # The file is already in the active location but registry was stale.
        pass
    else:
        shutil.move(str(src), str(active_path))

    active = {
        "path": _rel(root, active_path),
        "originalName": src.name,
        "version": version,
        "sha256": new_hash,
        "source": source,
        "uploadedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    slot["active"] = active
    _save(root, data)
    return {"changed": True, "active": active, "archivedPath": archived_path}


def promote_new_lld_if_present(skill_root: Path) -> dict[str, Any]:
    candidate = find_new_lld_candidate(skill_root)
    if not candidate:
        active = get_active_file(skill_root, "lld_design")
        return {"changed": False, "active": active, "reason": "no_new_candidate"}
    active = get_active_file(skill_root, "lld_design")
    if active:
        active_path = Path(str(active.get("absPath") or ""))
        try:
            # Avoid rolling back to older raw files left in the inbox before the
            # active/archive convention was introduced.
            if active_path.is_file() and candidate.stat().st_mtime <= active_path.stat().st_mtime:
                return {"changed": False, "active": active, "reason": "candidate_not_newer_than_active"}
        except Exception:
            pass
        try:
            if _sha256(candidate) == str(active.get("sha256") or ""):
                return {"changed": False, "active": active, "reason": "same_hash_candidate"}
        except Exception:
            pass
    return promote_lld(skill_root, candidate)
