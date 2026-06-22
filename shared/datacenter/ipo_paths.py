"""IPO 逻辑路径 ↔ 数据中心语义键（与 mock 目录 SSOT 对齐）。"""
from __future__ import annotations

from shared.datacenter.types import SemanticFileRef

# 组织资产（跨项目）— 物理根 org-assets/，与数据中心 moduleCode 一致
RACI_TEMPLATE_LOGICAL = "org-assets/责任矩阵/责任矩阵模板.xlsx"

# 项目内相对路径后缀（不含项目根前缀）
SUFFIX_RACI_OUT = "早期介入/交付预案/输出结果/项目责任矩阵.xlsx"
SUFFIX_ACCEPTANCE_OUT = "早期介入/交付预案/输出结果/验收策略.xlsx"
SUFFIX_TESTCASES_OUT = "早期介入/交付预案/输出结果/测试用例.xlsx"
SUFFIX_TESTCASES_TEMPLATE = "早期介入/交付预案/输入文件/测试用例/测试用例模板.xlsx"
SUFFIX_TECH_PROPOSAL_DIR = "早期介入/交付预案/输入文件/技术建议书"
SUFFIX_PLAN_SCHEDULE = "项目管理/计划/输入文件/交付计划表.xlsx"
SUFFIX_SIMULATION_MD = "早期介入/合同/输出结果/建模仿真/建模仿真设备信息表.md"
SUFFIX_BOQ_UPLOAD_DIR = "早期介入/合同/输入文件/BOQ"
SUFFIX_BOQ_DEVICE_PARSE_DIR = "早期介入/合同/解析结果/BOQ设备解析原始结果"
SUFFIX_SERVICE_BOQ_PARSE_DIR = "早期介入/合同/解析结果/服务BOQ解析结果"
SUFFIX_DELIVERY_SCENARIO = "早期介入/合同/解析结果/项目交付场景信息表"
SUFFIX_PROJECT_BASIC_OUT = "早期介入/合同/输出结果/项目基础信息表"
SUFFIX_PROPOSAL_DEVICE_TABLE_OUT = "早期介入/交付预案/输出结果/设备信息表.xlsx"
SUFFIX_HLD_PARSE_DIR = "早期介入/交付预案/解析结果/HLD解析结果"
SUFFIX_TECH_PROPOSAL_PARSE_DIR = "早期介入/交付预案/解析结果/服务建议书解析结果"
SUFFIX_TESTCASE_PARSE_DIR = "早期介入/交付预案/解析结果/测试用例解析结果"


def mock_logical_path(project_folder: str, suffix: str) -> str:
    return f"{project_folder}/{suffix}" if project_folder else suffix


def raci_template_ref() -> SemanticFileRef:
    return SemanticFileRef(
        module_code="org-assets",
        folder_sub_path="责任矩阵",
        file_name="责任矩阵模板.xlsx",
    )


def raci_out_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="proposal",
        file_stage="输出结果",
        file_name="项目责任矩阵.xlsx",
    )


def plan_schedule_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="pm-plan",
        file_stage="输入文件",
        file_name="交付计划表.xlsx",
    )


def acceptance_out_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="proposal",
        file_stage="输出结果",
        file_name="验收策略.xlsx",
    )


def tech_proposal_dir_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="proposal",
        file_stage="输入文件",
        folder_sub_path="技术建议书",
    )


def testcases_template_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="proposal",
        file_stage="输入文件",
        folder_sub_path="测试用例",
        file_name="测试用例模板.xlsx",
    )


def testcases_out_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="proposal",
        file_stage="输出结果",
        file_name="测试用例.xlsx",
    )


def card_scale_md_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="contract",
        file_stage="输出结果",
        folder_sub_path="建模仿真",
        file_name="建模仿真设备信息表.md",
    )


def boq_upload_dir_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="contract",
        file_stage="输入文件",
        folder_sub_path="BOQ",
    )


def boq_device_parse_dir_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="contract",
        file_stage="解析结果",
        folder_sub_path="BOQ设备解析原始结果",
    )


def service_boq_parse_dir_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="contract",
        file_stage="解析结果",
        folder_sub_path="服务BOQ解析结果",
    )


def delivery_scenario_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="contract",
        file_stage="解析结果",
        file_name="项目交付场景信息表.xlsx",
    )


def project_basic_out_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="contract",
        file_stage="输出结果",
        file_name="项目基础信息表",
    )


def proposal_device_table_out_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="proposal",
        file_stage="输出结果",
        file_name="设备信息表.xlsx",
    )


def tech_proposal_parse_dir_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="proposal",
        file_stage="解析结果",
        folder_sub_path="服务建议书解析结果",
    )


def testcase_parse_dir_ref(project_id: str) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code="proposal",
        file_stage="解析结果",
        folder_sub_path="测试用例解析结果",
    )


def slot_to_ref(slot: str, project_id: str) -> SemanticFileRef:
    mapping = {
        "raci_template": raci_template_ref,
        "raci_out": lambda: raci_out_ref(project_id),
        "plan": lambda: plan_schedule_ref(project_id),
        "acceptance_out": lambda: acceptance_out_ref(project_id),
        "acceptance_input": lambda: tech_proposal_dir_ref(project_id),
        "testcases_template": lambda: testcases_template_ref(project_id),
        "testcases_out": lambda: testcases_out_ref(project_id),
        "card_scale": lambda: card_scale_md_ref(project_id),
    }
    fn = mapping.get(slot)
    if not fn:
        raise ValueError(f"unknown slot: {slot}")
    return fn()


def slot_to_mock_suffix(slot: str) -> str:
    mapping = {
        "raci_template": RACI_TEMPLATE_LOGICAL,
        "raci_out": SUFFIX_RACI_OUT,
        "plan": SUFFIX_PLAN_SCHEDULE,
        "acceptance_out": SUFFIX_ACCEPTANCE_OUT,
        "acceptance_input": SUFFIX_TECH_PROPOSAL_DIR,
        "testcases_template": SUFFIX_TESTCASES_TEMPLATE,
        "testcases_out": SUFFIX_TESTCASES_OUT,
        "card_scale": SUFFIX_SIMULATION_MD,
    }
    suffix = mapping.get(slot)
    if not suffix:
        raise ValueError(f"unknown slot: {slot}")
    return suffix
