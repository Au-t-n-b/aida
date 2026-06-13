"""
IPO path constants — mirror of aida-delivery-v1 project-paths.ts (SSOT).
Business code must import from here; no scattered path strings.
"""
from __future__ import annotations

from typing import TypedDict


class IpoTriple(TypedDict):
    base: str
    in_: str
    parse: str
    out: str


IPO_INPUT = "输入文件"
IPO_PARSE = "解析结果"
IPO_OUTPUT = "输出结果"


def _join_path(*parts: str) -> str:
    cleaned: list[str] = []
    for part in parts:
        seg = str(part).strip().strip("/\\")
        if seg:
            cleaned.append(seg)
    return "/".join(cleaned)


def _ipo_triple(root: str, domain: str, module: str) -> IpoTriple:
    base = _join_path(root, domain, module)
    return {
        "base": base,
        "in_": _join_path(base, IPO_INPUT),
        "parse": _join_path(base, IPO_PARSE),
        "out": _join_path(base, IPO_OUTPUT),
    }


class ProposalPaths(TypedDict):
    base: str
    in_: str
    parse: str
    out: str
    proposal_draft_dir: str
    proposal_draft_manifest: str
    proposal_versions_out: str
    version_info_out: str
    contract_project_basic_out: str
    device_boq_parse: str
    product_basic_info: str
    device_table_out: str
    service_boq_parse: str
    maint_proposal_parse: str
    service_delivery_ui_out: str
    service_content_out: str
    maint_strategy_out: str
    maint_sla_out: str


def proposal_paths(project_root: str) -> ProposalPaths:
    triple = _ipo_triple(project_root, "早期介入", "交付预案")
    draft_dir = _join_path(triple["parse"], "预案草稿")
    versions_dir = _join_path(triple["out"], "预案版本")
    contract_root = _join_path(project_root, "早期介入", "合同")
    return {
        **triple,
        "proposal_draft_dir": draft_dir,
        "proposal_draft_manifest": _join_path(draft_dir, "manifest.json"),
        "proposal_versions_out": versions_dir,
        "version_info_out": _join_path(triple["out"], "预案版本信息表"),
        "contract_project_basic_out": _join_path(contract_root, IPO_OUTPUT, "项目基础信息表"),
        "device_boq_parse": _join_path(triple["parse"], "设备BOQ解析结果"),
        "product_basic_info": "组织资产/产品基本信息表",
        "device_table_out": _join_path(triple["out"], "设备信息表"),
        "service_boq_parse": _join_path(triple["parse"], "服务BOQ解析结果"),
        "maint_proposal_parse": _join_path(triple["parse"], "维保建议书"),
        "service_delivery_ui_out": _join_path(triple["out"], "服务配置.xlsx"),
        "service_content_out": _join_path(triple["out"], "服务内容.xlsx"),
        "maint_strategy_out": _join_path(triple["out"], "维保策略.xlsx"),
        "maint_sla_out": _join_path(triple["out"], "维保SLA.xlsx"),
    }


def project_root(project_id: str) -> str:
    return project_id
