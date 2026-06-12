from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class SkillJobRequest:
    intent: str
    inputs: dict[str, Path]
    out_dir: Path
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillJobResult:
    status: Literal["ok", "error"]
    output_files: tuple[Path, ...]
    summary: str
    errors: tuple[str, ...] = ()
    sub_skill_name: str = ""
    stdout: str = ""
    stderr: str = ""
