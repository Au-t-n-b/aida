"""LangGraph Step IO 契约 · early.contract.boq_parse / early.proposal.table_gen。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ModuleCode = Literal["contract", "proposal", "org-assets", "pm-plan"]
FileStage = Literal["输入文件", "解析结果", "输出结果"]


@dataclass(frozen=True)
class StepIoRef:
    step_key: str
    skill_id: str
    module_code: ModuleCode
    file_stage: FileStage
    folder_sub_path: str | None
    file_name: str | None
    logical_suffix: str
    description: str


CONTRACT_BOQ_STEPS: tuple[StepIoRef, ...] = (
    StepIoRef(
        "preflight",
        "contract_boq",
        "contract",
        "输入文件",
        None,
        None,
        "早期介入/合同",
        "环境预检：目录可写、uniEx 可用性",
    ),
    StepIoRef(
        "boq_input_check",
        "contract_boq",
        "contract",
        "输入文件",
        "BOQ",
        None,
        "早期介入/合同/输入文件/BOQ/",
        "检查 BOQ xlsx 已上传（HITL FilePicker）",
    ),
    StepIoRef(
        "stage1_parse",
        "contract_boq",
        "contract",
        "解析结果",
        "BOQ设备解析原始结果",
        "*.normalized.json",
        "早期介入/合同/解析结果/BOQ设备解析原始结果/",
        "uniEx clone-boq Stage1 → normalized.json",
    ),
    StepIoRef(
        "stage2_device_table",
        "contract_boq",
        "contract",
        "输出结果",
        "建模仿真",
        "建模仿真设备信息表.md",
        "早期介入/合同/输出结果/建模仿真/建模仿真设备信息表.md",
        "uniEx clone-boq Stage2 → 建模仿真设备信息表",
    ),
    StepIoRef(
        "publish_outputs",
        "contract_boq",
        "contract",
        "解析结果",
        "BOQ设备解析原始结果",
        None,
        "早期介入/合同/解析结果/BOQ设备解析原始结果/",
        "登记产物到 state.files，供交付预案消费",
    ),
)

PROPOSAL_GEN_STEPS: tuple[StepIoRef, ...] = (
    StepIoRef(
        "preflight",
        "proposal_gen",
        "proposal",
        "输入文件",
        None,
        None,
        "早期介入/交付预案",
        "环境预检：合同解析结果是否就绪",
    ),
    StepIoRef(
        "ingest_contract",
        "proposal_gen",
        "contract",
        "解析结果",
        "BOQ设备解析原始结果",
        "*.normalized.json",
        "早期介入/合同/解析结果/BOQ设备解析原始结果/",
        "读取合同侧 BOQ 解析产物（只读）",
    ),
    StepIoRef(
        "parse_tech_proposal",
        "proposal_gen",
        "proposal",
        "解析结果",
        "服务建议书解析结果",
        None,
        "早期介入/交付预案/解析结果/服务建议书解析结果/",
        "uniEx doC · 技术建议书 → 验收策略",
    ),
    StepIoRef(
        "parse_testcases",
        "proposal_gen",
        "proposal",
        "解析结果",
        "测试用例解析结果",
        None,
        "早期介入/交付预案/解析结果/测试用例解析结果/",
        "uniEx doC · 测试用例结构化",
    ),
    StepIoRef(
        "assemble_device_table",
        "proposal_gen",
        "proposal",
        "输出结果",
        None,
        "设备信息表.xlsx",
        "早期介入/交付预案/输出结果/设备信息表.xlsx",
        "device_boq_assembler + OCC enrichment",
    ),
    StepIoRef(
        "assemble_service_maint",
        "proposal_gen",
        "contract",
        "解析结果",
        "服务BOQ解析结果",
        None,
        "早期介入/合同/解析结果/服务BOQ解析结果/",
        "第8章服务/维保组装（读合同服务 BOQ）",
    ),
    StepIoRef(
        "table_gen_release",
        "proposal_gen",
        "proposal",
        "输出结果",
        None,
        None,
        "早期介入/交付预案/输出结果/",
        "17+ 表：读取 解析结果/* → promote 写 输出结果/*.xlsx；HITL 后 release 写 预案版本信息表（见 promote.py）",
    ),
)
