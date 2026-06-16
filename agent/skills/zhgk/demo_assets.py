"""
zhgk 演示资产路径约定。

- mock 工勘报告：随项目 demo 数据走（data/projects/{project_id}/…），push 到 Gitea 时一并入库。
- 入场评估标准表 / 工勘常见高风险库：组织资产，运行时由用户在 filter_build HITL 自行上传。
"""
from __future__ import annotations

import shutil
from pathlib import Path

# 本地联调默认演示项目（与 data/projects/ 下 mock 目录一致）
DEFAULT_DEMO_PROJECT_ID = "70e5ca737ae5433e9f0f3134d216acf7"

MOCK_REPORT_FILENAME = "本地工勘报告.pdf"
ROOM_RACK_FILENAME = "机房机柜信息表.xlsx"
SURVEY_INPUT_REL = Path("交付作业") / "智慧工勘" / "输入文件"
TWIN_ROOM_RACK_REL = (
    Path("孪生世界") / "算力底座孪生" / "输出结果" / "机房机柜信息表"
)
SURVEY_OUTPUT_REL = Path("交付作业") / "智慧工勘" / "输出结果"

_AGENT_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = _AGENT_DIR.parent
LEGACY_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / MOCK_REPORT_FILENAME


def project_data_root(repo_root: Path, project_id: str) -> Path:
    return repo_root / "data" / "projects" / project_id


def mock_report_project_path(
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
) -> Path:
    root = repo_root or REPO_ROOT
    return project_data_root(root, project_id) / SURVEY_INPUT_REL / MOCK_REPORT_FILENAME


def mock_report_manifest_path(
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
) -> Path:
    return mock_report_project_path(repo_root, project_id).parent / "manifest.json"


def room_rack_project_path(
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
) -> Path:
    root = repo_root or REPO_ROOT
    return project_data_root(root, project_id) / TWIN_ROOM_RACK_REL / ROOM_RACK_FILENAME


def room_rack_manifest_path(
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
) -> Path:
    return room_rack_project_path(repo_root, project_id).parent / "manifest.json"


def survey_output_project_dir(
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
) -> Path:
    root = repo_root or REPO_ROOT
    return project_data_root(root, project_id) / SURVEY_OUTPUT_REL


def resolve_room_rack_xlsx(
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
) -> Path | None:
    """项目孪生输出优先。"""
    project_xlsx = room_rack_project_path(repo_root, project_id)
    if project_xlsx.is_file():
        return project_xlsx
    return None


def resolve_mock_report_source(
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
) -> Path | None:
    """项目演示资产优先，旧 skill fixture 兜底。"""
    project_pdf = mock_report_project_path(repo_root, project_id)
    if project_pdf.is_file():
        return project_pdf
    if LEGACY_FIXTURE_PATH.is_file():
        return LEGACY_FIXTURE_PATH
    return None


def seed_mock_report_to_workspace(
    workspace_input_dir: Path,
    *,
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
) -> Path | None:
    """将项目演示 PDF 复制到 ZHGK_ROOT/ProjectData/Input/，供 report_gen_run 读取。"""
    src = resolve_mock_report_source(repo_root, project_id)
    if src is None:
        return None
    workspace_input_dir.mkdir(parents=True, exist_ok=True)
    dest = workspace_input_dir / MOCK_REPORT_FILENAME
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest
