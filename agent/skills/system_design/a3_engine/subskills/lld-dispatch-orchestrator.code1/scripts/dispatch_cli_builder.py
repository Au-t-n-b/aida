"""Build subprocess CLI for child skills (args from l3_skill_index only)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from dispatch_config_loader import L3SkillDef, load_l3_index
from dispatch_path_utils import SKILL_ROOT


def _py() -> str:
    return sys.executable or "python"


def entrypoint_path(skill: L3SkillDef) -> Path:
    return (SKILL_ROOT / skill.package / skill.entrypoint).resolve()


def find_prior_flags(out_dir: Path, pass_prior: List[str]) -> str:
    flags: List[str] = []
    if "connect" in pass_prior:
        for p in sorted(out_dir.rglob("A3网络互连规划.xlsx")):
            flags = ["--prior-connect", str(p)]
            break
        if not flags:
            for p in sorted(out_dir.rglob("*网络互联规划.xlsx")):
                flags = ["--prior-connect", str(p)]
                break
    if "access" in pass_prior:
        for p in sorted(out_dir.rglob("A3网络设备接入规划.xlsx")):
            flags += ["--prior-access", str(p)]
            break
    return " ".join(flags)


def _find_access_plan(out_dir: Path) -> Path:
    for p in sorted(out_dir.rglob("A3网络设备接入规划.xlsx")):
        return p
    return out_dir / "A3网络设备接入规划.xlsx"


def _package_tail(package: str) -> str:
    return Path(package.replace("\\", "/")).name.lower()


def _connect_or_007_flag(package: str) -> str:
    tail = _package_tail(package)
    if tail in {
        "a3-ywm-ip-workflow.code1",
        "a3-ybm-ip-workflow.code1",
        "a3-cpm-lq-ip-workflow.code1",
        "a3-gcm-ip-workflow.code1",
    }:
        return "--007"
    return "--connect"


def _append_default_connect_sheet(
    parts: list,
    skill: L3SkillDef,
    style: str,
) -> None:
    """Pass main_flow-aligned 007/connect sheet when l3_skill_index defines default_sheet."""
    sheet = skill.default_sheet
    if not sheet or style in ("l2l3_sheet",):
        return
    tail = _package_tail(skill.package)
    if style == "dw_007":
        sheet_flag = "--sheet007" if tail == "a3-dw-manage-ip-workflow.code1" else "--sheet"
        parts += [sheet_flag, sheet]
    elif style == "gcm":
        parts += ["--sheet007", sheet]
    elif style == "connect_resource":
        flag = (
            "--sheet007"
            if _connect_or_007_flag(skill.package) == "--007"
            else "--sheet-connect"
        )
        parts += [flag, sheet]


def _append_topology_resource(
    parts: list,
    skill: L3SkillDef,
    style: str,
    topology: Optional[Path],
    resource: Optional[Path],
) -> None:
    if style == "dw_007":
        if topology is not None:
            parts += ["--007", str(topology)]
        if resource is not None:
            parts += ["--resource", str(resource)]
        return
    if style == "mlag":
        if topology is not None:
            parts += ["--topology", str(topology)]
        if resource is not None:
            parts += ["--resource", str(resource)]
        return
    if style in ("ywm", "ni", "connect_resource"):
        if topology is not None:
            parts += [_connect_or_007_flag(skill.package), str(topology)]
        if resource is not None:
            parts += ["--resource", str(resource)]
        tail = _package_tail(skill.package)
        if tail == "a3-ywm-ip-workflow.code1" and style == "connect_resource":
            parts += ["--topology", "i3", "--server-substring", "AT900A3"]
        if tail == "a3-ybm-ip-workflow.code1":
            parts += ["--topology", "i3", "--no-server-filter"]
        if tail == "a3-gcm-ip-workflow.code1" and style == "gcm":
            parts += ["--server-substring", "AT900A3"]
        return
    if style == "oob_plan":
        if topology is not None:
            parts += ["--topology", str(topology)]
        if resource is not None:
            parts += ["--resource", str(resource)]
        return
    if style == "l2l3_sheet":
        if topology is not None:
            parts += ["--007", str(topology)]
        if resource is not None:
            parts += ["--resource", str(resource)]
        return
    if style == "gcm":
        if topology is not None:
            parts += ["--007", str(topology)]
        if resource is not None:
            parts += ["--resource", str(resource)]
        return
    if style == "lld_generate":
        if topology is not None:
            parts += ["--topology", str(topology)]
        if resource is not None:
            parts += ["--resource", str(resource)]
        return


def build_cli(
    skill: L3SkillDef,
    intent: str,
    out_dir: Path,
    topology: Optional[Path] = None,
    resource: Optional[Path] = None,
    prior_flags: str = "",
) -> str:
    ep = entrypoint_path(skill)
    style = skill.args_style
    parts = [_py(), str(ep)]

    if style == "ywm":
        parts += ["--intent", intent]
    elif style == "ni":
        parts += ["--intent", intent]
    elif style == "oob_plan":
        layer_arg = (skill.default_layer or "l3").lower()
        out_file = out_dir / "A3网络互联规划.xlsx"
        parts += [
            "--layer",
            layer_arg,
            "--out",
            str(out_file),
            "--plan",
            intent,
        ]
    elif style == "l2l3_sheet":
        sheet = skill.default_sheet or "计算管理面端口互联"
        parts += ["--sheet", sheet]
    elif style == "gcm":
        plane = skill.default_network_plane or "计算管存面"
        parts += [
            "--topology",
            "i3",
            "--network-plane",
            plane,
            "--skip-prompt-check",
            "--server-substring",
            "AT900A3",
        ]
    elif style == "access_query":
        access_plan = _find_access_plan(out_dir)
        out_file = out_dir / f"A3接入查询_{intent}.xlsx"
        parts += [
            "--access-plan",
            str(access_plan),
            "--plan",
            intent,
            "--out",
            str(out_file),
        ]
    elif style == "lld_generate":
        mode = skill.lld_mode or "plan"
        parts += ["--mode", mode]
    elif style in ("ztp_scan", "lq_open_scan"):
        parts += ["--scan-dir", str(out_dir)]
        parts += ["--out-dir", str(out_dir)]
    elif style == "device_naming":
        sub = skill.naming_subcommand or "generate-list"
        parts.append(sub)
    elif style == "input_check":
        parts += ["--scan-dir", str(out_dir.parent)]
        parts += ["--out-dir", str(out_dir)]
    elif style == "mlag":
        parts += ["--output-dir", str(out_dir)]
    elif style == "planner":
        tail = _package_tail(skill.package)
        if tail == "dme-planning.code1":
            parts += ["--trigger", intent]
            if topology is not None:
                parts += ["--port-file", str(topology)]
            if resource is not None:
                parts += ["--resource-file", str(resource)]
            parts += ["--output-dir", str(out_dir), "--dataturbo", "false", "--mlag", "auto"]
        elif tail == "ccae-planner.code1":
            if topology is not None:
                parts += ["--topology", str(topology)]
            if resource is not None:
                parts += ["--resource", str(resource)]
            parts += ["--out", str(out_dir / "A3CCAE部署规划.xlsx")]
        elif tail == "nce-planner.code1":
            if topology is not None:
                parts += ["--topology", str(topology)]
            if resource is not None:
                parts += ["--resource", str(resource)]
            parts += ["--out", str(out_dir / "A3NCE部署规划.xlsx")]

    _append_default_connect_sheet(parts, skill, style)

    if style not in (
        "access_query",
        "ztp_scan",
        "lq_open_scan",
        "input_check",
        "oob_plan",
        "planner",
        "mlag",
    ):
        parts += ["--out-dir", str(out_dir)]

    if style != "planner":
        _append_topology_resource(parts, skill, style, topology, resource)

    if prior_flags.strip():
        parts.append(prior_flags.strip())
    return " ".join(parts)


def resolve_run_cli(
    task: Mapping[str, object],
    phase: Mapping[str, object],
    plan_inputs: Mapping[str, object],
    l3_index: Optional[Dict[str, L3SkillDef]] = None,
) -> str:
    """Rebuild CLI at run time with fresh pass_prior / access-plan paths."""
    intent = str(task.get("intent", ""))
    out_dir = Path(str(plan_inputs.get("out_dir", ".")))
    topo_raw = plan_inputs.get("topology")
    res_raw = plan_inputs.get("resource")
    topology = Path(str(topo_raw)) if topo_raw else None
    resource = Path(str(res_raw)) if res_raw else None
    pass_prior = list(phase.get("pass_prior") or [])
    prior_flags = find_prior_flags(out_dir, pass_prior)

    index = l3_index if l3_index is not None else load_l3_index()
    skill = index.get(intent)
    if skill and not skill.unsupported and not skill.pending and skill.package:
        return build_cli(
            skill,
            intent,
            out_dir,
            topology=topology,
            resource=resource,
            prior_flags=prior_flags,
        )

    cli = str(task.get("cli", ""))
    if prior_flags.strip() and prior_flags not in cli:
        cli = f"{cli} {prior_flags}".strip()
    return cli
