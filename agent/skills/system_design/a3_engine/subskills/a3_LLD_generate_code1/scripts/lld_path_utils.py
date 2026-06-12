"""Path resolution, CWD contract, autodetect, run directory layout."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

SKILL_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SKILL_ROOT.parent  # LLD_IP
DEFAULT_OUT_DIR = SKILL_ROOT / "output"


def _allowed_roots(cwd: Path) -> List[Path]:
    return [cwd.resolve(), SKILL_ROOT.resolve(), PACKAGE_ROOT.resolve()]


def _is_under_any(path: Path, roots: Sequence[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def resolve_local(path: Path | str, cwd: Optional[Path] = None) -> Path:
    p = Path(path)
    base = (cwd or Path.cwd()).resolve()
    return p.resolve() if p.is_absolute() else (base / p).resolve()


def require_under_cwd(path: Path, cwd: Path, label: str) -> Path:
    resolved = resolve_local(path, cwd)
    roots = _allowed_roots(cwd)
    if not _is_under_any(resolved, roots):
        raise SystemExit(
            f"ERROR: {label} must be under cwd, skill root, or LLD_IP package.\n"
            f"  path: {resolved}\n  cwd:  {cwd.resolve()}"
        )
    return resolved


def list_excel_in_tree(root: Path) -> List[Path]:
    files: List[Path] = []
    if not root.exists():
        return files
    for ext in (".xlsx", ".xls"):
        files.extend(root.rglob(f"*{ext}"))
    uniq: List[Path] = []
    seen = set()
    for p in sorted(files):
        if p.name.startswith("~$"):
            continue
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def autodetect_topology(cwd: Path) -> Optional[Path]:
    search_roots = _allowed_roots(cwd)
    seen_paths: List[Path] = []
    for root in search_roots:
        for p in list_excel_in_tree(root):
            if p.resolve() not in {x.resolve() for x in seen_paths}:
                seen_paths.append(p)
    candidates = [
        p
        for p in seen_paths
        if "007" in p.name or "端口连线" in p.name or "端口互联" in p.name
    ]
    if not candidates:
        return None
    if len(candidates) > 1:
        names = "\n".join(f"  - {c}" for c in candidates[:10])
        raise SystemExit(f"ERROR: multiple topology files found under cwd; specify --topology:\n{names}")
    return candidates[0]


def autodetect_resource(cwd: Path) -> Optional[Path]:
    search_roots = _allowed_roots(cwd)
    seen_paths: List[Path] = []
    for root in search_roots:
        for p in list_excel_in_tree(root):
            if p.resolve() not in {x.resolve() for x in seen_paths}:
                seen_paths.append(p)
    candidates = [
        p
        for p in seen_paths
        if "项目信息收集" in p.name or ("资源" in p.name and "007" not in p.name)
    ]
    if not candidates:
        return None
    if len(candidates) > 1:
        names = "\n".join(f"  - {c}" for c in candidates[:10])
        raise SystemExit(f"ERROR: multiple resource files found under cwd; specify --resource:\n{names}")
    return candidates[0]


def new_run_dir(out_dir: Path, run_id: Optional[str] = None) -> Path:
    """Plan metadata dir only (workflow_plan.json). No step_out / staging subdirs."""
    rid = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = out_dir / f"run_{rid}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def default_lld_output_path(out_dir: Path, project_name: str) -> Path:
    """Final LLD workbook path directly under out-dir."""
    ts = datetime.now().strftime("%Y%m%d%H%M")
    safe_name = sanitize_project_name(project_name)
    return out_dir / f"{safe_name}-LLD设计-{ts}.xlsx"


def find_run_dir(out_dir: Path, run_id: str) -> Path:
    if run_id.startswith("run_"):
        candidate = out_dir / run_id
    else:
        candidate = out_dir / f"run_{run_id}"
    if not candidate.is_dir():
        raise SystemExit(f"ERROR: run directory not found: {candidate}")
    return candidate


def sanitize_project_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name.strip())
    return cleaned or "LLD项目"


def workflow_yaml_path() -> Path:
    return SKILL_ROOT / "workflow.yaml"
