"""本地 mock 文件降级（仅 DC 不可达时使用）。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from shared.datacenter import ipo_paths

_AIDA_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MOCK_ROOT = _AIDA_ROOT / "data" / "delivery" / "mock"
MOCK_ROOT = Path(os.environ.get("AIDA_MOCK_DATA_ROOT", str(_DEFAULT_MOCK_ROOT))).resolve()
_DEFAULT_MOCK_PROJECT = "JD2项目_test-boq"

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
    return p


def mock_logical_for_slot(slot: str, project_name: str, project_code: str | None) -> str:
    suffix = ipo_paths.slot_to_mock_suffix(slot)
    if slot == "raci_template":
        return suffix
    for folder in (project_name, project_code or "", _DEFAULT_MOCK_PROJECT):
        if not folder:
            continue
        candidate = ipo_paths.mock_logical_path(folder, suffix)
        if _resolve_path(candidate).is_file() or (
            slot == "acceptance_input" and (MOCK_ROOT / candidate.replace("\\", "/")).is_dir()
        ):
            return candidate
    return ipo_paths.mock_logical_path(_DEFAULT_MOCK_PROJECT, suffix)


def read_bytes(slot: str, project_name: str, project_code: str | None) -> tuple[bytes, str]:
    logical = mock_logical_for_slot(slot, project_name, project_code)
    path = _resolve_path(logical)
    if not path.is_file():
        raise FileNotFoundError(logical)
    return path.read_bytes(), logical


def write_bytes(logical_path: str, content: bytes) -> str:
    path = _resolve_path(logical_path)
    if path.is_dir():
        raise FileNotFoundError(logical_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return logical_path
