from pathlib import Path

from openpyxl import Workbook

from agent.skills.zhgk.steps.assess import _build_assessment_detail_groups


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
