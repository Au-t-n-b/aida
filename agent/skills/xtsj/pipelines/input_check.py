"""input_check pipeline · 进程内移植 a3 offline_input_components_pipeline.py。

原始逻辑：扫描 ProjectData/Input 目录，按 FILE_CONFIG 中的标准文件名
识别已就绪的输入件，对缺失的必需件打标。
不用 subprocess、不用 pandas（dataclass 替代），符合 AGENTS.md 铁律。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── 输入件目录名（a3 ProjectData/Input 或 jmfz 兼容路径）────────────────────
INPUT_DIR_CANDIDATES = ["ProjectData/Input", "Input", ""]

# ── 标准文件配置（tag → label + filename · 与 a3 FILE_CONFIG 对齐）──────────
FILE_CONFIG: dict[str, dict[str, str]] = {
    "Device_Info": {
        "label": "设备信息概览",
        "filename": "建模仿真输出文档001-设备信息表.xlsx",
    },
    "Location_Information": {
        "label": "设备位置信息",
        "filename": "建模仿真输出文档004-设备位置表.xlsx",
    },
    "Interconnection_Relationship": {
        "label": "端口互联关系",
        "filename": "建模仿真输出文档007-端口连线表.xlsx",
    },
}

# 默认必需件（系统设计必须有全部三件才能运转）
REQUIRED_DEFAULT: list[str] = list(FILE_CONFIG.keys())


@dataclass
class InputFoundEntry:
    tag: str
    label: str
    path: Path


def label_of(tag: str) -> str:
    """返回 tag 的中文展示名；未知 tag 原样返回。"""
    return FILE_CONFIG.get(tag, {}).get("label", tag)


def _resolve_input_dir(work_root: Path) -> Path | None:
    """在 work_root 下找可用的输入件目录，依优先级尝试。"""
    for candidate in INPUT_DIR_CANDIDATES:
        d = (work_root / candidate) if candidate else work_root
        if d.is_dir():
            return d
    return None


def collect_inputs(work_root: Any) -> dict[str, InputFoundEntry]:
    """扫描 work_root 下标准输入件，返回 {tag: InputFoundEntry}（只含已找到的）。

    work_root 可为 str / Path；不存在则返回空 dict（不 raise，供 SkillRegistry 懒加载）。
    """
    root = Path(work_root) if not isinstance(work_root, Path) else work_root
    if not root.exists():
        return {}

    input_dir = _resolve_input_dir(root)
    if input_dir is None:
        return {}

    found: dict[str, InputFoundEntry] = {}
    for tag, cfg in FILE_CONFIG.items():
        candidate = input_dir / cfg["filename"]
        if candidate.is_file():
            found[tag] = InputFoundEntry(tag=tag, label=cfg["label"], path=candidate)
    return found


def missing_required(
    found: dict[str, InputFoundEntry],
    required: list[str] | None = None,
) -> list[str]:
    """返回 required 中未在 found 里的 tag 列表（默认用 REQUIRED_DEFAULT）。"""
    req = required if required is not None else REQUIRED_DEFAULT
    return [t for t in req if t not in found]
