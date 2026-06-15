"""本地 mock 文件降级（仅 DC 不可达时使用）。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from shared.datacenter import ipo_paths

_AIDA_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MOCK_ROOT = _AIDA_ROOT / "data" / "delivery" / "mock"
MOCK_ROOT = Path(os.environ.get("AIDA_MOCK_DATA_ROOT", str(_DEFAULT_MOCK_ROOT))).resolve()
DEFAULT_MOCK_PROJECT = "mock_project"
_DEFAULT_MOCK_PROJECT = DEFAULT_MOCK_PROJECT

# 交付预案输出表：草稿期可能尚未保存到数据中心，缺失不算错误
OPTIONAL_OUTPUT_SLOTS = frozenset({"raci_out", "acceptance_out", "testcases_out"})

_INPUT_DIR_SUFFIXES = (".docx", ".xlsx", ".xlsm", ".md", ".pdf", ".pptx")


def _resolve_path(logical_path: str) -> Path:
    p = (MOCK_ROOT / logical_path.replace("\\", "/")).resolve()
    try:
        p.relative_to(MOCK_ROOT.resolve())
    except ValueError as e:
        raise FileNotFoundError("path outside mock root") from e
    if p.is_dir():
        for suffix in _INPUT_DIR_SUFFIXES:
            matches = sorted(p.glob(f"*{suffix}"))
            if matches:
                return matches[0].resolve()
        raise FileNotFoundError(f"no readable file in directory: {logical_path}")
    if not p.is_file():
        raise FileNotFoundError(logical_path)
    return p


def resolve_mock_path(logical_path: str) -> Path:
    """逻辑路径 → mock 根下物理文件（目录则取首个可读文件）。"""
    return _resolve_path(logical_path)


def is_under_mock_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(MOCK_ROOT.resolve())
        return True
    except ValueError:
        return False


def mock_physical_path_for_dc_logical(
    dc_logical: str,
    project_name: str,
    project_code: str | None,
) -> Path:
    """数据中心 logicalPath（无项目前缀）→ mock 物理路径。"""
    normalized = dc_logical.replace("\\", "/").strip("/")
    if not normalized:
        raise ValueError("empty logical path")
    if normalized.startswith("组织资产/"):
        target = (MOCK_ROOT / normalized).resolve()
    else:
        folder = project_name or project_code or _DEFAULT_MOCK_PROJECT
        target = (MOCK_ROOT / folder / normalized).resolve()
    try:
        target.relative_to(MOCK_ROOT.resolve())
    except ValueError as e:
        raise FileNotFoundError("path outside mock root") from e
    return target


def save_dc_download(
    dc_logical: str,
    content: bytes,
    project_name: str,
    project_code: str | None,
) -> Path:
    """将数据中心下载内容落盘到 data/delivery/mock 对应目录。"""
    path = mock_physical_path_for_dc_logical(dc_logical, project_name, project_code)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def local_logical_candidates(
    slot: str,
    project_name: str,
    project_code: str | None,
) -> list[str]:
    """按固定 IPO 目录返回候选逻辑路径（优先当前项目名）。"""
    suffix = ipo_paths.slot_to_mock_suffix(slot)
    if slot == "raci_template":
        return [suffix]
    candidates: list[str] = []
    for folder in (project_code or "", project_name, _DEFAULT_MOCK_PROJECT):
        if folder:
            candidates.append(ipo_paths.mock_logical_path(folder, suffix))
    return candidates


def try_resolve_mock_project_slot(slot: str) -> tuple[Path, str] | None:
    """从 mock_project 固定目录查找 slot 对应文件。"""
    suffix = ipo_paths.slot_to_mock_suffix(slot)
    if slot == "raci_template":
        logical = suffix
    else:
        logical = ipo_paths.mock_logical_path(DEFAULT_MOCK_PROJECT, suffix)
    try:
        path = resolve_mock_path(logical)
        if path.is_file():
            return path, logical
    except FileNotFoundError:
        pass
    return None


def try_resolve_local_slot(
    slot: str,
    project_name: str,
    project_code: str | None,
) -> tuple[Path, str] | None:
    """本地 mock 是否已有可读文件；有则返回 (物理路径, 逻辑路径)。"""
    for logical in local_logical_candidates(slot, project_name, project_code):
        try:
            path = resolve_mock_path(logical)
            if path.is_file():
                return path, logical
        except FileNotFoundError:
            continue
    # 目录型 slot（技术建议书）：目录存在且含文件即可
    if slot == "acceptance_input":
        for logical in local_logical_candidates(slot, project_name, project_code):
            dir_path = MOCK_ROOT / logical.replace("\\", "/")
            if dir_path.is_dir() and any(dir_path.iterdir()):
                try:
                    path = resolve_mock_path(logical)
                    if path.is_file():
                        return path, logical
                except FileNotFoundError:
                    continue
    return try_resolve_mock_project_slot(slot)


def mock_logical_for_slot(slot: str, project_name: str, project_code: str | None) -> str:
    suffix = ipo_paths.slot_to_mock_suffix(slot)
    if slot == "raci_template":
        return suffix
    for folder in (project_code or "", project_name, _DEFAULT_MOCK_PROJECT):
        if not folder:
            continue
        candidate = ipo_paths.mock_logical_path(folder, suffix)
        try:
            path = _resolve_path(candidate)
            if path.is_file():
                return candidate
        except FileNotFoundError:
            if slot == "acceptance_input" and (MOCK_ROOT / candidate.replace("\\", "/")).is_dir():
                return candidate
            continue
    return ipo_paths.mock_logical_path(_DEFAULT_MOCK_PROJECT, suffix)


def read_bytes(slot: str, project_name: str, project_code: str | None) -> tuple[bytes, str]:
    logical = mock_logical_for_slot(slot, project_name, project_code)
    path = _resolve_path(logical)
    if not path.is_file():
        raise FileNotFoundError(logical)
    return path.read_bytes(), logical


def write_bytes(logical_path: str, content: bytes) -> str:
    """写入 mock 逻辑路径（不存在则创建父目录与文件）。"""
    p = (MOCK_ROOT / logical_path.replace("\\", "/")).resolve()
    try:
        p.relative_to(MOCK_ROOT.resolve())
    except ValueError as e:
        raise FileNotFoundError("path outside mock root") from e
    if p.is_dir():
        raise FileNotFoundError(logical_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return logical_path
