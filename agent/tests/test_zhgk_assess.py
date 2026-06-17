from pathlib import Path

from openpyxl import Workbook

from agent.skills.zhgk.services.assessment_engine import _parse_response
from agent.skills.zhgk.steps.assess import _build_assessment_detail_groups


def test_parse_response_plain_json():
    result = _parse_response('{"conclusion": "满足", "defect": ""}')
    assert result.conclusion.value == "满足"
    assert result.defect_description == ""


def test_parse_response_strips_redacted_thinking_block():
    response = (
        '<think>让我分析这个任务：\n'
        "检查内容：楼内运输走廊最窄宽度不低于1.5m\n"
        "检查结果：沿途最窄处1.62m，满足运输要求。\n"
        '结论：满足要求</think>\n\n'
        '{"conclusion":"满足","defect":""}'
    )
    result = _parse_response(response)
    assert result.conclusion.value == "满足"


def test_parse_response_strips_markdown_fence():
    response = '```json\n{"conclusion": "不满足", "defect": "温度超标"}\n```'
    result = _parse_response(response)
    assert result.conclusion.value == "不满足"
    assert result.defect_description == "温度超标"


def test_build_assessment_detail_groups_reads_survey_rows(tmp_path: Path):
    path = tmp_path / "全量勘测结果表.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["序号", "检查内容", "最新检查结果", "最新结果来源", "最新勘测时间", "AI评估结果", "风险描述"])
    ws.append([1, "冷通道封闭完整", "已封闭", "第1次视频工勘", "2026-06-14 17:30:00", "满足", ""])
    ws.append([2, "温湿度监控可用", "", "第1次手动上传", "2026-06-14 17:35:00", "未勘测", "缺少采集数据"])
    wb.save(path)

    groups = _build_assessment_detail_groups(str(path))

    assert groups["满足"] == [
        {
            "item": "冷通道封闭完整",
            "result": "已封闭",
            "source": "第1次视频工勘",
            "time": "2026-06-14 17:30:00",
            "risk": "",
        }
    ]
    assert groups["未勘测"] == [
        {
            "item": "温湿度监控可用",
            "result": "",
            "source": "第1次手动上传",
            "time": "2026-06-14 17:35:00",
            "risk": "缺少采集数据",
        }
    ]
