"""Load dispatch_tree.yaml and skill_registry.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

from dispatch_path_utils import yaml_path


@dataclass
class L2Policy:
    secondary_intent: str
    strategy: str
    execution: str = "serial"
    pass_prior: List[str] = field(default_factory=list)
    third_intent: Optional[str] = None
    child_skill: Optional[dict] = None
    conductor: Optional[dict] = None
    note: Optional[str] = None


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


@dataclass
class DispatchTree:
    l1_to_l2: Dict[str, List[str]]
    l2_children: Dict[str, List[str]]
    l2_order_under_l1: Dict[str, List[str]]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_dispatch_tree() -> DispatchTree:
    raw = _load_yaml(yaml_path("dispatch_tree.yaml"))
    tree = raw.get("tree") or {}
    l1_to_l2: Dict[str, List[str]] = {}
    l2_children: Dict[str, List[str]] = {}
    l2_order_under_l1: Dict[str, List[str]] = {}

    for l1, l2_map in tree.items():
        if not isinstance(l2_map, dict):
            continue
        order: List[str] = []
        for l2, children in l2_map.items():
            order.append(l2)
            if children is None:
                child_list: List[str] = []
            elif isinstance(children, list):
                child_list = list(children)
            else:
                child_list = []
            l2_children[l2] = child_list
        l1_to_l2[l1] = order
        l2_order_under_l1[l1] = order

    return DispatchTree(l1_to_l2=l1_to_l2, l2_children=l2_children, l2_order_under_l1=l2_order_under_l1)


def load_l2_policies() -> Dict[str, L2Policy]:
    raw = _load_yaml(yaml_path("skill_registry.yaml"))
    result: Dict[str, L2Policy] = {}
    for item in raw.get("l2_policies") or []:
        pol = L2Policy(
            secondary_intent=item["secondary_intent"],
            strategy=item["strategy"],
            execution=item.get("execution", "serial"),
            pass_prior=list(item.get("pass_prior") or []),
            third_intent=item.get("third_intent"),
            child_skill=item.get("child_skill"),
            conductor=item.get("conductor"),
            note=item.get("note"),
        )
        result[pol.secondary_intent] = pol
    return result


def load_l2_without_offline() -> Set[str]:
    raw = _load_yaml(yaml_path("skill_registry.yaml"))
    return set(raw.get("l2_without_offline") or [])


def load_l3_index() -> Dict[str, L3SkillDef]:
    raw = _load_yaml(yaml_path("l3_skill_index.yaml"))
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
