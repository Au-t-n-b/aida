"""A3 路径解析 · 代码根（vendored）与数据根（project_paths.json 绝对路径）解耦。"""
from __future__ import annotations

import os
from pathlib import Path

from .path_manifest import abs_input_dir, resolve_data_root

_CODE_ROOT = (Path(__file__).resolve().parent.parent / "a3_engine")


def get_a3_code_root() -> Path:
    raw = os.environ.get("A3_CODE_ROOT", "").strip()
    return Path(raw).resolve() if raw else _CODE_ROOT.resolve()


def get_a3_data_root() -> Path:
    return resolve_data_root()


def get_a3_root() -> Path:
    return get_a3_data_root()


def get_subskills_root() -> Path:
    return get_a3_code_root() / "subskills"


def get_runtime_root() -> Path:
    return get_a3_code_root() / "runtime"


def get_input_dir(work_root: Path | None = None) -> Path:
    """输入件目录（project_paths.json 绝对路径；work_root 参数保留兼容，不再参与拼接）。"""
    _ = work_root
    return abs_input_dir()


_DEFAULT_DATA_ROOT = resolve_data_root()
