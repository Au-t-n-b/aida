"""Build argv for pipeline scripts (subprocess Skill-First)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from registry_loader import L3SkillDef


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


def _package_tail(package: str) -> str:
    return Path(package.replace("\\", "/")).name.lower()


def _connect_or_007_flag(package: str) -> str:
    """007/端口表 CLI 标志：按 package 精确匹配，避免 cc-ywm 子串误命中 ywm。"""
    tail = _package_tail(package)
    if tail in {
        "a3-ywm-ip-workflow.code1",
        "a3-ybm-ip-workflow.code1",
        "a3-cpm-lq-ip-workflow.code1",
    }:
        return "--007"
    return "--connect"


def _append_default_connect_sheet(
    argv: List[str],
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
        argv += [sheet_flag, sheet]
    elif style == "gcm":
        argv += ["--sheet007", sheet]
    elif style == "connect_resource":
        flag = (
            "--sheet007"
            if _connect_or_007_flag(skill.package) == "--007"
            else "--sheet-connect"
        )
        argv += [flag, sheet]


def _append_topology_resource(
    argv: List[str],
    skill: L3SkillDef,
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
    if style == "mlag":
        if topology is not None:
            argv += ["--topology", str(topology)]
        if resource is not None:
            argv += ["--resource", str(resource)]
        return
    if style in ("ywm", "ni", "connect_resource"):
        if topology is not None:
            argv += [_connect_or_007_flag(skill.package), str(topology)]
        if resource is not None:
            argv += ["--resource", str(resource)]
        tail = _package_tail(skill.package)
        if tail == "a3-ywm-ip-workflow.code1" and style == "connect_resource":
            argv += ["--topology", "i3", "--server-substring", "AT900A3"]
        if tail == "a3-ybm-ip-workflow.code1":
            argv += ["--topology", "i3", "--no-server-filter"]
        if tail == "a3-gcm-ip-workflow.code1" and style == "gcm":
            argv += ["--server-substring", "AT900A3"]
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
    ztp_lld: Optional[Path] = None,
    name_mapping: Optional[Path] = None,
    device_list: Optional[Path] = None,
    lld_design: Optional[Path] = None,
    location_004: Optional[Path] = None,
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
        argv += ["--layer", layer_arg, "--out", str(out_file), "--plan", intent]
        if out_file.is_file():
            argv += ["--merge-existing"]
        access_plan = prior.get("prior_access") or _find_access_plan(out_dir)
        if access_plan.is_file():
            argv += ["--access-plan", str(access_plan)]
    elif style == "l2l3_sheet":
        sheet = skill.default_sheet or "计算管理面端口互联"
        argv += ["--sheet", sheet]
    elif style == "gcm":
        plane = skill.default_network_plane or "计算管存面"
        argv += [
            "--topology",
            "i3",
            "--network-plane",
            plane,
            "--skip-prompt-check",
            "--server-substring",
            "AT900A3",
        ]
    elif style == "access_query":
        access_plan = prior.get("prior_access") or _find_access_plan(out_dir)
        out_file = out_dir / f"A3接入查询_{intent}.xlsx"
        argv += ["--access-plan", str(access_plan), "--plan", intent, "--out", str(out_file)]
    elif style == "lld_generate":
        argv += ["--mode", skill.lld_mode or "plan"]
        if (skill.lld_mode or "") == "integrate":
            # 部分产物（A3*.xlsx）落在 out_dir；勿用 Input 扫描目录
            argv += ["--scan-dir", str(out_dir)]
    elif style in ("ztp_scan", "lq_open_scan"):
        argv += ["--scan-dir", str(scan_dir or out_dir)]
        argv += ["--out-dir", str(out_dir)]
    elif style == "device_naming":
        argv.append(skill.naming_subcommand or "generate-list")
        sub = skill.naming_subcommand or "generate-list"
        if sub == "generate-list" and location_004 is not None:
            argv += ["--location", str(location_004)]
        elif sub == "replace-lld":
            if device_list is not None:
                argv += ["--device-list", str(device_list)]
            if lld_design is not None:
                argv += ["--lld", str(lld_design)]
        elif sub.startswith("replace-ztp"):
            if ztp_lld is not None:
                argv += ["--ztp-lld", str(ztp_lld)]
            if name_mapping is not None:
                argv += ["--mapping", str(name_mapping)]
    elif style == "input_check":
        argv += ["--scan-dir", str(scan_dir or out_dir.parent if scan_dir is None else scan_dir)]
        argv += ["--out-dir", str(out_dir)]
    elif style == "mlag":
        argv += [
            "--output-dir",
            str(out_dir),
            "--out",
            str(out_dir / "A3交换机MLAG规划.xlsx"),
            "--temp",
            str(out_dir / "交换机MLAG规划.xlsx"),
        ]
    elif style == "planner":
        tail = _package_tail(skill.package)
        if tail == "dme-planning.code1":
            argv += ["--trigger", intent]
            if topology is not None:
                argv += ["--port-file", str(topology)]
            if resource is not None:
                argv += ["--resource-file", str(resource)]
            argv += ["--output-dir", str(out_dir), "--dataturbo", "false", "--mlag", "auto"]
        elif tail == "ccae-planner.code1":
            if topology is not None:
                argv += ["--topology", str(topology)]
            if resource is not None:
                argv += ["--resource", str(resource)]
            argv += ["--out", str(out_dir / "A3CCAE部署规划.xlsx")]
        elif tail == "nce-planner.code1":
            if topology is not None:
                argv += ["--topology", str(topology)]
            if resource is not None:
                argv += ["--resource", str(resource)]
            argv += ["--out", str(out_dir / "A3NCE部署规划.xlsx")]

    _append_default_connect_sheet(argv, skill, style)

    # oob_plan / access_query / planner / mlag 等已用 --out/--output-dir/--scan-dir，勿再追加 --out-dir
    if style not in (
        "access_query",
        "ztp_scan",
        "lq_open_scan",
        "input_check",
        "oob_plan",
        "planner",
        "mlag",
    ):
        argv += ["--out-dir", str(out_dir)]

    if style != "planner":
        _append_topology_resource(argv, skill, style, topology, resource)

    # --prior-connect / --prior-access 仅 a3-net-interconnection-workflow（style=ni）接受；
    # oob_plan（run_oob_interconnect.py）与 access_query（run_network_access_plan.py）均不接受，
    # 误传会导致 argparse「unrecognized arguments」整条命令失败（如网络接入规划 13 条全错）。
    if style == "ni":
        if prior.get("prior_connect") is not None:
            argv += ["--prior-connect", str(prior["prior_connect"])]
        if prior.get("prior_access") is not None:
            argv += ["--prior-access", str(prior["prior_access"])]

    return argv
