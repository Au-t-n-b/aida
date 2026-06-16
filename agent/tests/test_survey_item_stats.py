"""底表条目统计单测。"""
from __future__ import annotations

from openpyxl import Workbook

from agent.skills.zhgk.services.survey_item_stats import compute_survey_item_stats


def _write_mini_base_table(path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "入场评估标准"
    headers = ["序号", "代际-制冷", "分类", "细分场景", "勘测要素", "项目", "检查内容", "勘测方法"]
    ws.append(headers)
    rows = [
        (1, "A3-液冷", "标准", "硬装入场", "机柜", "项目A", "检查A", "现场"),
        (2, "A3-液冷", "标准", "通液前", "管路", "项目B", "检查B", "现场"),
        (3, "A3-液冷", "数据", "通液前", "数据项", "项目C", "检查C", "数据"),
        (4, "A2-风冷", "标准", "硬装入场", "机柜", "项目D", "检查D", "现场"),
    ]
    for row in rows:
        ws.append(row)
    wb.save(path)


def test_compute_survey_item_stats_base_only(monkeypatch, tmp_path):
    table = tmp_path / "入场评估标准表.xlsx"
    _write_mini_base_table(table)
    monkeypatch.setattr(
        "agent.skills.zhgk.path_config.get_base_table_path",
        lambda: str(table),
    )

    stats = compute_survey_item_stats(None)
    assert stats["base_table_count"] == 4
    assert "filtered_count" not in stats


def test_compute_survey_item_stats_filtered_preview(monkeypatch, tmp_path):
    table = tmp_path / "入场评估标准表.xlsx"
    _write_mini_base_table(table)
    monkeypatch.setattr(
        "agent.skills.zhgk.path_config.get_base_table_path",
        lambda: str(table),
    )

    stats = compute_survey_item_stats("A3-液冷")
    assert stats["base_table_count"] == 4
    assert stats["filtered_count"] == 2
    assert stats["sub_scenes"] == ["硬装入场", "通液前", "加电前"]
    assert len(stats["preview_rows"]) == 2
