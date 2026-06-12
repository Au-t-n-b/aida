# -*- coding: utf-8 -*-
"""文件标签机制（对齐 CPCIA Agent `deploymentandtest/constant/files.py`）。

Agent 用 `project_file_info(tag_name, agent_name, file_path, doc_id)` 登记每个文件，
靠 **标签** 而非文件名检索，避免改名导致后续处理遗漏。

本模块只放**常量与名称→标签映射**；登记/查询见 `file_registry.py`。
标签字符串与 Agent **保持一致**，后续对接数据库零映射。
"""
from __future__ import annotations


class AgentTag:
    """文件来源 Agent（与 Agent 端一致）。"""

    INSTALLATION = "installation_agent"
    DESIGN = "design_agent"
    DEPLOYMENT = "deployment_agent"


class FileTagName:
    """文件标签常量（照搬 Agent + 截图下拉项 + 结果类标签）。"""

    # —— 部署调测 Agent 相关（与 Agent files.py 完全一致）——
    PARAMS_CONFIG = "CloudOps_Params_Config"
    LLD_DESIGN = "LLD_Design"
    CHECK_LIST = "Device_Checklist"
    TESTCASE_A2 = "CloudOps_Testcase_A2"
    TESTCASE_A3 = "CloudOps_Testcase_A3"
    TESTCASE = "TestCase"
    CLOUDOPS_CONFIG_INIT = "CloudOps_Config_Init"
    CLOUDOPS_CONFIG_MANUAL = "CloudOps_Config_Manual"
    CLOUDOPS_CONFIG_FULL = "CloudOps_Config_Full"
    LQ_CONFIG_CHECK = "ZTP_CFG"
    POD_ID_MAP = "pod_id_map"
    DEFAULT = "default"

    # —— 执行结果（与 Agent 一致）——
    # Agent: 原始导出报告 tag=task_type；解析后 JSON 报告 tag="REPORT_JSON"
    REPORT_JSON = "REPORT_JSON"

    # —— 上游/其它 Agent 标签（截图下拉项，登记跨 Agent 文件时可用）——
    BOQ = "BOQ"
    HLD = "HLD"
    PERSONNEL = "Personnel"
    ARRIVAL_INFO = "Arrival_Info"
    INSTRUCTION = "instruction"
    WORK_PROCESS = "work_process"

    # 部署调测可选标签清单（校验上传 tag 是否合法，对齐 Agent FILE_TAG_LIST）
    FILE_TAG_LIST = [
        PARAMS_CONFIG,
        LLD_DESIGN,
        CHECK_LIST,
        TESTCASE,
        TESTCASE_A2,
        TESTCASE_A3,
        CLOUDOPS_CONFIG_INIT,
        CLOUDOPS_CONFIG_MANUAL,
        CLOUDOPS_CONFIG_FULL,
        LQ_CONFIG_CHECK,
        POD_ID_MAP,
        REPORT_JSON,
        DEFAULT,
    ]


# 文件名关键字 → 标签（对齐 Agent FILE_NAME_TAG_MAP，键为子串匹配）。
FILE_NAME_TAG_MAP: dict[str, str] = {
    "CloudOps上传测试参数": FileTagName.PARAMS_CONFIG,
    "CloudOps_task_params": FileTagName.PARAMS_CONFIG,
    "设备安装完工清单": FileTagName.CHECK_LIST,
    "全量设备完工清单列表": FileTagName.CHECK_LIST,
    "LLD设计": FileTagName.LLD_DESIGN,
    "计算子系统测试+集群测试用例": FileTagName.TESTCASE,
    "CloudOps初始配置手工补充": FileTagName.CLOUDOPS_CONFIG_MANUAL,
    "CloudOps配置_手工补充": FileTagName.CLOUDOPS_CONFIG_MANUAL,
    "CloudOps初始配置": FileTagName.CLOUDOPS_CONFIG_INIT,
    "CloudOps完整配置": FileTagName.CLOUDOPS_CONFIG_FULL,
    "ZTP配置检查": FileTagName.LQ_CONFIG_CHECK,
    "ZTP文件": FileTagName.LQ_CONFIG_CHECK,
    "pod_id_map": FileTagName.POD_ID_MAP,
}


def infer_tag_from_filename(filename: str) -> str:
    """按文件名子串推断标签；命中不到返回 DEFAULT。

    注意：顺序敏感——更长/更具体的键应排在前（如「手工补充」先于「初始配置」）。
    """
    name = str(filename or "")
    for keyword, tag in FILE_NAME_TAG_MAP.items():
        if keyword in name:
            return tag
    return FileTagName.DEFAULT


def report_tag_for_task(task_type: str) -> str:
    """原始导出报告的标签：与 Agent 一致，直接用 task_type（如 connection）。"""
    return str(task_type or "").strip() or FileTagName.DEFAULT
