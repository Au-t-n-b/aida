from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml

from skill_root import resolve_capability_root
from registry_loader import load_l3_index, resolve_package_dir
from input_checker import BASE_REQUIRED_INPUTS


@dataclass(frozen=True)
class CommandSpec:
    command: str
    category: str
    support_status: str
    adapter: str | None
    sub_skill: str | None
    required_inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    b2_group: str
    args_style: str = ""
    conductor_mode: str = ""
    can_run_in_one_click: bool = False


def _b2_group(intent: str) -> str:
    if any(x in intent for x in ("存储",)):
        return "存储面"
    if any(x in intent for x in ("网络", "SPINE", "防火墙")) and "带外" not in intent:
        return "网络面"
    if intent in {"NCE规划", "DME规划", "CCAE规划"}:
        return intent.replace("规划", "")
    if any(x in intent for x in ("MLAG", "ASN", "ZTP", "灵衢", "LLD", "设备清单", "替换设备")):
        return "SPINE/MLAG/ASN"
    if any(x in intent for x in ("灵衢", "管存")):
        return "管理面"
    return "计算面"


def _category(intent: str, args_style: str) -> str:
    if args_style == "input_check" or intent in {"检查输入件是否妥当", "查询输入件"}:
        return "input_check"
    if "接入" in intent:
        return "access"
    if "互联" in intent:
        return "interconnect"
    if intent in {"生成完整LLD设计", "融合完整LLD设计"}:
        return "lld"
    if args_style in {"ztp_scan", "lq_open_scan", "device_naming"}:
        return "file_gen"
    if args_style == "planner" or intent in {"NCE规划", "DME规划", "CCAE规划", "交换机MLAG规划"}:
        return "mgmt"
    return "address"


def _load_dispatch_l1(capability_root: Path) -> list[str]:
    path = capability_root / "lld-dispatch-orchestrator.code1" / "dispatch_tree.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list((raw.get("tree") or {}).keys())


def build_command_registry(skill_root: Path | None = None) -> Dict[str, CommandSpec]:
    start = skill_root or Path(__file__).resolve().parent.parent
    capability_root = resolve_capability_root(start)

    specs: Dict[str, CommandSpec] = {}

    for intent, skill in load_l3_index(capability_root).items():
        if skill.unsupported:
            continue
        if skill.pending or not skill.package:
            specs[intent] = CommandSpec(
                command=intent,
                category=_category(intent, skill.args_style),
                support_status="ready_later",
                adapter="l3",
                sub_skill=None,
                required_inputs=BASE_REQUIRED_INPUTS,
                outputs=(f"{intent}.xlsx",),
                b2_group=_b2_group(intent),
                args_style=skill.args_style,
            )
            continue

        package_name = resolve_package_dir(capability_root, skill.package).name
        required: tuple[str, ...] = BASE_REQUIRED_INPUTS
        if skill.requires_access_plan:
            required = BASE_REQUIRED_INPUTS + ("access_plan",)
        if intent.startswith("ZTP名称替换"):
            # ztp_lld 由 runtime/ztp_prereq.ensure_ztp_lld 自动补齐
            required = BASE_REQUIRED_INPUTS
        if intent == "替换设备名称":
            required = BASE_REQUIRED_INPUTS + ("lld_design",)
        if intent == "生成设备清单":
            required = BASE_REQUIRED_INPUTS

        if intent == "生成完整LLD设计":
            specs[intent] = CommandSpec(
                command=intent,
                category="lld",
                support_status="ready",
                adapter="conductor",
                sub_skill="a3_LLD_generate_code1",
                required_inputs=required,
                outputs=("LLD设计.xlsx",),
                b2_group="SPINE/MLAG/ASN",
                args_style=skill.args_style,
                conductor_mode="plan_run",
                can_run_in_one_click=True,
            )
            continue

        if intent == "融合完整LLD设计":
            specs[intent] = CommandSpec(
                command=intent,
                category="lld",
                support_status="ready",
                adapter="conductor",
                sub_skill="a3_LLD_generate_code1",
                required_inputs=required,
                outputs=("LLD设计.xlsx",),
                b2_group="SPINE/MLAG/ASN",
                args_style=skill.args_style,
                conductor_mode="integrate",
                can_run_in_one_click=True,
            )
            continue

        specs[intent] = CommandSpec(
            command=intent,
            category=_category(intent, skill.args_style),
            support_status="ready",
            adapter="l3",
            sub_skill=package_name,
            required_inputs=required,
            outputs=(f"{intent}.xlsx",),
            b2_group=_b2_group(intent),
            args_style=skill.args_style,
            can_run_in_one_click=skill.args_style in {"dw_007", "input_check"},
        )

    for l1 in _load_dispatch_l1(capability_root):
        if l1 in specs:
            continue
        specs[l1] = CommandSpec(
            command=l1,
            category="batch",
            support_status="ready",
            adapter="dispatch",
            sub_skill="lld-dispatch-orchestrator.code1",
            required_inputs=BASE_REQUIRED_INPUTS,
            outputs=(),
            b2_group=_b2_group(l1),
            can_run_in_one_click=True,
        )

    return specs


def reload_command_registry(skill_root: Path) -> None:
    global COMMANDS
    COMMANDS = build_command_registry(skill_root)


COMMANDS: Dict[str, CommandSpec] = {}
try:
    COMMANDS = build_command_registry()
except FileNotFoundError:
    COMMANDS = {}


READY_LATER_COMMANDS: dict[str, str] = {
    "带外管理地址规划": "管理面",
    "管理面地址规划": "计算面",
    "管存面地址规划": "计算面",
    "业务面地址规划": "计算面",
    "样本面地址规划": "计算面",
    "参数面地址规划": "计算面",
    "超平面地址规划": "SPINE/MLAG/ASN",
    "网络业务地址规划": "网络面",
    "防火墙互联规划": "网络面",
    "路由协议规划": "SPINE/MLAG/ASN",
    "ZTP开局": "SPINE/MLAG/ASN",
    "查询设计进度": "计算面",
}


PARTIAL_COMMANDS: dict[str, str] = {}

PENDING_COMMANDS: dict[str, str] = {
    "网络地址规划知识": "计算面",
}


def get_command(command: str) -> CommandSpec | None:
    spec = COMMANDS.get(command)
    if spec is not None and spec.support_status == "ready":
        return spec
    return None


def get_command_spec(command: str) -> CommandSpec | None:
    return COMMANDS.get(command)


def support_status(command: str) -> tuple[str, str]:
    spec = COMMANDS.get(command)
    if spec is not None:
        return spec.support_status, spec.b2_group
    if command in READY_LATER_COMMANDS:
        return "ready_later", READY_LATER_COMMANDS[command]
    if command in PARTIAL_COMMANDS:
        return "partial", PARTIAL_COMMANDS[command]
    if command in PENDING_COMMANDS:
        return "pending", PENDING_COMMANDS[command]
    return "unknown", "计算面"


def all_known_commands() -> list[str]:
    return sorted(set(COMMANDS) | set(READY_LATER_COMMANDS) | set(PARTIAL_COMMANDS) | set(PENDING_COMMANDS))
