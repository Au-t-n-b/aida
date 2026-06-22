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


class ContractPaths(TypedDict):
    base: str
    in_: str
    parse: str
    out: str
    boq_list_in: str
    boq_info_in: str
    boq_upload_in: str
    boq_device_parse: str
    service_boq_parse: str
    delivery_scenario_parse: str
    project_basic_out: str
    contract_device_table_out: str
    simulation_device_out: str


def contract_paths(project_root: str) -> ContractPaths:
    triple = _ipo_triple(project_root, "早期介入", "合同")
    in_base = triple["in_"]
    parse_base = triple["parse"]
    out_base = triple["out"]
    return {
        **triple,
        "boq_list_in": _join_path(in_base, "合同BOQ列表.xlsx"),
        "boq_info_in": _join_path(in_base, "BOQ信息表"),
        "boq_upload_in": _join_path(in_base, "BOQ"),
        "boq_device_parse": _join_path(parse_base, "BOQ设备解析原始结果"),
        "service_boq_parse": _join_path(parse_base, "服务BOQ解析结果"),
        "delivery_scenario_parse": _join_path(parse_base, "项目交付场景信息表"),
        "project_basic_out": _join_path(out_base, "项目基础信息表"),
        "contract_device_table_out": _join_path(out_base, "设备信息表"),
        "simulation_device_out": _join_path(out_base, "建模仿真设备信息表"),
    }


class ProposalPaths(TypedDict):
    base: str
    in_: str
    parse: str
    out: str
    proposal_draft_dir: str
    proposal_draft_manifest: str
    proposal_versions_out: str
    version_info_records_out: str
    version_info_xlsx_out: str
    contract_project_basic_out: str
    device_boq_parse: str
    contract_service_boq_parse: str
    product_basic_info: str
    device_table_out: str
    service_boq_parse: str
    maint_proposal_parse: str


def proposal_paths(project_root: str) -> ProposalPaths:
    triple = _ipo_triple(project_root, "早期介入", "交付预案")
    draft_dir = _join_path(triple["parse"], "预案草稿")
    versions_dir = _join_path(triple["out"], "预案版本")
    contract = contract_paths(project_root)
    return {
        **triple,
        "proposal_draft_dir": draft_dir,
        "proposal_draft_manifest": _join_path(draft_dir, "manifest.json"),
        "proposal_versions_out": versions_dir,
        "version_info_records_out": _join_path(triple["out"], "预案版本信息表.records.json"),
        "version_info_xlsx_out": _join_path(triple["out"], "预案版本信息表.xlsx"),
        "contract_project_basic_out": contract["project_basic_out"],
        # BOQ 原始解析结果统一归档在合同模块，交付预案只读取不重复落盘。
        "device_boq_parse": contract["boq_device_parse"],
        "contract_service_boq_parse": contract["service_boq_parse"],
        "product_basic_info": "org-assets/产品基本信息表",
        "device_table_out": _join_path(triple["out"], "设备信息表.xlsx"),
        # Keep key for backward compatibility with current assemblers/readers.
        "service_boq_parse": contract["service_boq_parse"],
        "maint_proposal_parse": _join_path(triple["parse"], "维保建议书解析结果"),
    }


def project_root(project_id: str) -> str:
    return project_id
