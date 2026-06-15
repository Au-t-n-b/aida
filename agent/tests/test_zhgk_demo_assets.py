"""zhgk 演示资产：mock 报告随项目，底表不打包。"""
from __future__ import annotations

from pathlib import Path

from agent.skills.zhgk.demo_assets import (
    DEFAULT_DEMO_PROJECT_ID,
    mock_report_project_path,
    seed_mock_report_to_workspace,
)


def test_mock_report_project_path_layout() -> None:
    p = mock_report_project_path(Path("/repo"), DEFAULT_DEMO_PROJECT_ID)
    assert p == Path(
        "/repo/data/projects/70e5ca737ae5433e9f0f3134d216acf7/"
        "交付作业/智慧工勘/输入文件/本地工勘报告.pdf"
    )


def test_seed_mock_report_from_project_asset(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    project_pdf = mock_report_project_path(repo, DEFAULT_DEMO_PROJECT_ID)
    project_pdf.parent.mkdir(parents=True, exist_ok=True)
    project_pdf.write_bytes(b"%PDF-demo")

    dest = seed_mock_report_to_workspace(
        tmp_path / "workspace" / "Input",
        repo_root=repo,
        project_id=DEFAULT_DEMO_PROJECT_ID,
    )
    assert dest is not None
    assert dest.name == "本地工勘报告.pdf"
    assert dest.read_bytes() == b"%PDF-demo"
