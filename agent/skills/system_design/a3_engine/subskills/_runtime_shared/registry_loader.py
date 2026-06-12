"""Load l3_skill_index.yaml from agent-skill_full1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml


@dataclass
class L3SkillDef:
    package: str = ""
    entrypoint: str = ""
    args_style: str = "connect_resource"
    default_sheet: Optional[str] = None
    default_network_plane: Optional[str] = None
    default_layer: Optional[str] = None
    lld_mode: Optional[str] = None
    pending: bool = False
    unsupported: bool = False
    requires_access_plan: bool = False
    naming_subcommand: Optional[str] = None
    note: Optional[str] = None


def l3_index_path(agent_skill_root: Path) -> Path:
    return (
        agent_skill_root
        / "lld-dispatch-orchestrator.code1"
        / "l3_skill_index.yaml"
    )


def load_l3_index(agent_skill_root: Path) -> Dict[str, L3SkillDef]:
    path = l3_index_path(agent_skill_root)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result: Dict[str, L3SkillDef] = {}
    for intent, item in (raw.get("skills") or {}).items():
        if not item:
            continue
        result[intent] = L3SkillDef(
            package=item.get("package", ""),
            entrypoint=item.get("entrypoint", ""),
            args_style=item.get("args_style", "connect_resource"),
            default_sheet=item.get("default_sheet"),
            default_network_plane=item.get("default_network_plane"),
            default_layer=item.get("default_layer"),
            lld_mode=item.get("lld_mode"),
            pending=bool(item.get("pending", False)),
            unsupported=bool(item.get("unsupported", False)),
            requires_access_plan=bool(item.get("requires_access_plan", False)),
            naming_subcommand=item.get("naming_subcommand"),
            note=item.get("note"),
        )
    return result


def resolve_package_dir(agent_skill_root: Path, package: str) -> Path:
    pkg = package.replace("\\", "/").lstrip("./")
    while pkg.startswith("../"):
        pkg = pkg[3:]
    return (agent_skill_root / pkg).resolve()
