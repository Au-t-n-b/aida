"""发布收尾辅助 · 对齐设计稿 request_test_check（验收用例拷贝到关键输出件）。"""
from __future__ import annotations

import shutil
from pathlib import Path

from .a3_paths import get_a3_data_root
from .inputs import collect_inputs
from .path_manifest import abs_artifacts_dir, ensure_parent_dir, relpath_from_data_root

TEST_CASE_ARTIFACT_ID = "art-testcase"


def _output_dir(work_root: Path | None = None) -> Path:
    _ = work_root
    return abs_artifacts_dir()


def resolve_test_case_input(work_root: Path | str | None = None) -> Path | None:
    """从 Input/Output 扫描验收用例/测试用例输入件。"""
    root = Path(work_root).resolve() if work_root else get_a3_data_root()
    found = collect_inputs(root)
    f = found.get("Test_Case")
    return f.path if f and f.path.is_file() else None


def copy_test_case_to_output(work_root: Path | str | None = None) -> Path | None:
    """将输入件中的测试/验收用例拷贝到 output 产物目录（幂等）。"""
    src = resolve_test_case_input(work_root)
    if src is None:
        return None
    dest = _output_dir(work_root) / src.name
    ensure_parent_dir(dest)
    if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, dest)
    return dest


def output_rel_path(work_root: Path | str, abs_path: Path | str) -> str:
    """绝对路径 → 相对 data_root 的产物路径（供 state.files / artifact 预览）。"""
    _ = work_root
    return relpath_from_data_root(abs_path)
