"""zhgk 演示资产：mock 报告随项目，底表不打包。"""
from __future__ import annotations

from pathlib import Path

from agent.skills.zhgk.demo_assets import (
    DEFAULT_DEMO_PROJECT_ID,
    mock_report_project_path,
    room_rack_project_path,
    seed_mock_report_to_workspace,
)


def test_mock_report_project_path_layout() -> None:
    business = Path("/opt/aida/aida-data/business")
    p = mock_report_project_path(DEFAULT_DEMO_PROJECT_ID, business_root=business)
    assert p == Path(
        "/opt/aida/aida-data/business/projects/70e5ca737ae5433e9f0f3134d216acf7/"
        "交付作业/智慧工勘/输入文件/本地工勘报告.pdf"
    )


def test_room_rack_project_path_layout() -> None:
    business = Path("/opt/aida/aida-data/business")
    p = room_rack_project_path(DEFAULT_DEMO_PROJECT_ID, business_root=business)
    assert p == Path(
        "/opt/aida/aida-data/business/projects/70e5ca737ae5433e9f0f3134d216acf7/"
        "孪生世界/算力底座孪生/输出结果/机房机柜信息表/机房机柜信息表.xlsx"
    )


def test_seed_mock_report_from_project_asset(tmp_path: Path) -> None:
    business = tmp_path / "business"
    project_pdf = mock_report_project_path(DEFAULT_DEMO_PROJECT_ID, business_root=business)
    project_pdf.parent.mkdir(parents=True, exist_ok=True)
    project_pdf.write_bytes(b"%PDF-demo")

    dest = seed_mock_report_to_workspace(
        tmp_path / "workspace" / "Input",
        project_id=DEFAULT_DEMO_PROJECT_ID,
        business_root=business,
    )
    assert dest is not None
    assert dest.name == "本地工勘报告.pdf"
    assert dest.read_bytes() == b"%PDF-demo"
