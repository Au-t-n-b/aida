"""
智慧工勘 v4 — 错误码注册表

格式: SS-{模块代码}-{E|W}-{序号}
"""

ERROR_REGISTRY: dict[str, dict] = {
    # ─── table_filter (TF) ───
    "SS-TF-E-001": {
        "message": "底表文件不存在",
        "suggestion": "检查 ProjectData/Template/入场评估标准表.xlsx 是否存在",
    },
    "SS-TF-E-002": {
        "message": "底表中 Sheet '入场评估标准' 不存在",
        "suggestion": "检查 Sheet 名称是否正确",
    },
    "SS-TF-E-003": {
        "message": "过滤结果为空，无匹配条目",
        "suggestion": "检查代际-制冷/分类/细分场景条件是否与底表数据匹配",
    },
    "SS-TF-E-004": {
        "message": "底表必要列缺失",
        "suggestion": "检查底表表头是否包含: 代际-制冷, 分类, 细分场景, 勘测要素, 检查内容",
    },

    # ─── boq_parser (BP) ───
    "SS-BP-E-001": {
        "message": "BOQ 文件不存在",
        "suggestion": "请用户上传 BOQ.xlsx 到 ProjectData/Input/ 目录",
    },
    "SS-BP-E-002": {
        "message": "BOQ 中未找到设备型号信息",
        "suggestion": "检查 BOQ 文件内容是否包含设备型号或产品名称",
    },
    "SS-BP-E-003": {
        "message": "无法从 BOQ 推断代际或制冷方式",
        "suggestion": "设备型号不在已知模式中，请用户手动指定",
    },

    # ─── project_meta (PM) ───
    "SS-PM-E-001": {
        "message": "projects.json 文件不存在或读取失败",
        "suggestion": "检查 registry/projects.json 路径是否正确",
    },
    "SS-PM-E-002": {
        "message": "projects.json 格式错误",
        "suggestion": "检查 JSON 格式是否合法",
    },

    # ─── session_memory (SM) ───
    "SS-SM-E-001": {
        "message": "记忆冲突未解决",
        "suggestion": "需要用户确认使用新值还是保持旧值",
    },

    # ─── survey_table_builder (ST) ───
    "SS-ST-E-001": {
        "message": "全量勘测结果表写入失败",
        "suggestion": "检查文件是否被其他程序锁定，或路径权限是否正确",
    },
    "SS-ST-E-002": {
        "message": "动态列扩展失败",
        "suggestion": "检查 Excel 文件结构是否被破坏",
    },
    "SS-ST-E-003": {
        "message": "模板文件不存在",
        "suggestion": "检查 ProjectData/Template/ 目录下模板文件",
    },

    # ─── assessment_engine (AE) ───
    "SS-AE-E-001": {
        "message": "LLM 调用超时或全部失败",
        "suggestion": "检查网络连接，或重试",
    },
    "SS-AE-E-002": {
        "message": "LLM 返回格式异常，无法解析为五值",
        "suggestion": "检查 Prompt 格式，或 LLM 服务是否正常",
    },
    "SS-AE-E-003": {
        "message": "评估结果写入 Excel 失败",
        "suggestion": "检查文件是否锁定",
    },

    # ─── issue_list_builder (IL) ───
    "SS-IL-E-001": {
        "message": "全量勘测结果表无 AI评估结果列",
        "suggestion": "需先执行评估流程",
    },
    "SS-IL-E-002": {
        "message": "LLM 生成问题描述失败",
        "suggestion": "重试或检查 LLM 服务",
    },
    "SS-IL-E-003": {
        "message": "问题清单文件写入失败",
        "suggestion": "检查输出目录权限",
    },

    # ─── risk_engine (RE) ───
    "SS-RE-E-001": {
        "message": "高风险库文件不存在",
        "suggestion": "检查 ProjectData/Template/工勘常见高风险库.xlsx",
    },
    "SS-RE-E-002": {
        "message": "LLM 风险判断失败",
        "suggestion": "重试或检查 LLM 服务",
    },
    "SS-RE-E-003": {
        "message": "风险结果表写入失败",
        "suggestion": "检查输出目录权限",
    },

    # ─── report_builder (RB) ───
    "SS-RB-E-001": {
        "message": "报告模板文件不存在",
        "suggestion": "检查 ProjectData/Template/ 下报告模板 .docx",
    },
    "SS-RB-E-002": {
        "message": "报告模板表格数量不匹配（期望9个）",
        "suggestion": "模板可能被修改，请使用标准模板",
    },
    "SS-RB-E-003": {
        "message": "占位符替换失败",
        "suggestion": "检查模板中占位符格式",
    },
    "SS-RB-E-004": {
        "message": "照片插入失败",
        "suggestion": "照片格式可能不支持，跳过该照片",
    },

    # ─── resurvey_manager (RM) ───
    "SS-RM-E-001": {
        "message": "复勘列扩展失败",
        "suggestion": "检查 Excel 文件是否被锁定",
    },
    "SS-RM-E-002": {
        "message": "文件不存在或锁定",
        "suggestion": "检查全量勘测结果表路径",
    },
    "SS-RM-E-003": {
        "message": "行号越界",
        "suggestion": "指定的行号超出表格范围",
    },

    # ─── email_service (EM) ───
    "SS-EM-E-001": {
        "message": "邮件发送失败",
        "suggestion": "检查收件人邮箱格式和网络连接",
    },

    # ─── driver (DR) ───
    "SS-DR-E-001": {
        "message": "意图识别失败",
        "suggestion": "引导用户使用意图卡片或输入更明确的指令",
    },
    "SS-DR-E-002": {
        "message": "流程执行异常",
        "suggestion": "查看 exec_log.json 详细日志",
    },
}


def get_error_info(code: str) -> dict:
    """根据错误码获取详细信息。"""
    return ERROR_REGISTRY.get(code, {"message": "未知错误", "suggestion": "查看日志"})
