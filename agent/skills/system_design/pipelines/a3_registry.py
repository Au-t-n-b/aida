"""A3 命令注册表 · 读取 l3_skill_index.yaml + dispatch_tree.yaml（不复制 YAML，直接读 A3 工程）。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .a3_paths import get_subskills_root


@dataclass
class L3SkillDef:
    package: str = ""
    entrypoint: str = ""
    args_style: str = "connect_resource"
    default_sheet: str | None = None
    default_network_plane: str | None = None
    default_layer: str | None = None
    lld_mode: str | None = None
    pending: bool = False
    unsupported: bool = False
    requires_access_plan: bool = False
    naming_subcommand: str | None = None
    note: str | None = None


def _orchestrator_dir() -> Path:
    return get_subskills_root() / "lld-dispatch-orchestrator.code1"


def l3_index_path() -> Path:
    return _orchestrator_dir() / "l3_skill_index.yaml"


def dispatch_tree_path() -> Path:
    return _orchestrator_dir() / "dispatch_tree.yaml"


def load_l3_index() -> dict[str, L3SkillDef]:
    path = l3_index_path()
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result: dict[str, L3SkillDef] = {}
    for intent, item in (raw.get("skills") or {}).items():
        if not item:
            continue
        result[str(intent)] = L3SkillDef(
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


def resolve_package_dir(package: str) -> Path:
    pkg = package.replace("\\", "/").lstrip("./")
    while pkg.startswith("../"):
        pkg = pkg[3:]
    return (get_subskills_root() / pkg).resolve()


def load_dispatch_tree() -> dict[str, Any]:
    path = dispatch_tree_path()
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("tree") or {}


def _flatten_leaves(node: Any, out: list[str]) -> None:
    if isinstance(node, list):
        for item in node:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return
    if isinstance(node, dict):
        for v in node.values():
            _flatten_leaves(v, out)


def expand_dispatch(l1_command: str) -> list[str]:
    """展开 L1 批次命令为三级叶子命令列表（如 地址规划 → 全部地址 L3）。"""
    tree = load_dispatch_tree()
    node = tree.get(l1_command)
    if node is None:
        return []
    leaves: list[str] = []
    _flatten_leaves(node, leaves)
    # 去重保序
    seen: set[str] = set()
    ordered: list[str] = []
    for cmd in leaves:
        if cmd not in seen:
            seen.add(cmd)
            ordered.append(cmd)
    return ordered


def list_integrated_commands() -> list[str]:
    """l3_skill_index 中可执行的命令（非 unsupported/pending）。"""
    index = load_l3_index()
    return [
        k for k, v in index.items()
        if v.package and v.entrypoint and not v.unsupported and not v.pending
    ]
