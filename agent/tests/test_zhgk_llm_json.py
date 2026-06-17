from agent.skills.zhgk.services.issue_list_builder import _generate_issue
from agent.skills.zhgk.services.llm_json import extract_json_from_llm_response


def test_extract_json_from_redacted_thinking():
    response = (
        '<think>分析问题...</think>\n\n'
        '{"problem_description": "温度超标", "remediation_suggestion": "调整空调"}'
    )
    data = extract_json_from_llm_response(response)
    assert data["problem_description"] == "温度超标"
    assert data["remediation_suggestion"] == "调整空调"


def test_generate_issue_parses_thinking_wrapped_json():
    def fake_llm(_system: str, _user: str) -> str:
        return (
            '<think>生成问题描述...</think>\n\n'
            '{"problem_description": "防火门宽度不足", "remediation_suggestion": "更换合规防火门"}'
        )

    result = _generate_issue(
        {
            "check_content": "机房防火门宽度不小于1.2m",
            "latest_result": "净宽1.18m",
            "assessment": "不满足",
        },
        fake_llm,
    )
    assert result.problem_description == "防火门宽度不足"
    assert result.remediation_suggestion == "更换合规防火门"
