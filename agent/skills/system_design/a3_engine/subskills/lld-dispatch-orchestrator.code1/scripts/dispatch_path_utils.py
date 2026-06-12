"""Path resolution, CWD contract, run directory layout."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

SKILL_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SKILL_ROOT.parent
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
            f"ERROR: {label} must be under cwd, skill root, or agent-skill_full1.\n"
            f"  path: {resolved}\n  cwd:  {cwd.resolve()}"
        )
    return resolved


def new_run_dir(out_dir: Path, run_id: Optional[str] = None) -> Path:
    rid = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = out_dir / f"run_{rid}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def yaml_path(name: str) -> Path:
    return SKILL_ROOT / name
