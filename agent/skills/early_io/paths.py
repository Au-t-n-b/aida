"""物理路径解析 · 对齐 05-数据目录与平台规范 §3.3 / §4.1 / §4.2。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.config import BUSINESS_ROOT
from agent.constants.project_paths import contract_paths, proposal_paths


def resolve_project_id(project: dict[str, Any] | None) -> str:
    if not project:
        return ""
    for key in ("project_id", "projectId", "id", "project_code", "projectCode"):
        val = str(project.get(key) or "").strip()
        if val:
            return val
    return ""


def project_physical_root(project_id: str) -> Path:
    return BUSINESS_ROOT / "projects" / project_id


def uniex_bench_root() -> Path | None:
    """uniEx-bench 仓库根；用于 subprocess 调用 clone-boq。"""
    raw = os.environ.get("UNIEX_BENCH_ROOT", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_dir() else None
    sibling = BUSINESS_ROOT.parents[2] / "交付预案" / "uniEx-bench"
    if sibling.is_dir():
        return sibling
    return None


def clone_boq_skill_root() -> Path | None:
    root = uniex_bench_root()
    if not root:
        return None
    skill = root / "boQ-bench" / "SKILL" / "clone-boq"
    return skill if skill.is_dir() else None


@dataclass(frozen=True)
class EarlyIoPaths:
    project_id: str
    project_root: Path
    contract_boq_upload: Path
    contract_boq_parse: Path
    contract_service_boq_parse: Path
    contract_simulation_out: Path
    contract_simulation_md: Path
    proposal_parse_root: Path
    proposal_output_root: Path
    proposal_device_table_out: Path
    proposal_tech_proposal_in: Path
    proposal_testcases_in: Path
    proposal_tech_proposal_parse: Path
    proposal_testcase_parse: Path
    proposal_acceptance_parse: Path
    proposal_hld_parse: Path
    proposal_maint_proposal_parse: Path

    def rel(self, path: Path) -> str:
        return str(path.relative_to(self.project_root))

    def proposal_output_table(self, xlsx_name: str) -> Path:
        return self.proposal_output_root / xlsx_name


def resolve_early_io_paths(project: dict[str, Any] | None) -> EarlyIoPaths | None:
    pid = resolve_project_id(project)
    if not pid:
        return None
    root = project_physical_root(pid)
    c = contract_paths("")
    p = proposal_paths("")
    parse_root = root / p["parse"]
    return EarlyIoPaths(
        project_id=pid,
        project_root=root,
        contract_boq_upload=root / c["boq_upload_in"],
        contract_boq_parse=root / c["boq_device_parse"],
        contract_service_boq_parse=root / c["service_boq_parse"],
        contract_simulation_out=root / c["simulation_device_out"],
        contract_simulation_md=root / "早期介入/合同/输出结果/建模仿真/建模仿真设备信息表.md",
        proposal_parse_root=parse_root,
        proposal_output_root=root / p["out"],
        proposal_device_table_out=root / p["device_table_out"],
        proposal_tech_proposal_in=root / f"{p['in_']}/技术建议书",
        proposal_testcases_in=root / f"{p['in_']}/测试用例",
        proposal_tech_proposal_parse=parse_root / "服务建议书解析结果",
        proposal_testcase_parse=parse_root / "测试用例解析结果",
        proposal_acceptance_parse=parse_root / "验收策略解析结果",
        proposal_hld_parse=parse_root / "HLD解析结果",
        proposal_maint_proposal_parse=parse_root / "维保建议书解析结果",
    )
