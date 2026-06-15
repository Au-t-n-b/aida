from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_capability_root(start: Path | None = None) -> Path:
    """Return directory containing workflow packages (subskills/ preferred)."""
    skill_root = start or Path(__file__).resolve().parent.parent
    subskills = skill_root / "subskills"
    index = subskills / "lld-dispatch-orchestrator.code1" / "l3_skill_index.yaml"
    if index.is_file():
        return subskills.resolve()

    env_root = os.environ.get("A3_AGENT_SKILL_ROOT") or os.environ.get("AGENT_SKILL_ROOT")
    if env_root:
        p = Path(env_root).expanduser()
        candidate = p if p.name in {"agent-skill_full1", "subskills"} else p / "agent-skill_full1"
        if (candidate / "lld-dispatch-orchestrator.code1" / "l3_skill_index.yaml").is_file():
            return candidate.resolve()

    anchor = skill_root.resolve()
    for parent in [anchor, *anchor.parents]:
        nested = parent / "agent-skill_full1"
        if (nested / "lld-dispatch-orchestrator.code1" / "l3_skill_index.yaml").is_file():
            return nested.resolve()

    raise FileNotFoundError(
        "未找到业务能力库；请先运行 scripts/copy_subskills.py，或设置 AGENT_SKILL_ROOT"
    )


def resolve_agent_skill_root(start: Path | None = None) -> Path:
    """Backward-compatible alias."""
    return resolve_capability_root(start)


def ensure_runtime_importable(capability_root: Path) -> None:
    """Insert capability root for dispatch/conductor planning imports."""
    root = str(capability_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
