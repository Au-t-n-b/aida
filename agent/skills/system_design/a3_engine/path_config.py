# -*- coding: utf-8 -*-
"""A3 智能网络开局 — 全局路径真值（绝对路径见 ../project_paths.json）。"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from agent.skills.system_design.pipelines.path_manifest import (
        abs_artifacts_dir,
        abs_input_dir,
        abs_upload_dir,
        ensure_parent_dir,
        resolve_data_root,
    )
except ImportError:
    _ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent / "workspace" / "a3-project"

    def resolve_data_root() -> Path:
        return _ROOT.resolve()

    def abs_input_dir() -> Path:
        return _ROOT / "input"

    def abs_upload_dir() -> Path:
        return abs_input_dir()

    def abs_artifacts_dir() -> Path:
        return _ROOT / "output"

    def ensure_parent_dir(path: Path | str) -> None:
        Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)

BASE = os.path.dirname(os.path.abspath(__file__))
SUBSKILLS_DIR = os.path.join(BASE, "subskills")

ORCHESTRATOR_DIR = os.path.join(SUBSKILLS_DIR, "lld-dispatch-orchestrator.code1")
L3_INDEX_REL = "lld-dispatch-orchestrator.code1/l3_skill_index.yaml"
DISPATCH_TREE_REL = "lld-dispatch-orchestrator.code1/dispatch_tree.yaml"

_DATA_ROOT = resolve_data_root()
INPUT_DIR = str(abs_input_dir())
UPLOAD_DIR = str(abs_upload_dir())
OUTPUT_DIR = str(abs_artifacts_dir())
# 兼容 vendored 子 skill 常量名；与 output 同根，不再单独 runtime 目录
RUNTIME_DIR = OUTPUT_DIR


def ensure_dirs() -> None:
    return


def skill_root_path() -> Path:
    return Path(BASE)


def refresh_data_root() -> None:
    global _DATA_ROOT, INPUT_DIR, UPLOAD_DIR, RUNTIME_DIR, OUTPUT_DIR
    _DATA_ROOT = resolve_data_root()
    INPUT_DIR = str(abs_input_dir())
    UPLOAD_DIR = str(abs_upload_dir())
    OUTPUT_DIR = str(abs_artifacts_dir())
    RUNTIME_DIR = OUTPUT_DIR
