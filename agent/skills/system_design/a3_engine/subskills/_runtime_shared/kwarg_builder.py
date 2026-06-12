"""Build argv for pipeline main() from l3_skill_index args_style."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from runtime.registry_loader import L3SkillDef


def find_prior_paths(out_dir: Path, pass_prior: List[str]) -> Dict[str, Path]:
    found: Dict[str, Path] = {}
    if "connect" in pass_prior:
        for p in sorted(out_dir.rglob("A3网络互连规划.xlsx")):
            found["prior_connect"] = p
            break
        if "prior_connect" not in found:
            for p in sorted(out_dir.rglob("*网络互联规划.xlsx")):
                found["prior_connect"] = p
                break
    if "access" in pass_prior:
        for p in sorted(out_dir.rglob("A3网络设备接入规划.xlsx")):
            found["prior_access"] = p
            break
    return found


def _find_access_plan(out_dir: Path) -> Path:
    for p in sorted(out_dir.rglob("A3网络设备接入规划.xlsx")):
        return p
    return out_dir / "A3网络设备接入规划.xlsx"


def _append_topology_resource(
    argv: List[str],
    style: str,
    topology: Optional[Path],
    resource: Optional[Path],
) -> None:
    if style == "dw_007":
        if topology is not None:
            argv += ["--007", str(topology)]
        if resource is not None:
            argv += ["--resource", str(resource)]
        return
    if style in ("ywm", "ni", "connect_resource", "planner", "mlag", "input_check"):
        if topology is not None:
            flag = "--007" if "ywm" in skill.package.lower() and style == "connect_resource" else "--connect"
            argv += [flag, str(topology)]
        if resource is not None:
            argv += ["--resource", str(resource)]
        if "ywm" in skill.package.lower() and style == "connect_resource":
            argv += ["--topology", "i3"]
        return
    if style == "oob_plan":
        if topology is not None:
            argv += ["--topology", str(topology)]
        if resource is not None:
            argv += ["--resource", str(resource)]
        return
    if style in ("l2l3_sheet", "gcm"):
        if topology is not None:
            argv += ["--007", str(topology)]
        if resource is not None:
            argv += ["--resource", str(resource)]
        return
    if style == "lld_generate":
        if topology is not None:
            argv += ["--topology", str(topology)]
        if resource is not None:
            argv += ["--resource", str(resource)]
        return


def build_argv(
    skill: L3SkillDef,
    intent: str,
    out_dir: Path,
    *,
    topology: Optional[Path] = None,
    resource: Optional[Path] = None,
    pass_prior: Optional[List[str]] = None,
    scan_dir: Optional[Path] = None,
) -> List[str]:
    style = skill.args_style
    argv: List[str] = []
    prior = find_prior_paths(out_dir, list(pass_prior or []))

    if style == "ywm":
        argv += ["--intent", intent]
    elif style == "ni":
        argv += ["--intent", intent]
    elif style == "oob_plan":
        layer_arg = (skill.default_layer or "l3").lower()
        out_file = out_dir / "A3网络互联规划.xlsx"
        argv += [
            "--layer",
            layer_arg,
            "--out",
            str(out_file),
            "--plan",
            intent,
        ]
    elif style == "l2l3_sheet":
        sheet = skill.default_sheet or "计算管理面端口互联"
        argv += ["--sheet", sheet]
    elif style == "gcm":
        plane = skill.default_network_plane or "计算管存面"
        argv += ["--topology", "i3", "--network-plane", plane, "--skip-prompt-check"]
    elif style == "access_query":
        access_plan = prior.get("prior_access") or _find_access_plan(out_dir)
        out_file = out_dir / f"A3接入查询_{intent}.xlsx"
        argv += ["--access-plan", str(access_plan), "--plan", intent, "--out", str(out_file)]
    elif style == "lld_generate":
        argv += ["--mode", skill.lld_mode or "plan"]
    elif style in ("ztp_scan", "lq_open_scan"):
        argv += ["--scan-dir", str(scan_dir or out_dir)]
    elif style == "device_naming":
        argv.append(skill.naming_subcommand or "generate-list")
    elif style == "input_check":
        argv += ["--scan-dir", str(scan_dir or out_dir.parent if scan_dir is None else scan_dir)]

    sheet = skill.default_sheet
    if sheet and style not in ("l2l3_sheet", "access_query", "ztp_scan", "lq_open_scan", "input_check"):
        if style == "dw_007":
            argv += ["--sheet007", sheet]
        elif style == "gcm":
            argv += ["--sheet007", sheet]
        elif style == "connect_resource":
            pkg = skill.package.replace("\\", "/").lower()
            flag = (
                "--sheet007"
                if any(
                    x in pkg
                    for x in (
                        "a3-ywm-ip-workflow",
                        "a3-ybm-ip-workflow",
                        "a3-cpm-lq-ip-workflow",
                        "a3-gcm-ip-workflow",
                    )
                )
                else "--sheet-connect"
            )
            argv += [flag, sheet]

    if style not in ("access_query", "ztp_scan", "lq_open_scan", "input_check"):
        argv += ["--out-dir", str(out_dir)]

    _append_topology_resource(argv, style, topology, resource)

    if prior.get("prior_connect") is not None:
        argv += ["--prior-connect", str(prior["prior_connect"])]
    if prior.get("prior_access") is not None:
        argv += ["--prior-access", str(prior["prior_access"])]

    return argv
