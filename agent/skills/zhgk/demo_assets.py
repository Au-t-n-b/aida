"""
zhgk 演示资产路径约定。

- mock 工勘报告：随项目 demo 数据走（{AIDA_BUSINESS_ROOT}/projects/{project_id}/…）。
- 入场评估标准表 / 工勘常见高风险库：组织资产，运行时由用户在 filter_build HITL 自行上传。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from agent.config import BUSINESS_ROOT

# 本地联调默认演示项目（与 business/projects/ 下 mock 目录一致）
DEFAULT_DEMO_PROJECT_ID = "70e5ca737ae5433e9f0f3134d216acf7"

MOCK_REPORT_FILENAME = "本地工勘报告.pdf"
ROOM_RACK_FILENAME = "机房机柜信息表.xlsx"
SURVEY_INPUT_REL = Path("交付作业") / "智慧工勘" / "输入文件"
# 物理：{business}/projects/{id}/孪生世界/算力底座孪生/输出结果/机房机柜信息表.xlsx
TWIN_ROOM_RACK_OUTPUT_REL = Path("孪生世界") / "算力底座孪生" / "输出结果"
# 旧版嵌套目录（本地 demo 可能仍存在）
TWIN_ROOM_RACK_LEGACY_DIR = TWIN_ROOM_RACK_OUTPUT_REL / "机房机柜信息表"
SURVEY_OUTPUT_REL = Path("交付作业") / "智慧工勘" / "输出结果"

LEGACY_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / MOCK_REPORT_FILENAME


def project_data_root(
    project_id: str,
    *,
    business_root: Path | None = None,
) -> Path:
    """项目物理根：{AIDA_BUSINESS_ROOT}/projects/{project_id}/"""
    root = business_root or BUSINESS_ROOT
    return root / "projects" / project_id


def mock_report_project_path(
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    *,
    business_root: Path | None = None,
) -> Path:
    return project_data_root(project_id, business_root=business_root) / SURVEY_INPUT_REL / MOCK_REPORT_FILENAME


def mock_report_manifest_path(
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    *,
    business_root: Path | None = None,
) -> Path:
    return mock_report_project_path(project_id, business_root=business_root).parent / "manifest.json"


def room_rack_project_path(
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    *,
    business_root: Path | None = None,
) -> Path:
    base = project_data_root(project_id, business_root=business_root)
    return base / TWIN_ROOM_RACK_OUTPUT_REL / ROOM_RACK_FILENAME


def room_rack_legacy_project_path(
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    *,
    business_root: Path | None = None,
) -> Path:
    base = project_data_root(project_id, business_root=business_root)
    return base / TWIN_ROOM_RACK_LEGACY_DIR / ROOM_RACK_FILENAME


def room_rack_manifest_path(
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    *,
    business_root: Path | None = None,
) -> Path:
    return room_rack_project_path(project_id, business_root=business_root).parent / "manifest.json"


def survey_output_project_dir(
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    *,
    business_root: Path | None = None,
) -> Path:
    return project_data_root(project_id, business_root=business_root) / SURVEY_OUTPUT_REL


def resolve_room_rack_xlsx(
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    *,
    business_root: Path | None = None,
) -> Path | None:
    """项目孪生输出：输出结果/机房机柜信息表.xlsx；旧版嵌套子目录兜底。"""
    for candidate in (
        room_rack_project_path(project_id, business_root=business_root),
        room_rack_legacy_project_path(project_id, business_root=business_root),
    ):
        if candidate.is_file():
            return candidate
    return None


def resolve_mock_report_source(
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    *,
    business_root: Path | None = None,
) -> Path | None:
    """项目演示资产优先，旧 skill fixture 兜底。"""
    project_pdf = mock_report_project_path(project_id, business_root=business_root)
    if project_pdf.is_file():
        return project_pdf
    if LEGACY_FIXTURE_PATH.is_file():
        return LEGACY_FIXTURE_PATH
    return None


def seed_mock_report_to_workspace(
    workspace_input_dir: Path,
    *,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    business_root: Path | None = None,
) -> Path | None:
    """将项目演示 PDF 复制到 ZHGK_ROOT/ProjectData/Input/，供 report_gen_run 读取。"""
    src = resolve_mock_report_source(project_id, business_root=business_root)
    if src is None:
        return None
    workspace_input_dir.mkdir(parents=True, exist_ok=True)
    dest = workspace_input_dir / MOCK_REPORT_FILENAME
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest
