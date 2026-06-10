"""zhgk skill 的 prompt 模板集 · 抽离便于 Langfuse trace 命名 + 版本管理"""

ASSESSMENT_SYSTEM = "你是数据中心机房工勘评估专家。请按要求输出严格 JSON。"

ASSESSMENT_USER = """请对以下"检查内容及要求"给出评估结论与缺陷记录。

检查内容及要求：{check}

输出 JSON：{{"conclusion": "满足|不满足|无法识别|不涉及", "defect": "缺陷记录（若满足/不涉及可为空）"}}
只输出 JSON，不要输出其它文本。"""


RISK_SYSTEM = "你是数据中心机房工勘风险评估专家。"

RISK_USER = """风险描述：{risk_desc}
触发条件：{trigger}
现场数据：{site_summary}

请判断该风险是否在本项目机房成立。输出 JSON：
{{"hit": true|false, "level": "高|中|低", "evidence": "证据描述（不超过 80 字）"}}
只输出 JSON。"""
