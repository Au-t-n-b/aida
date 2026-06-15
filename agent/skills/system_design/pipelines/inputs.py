"""输入件配置 · 系统设计必需输入件（移植自 a3 FILE_CONFIG + runtime BASE_REQUIRED_INPUTS）。

扫描目录按 project_paths.json → read.scan_by_tag 分 tag 配置（绝对路径）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .path_manifest import INPUT_TAGS, abs_upload_dir, read_scan_dir_for_tag, read_scan_dirs

INPUT_DIR_CANDIDATES = [str(p) for p in read_scan_dirs()]

FILE_CONFIG: dict[str, dict[str, Any]] = {
    "resource": {
        "label": "项目信息收集表",
        "keywords": ["项目信息收集", "资源需求", "资源表"],
        "from_simulation": False,
        "extensions": [".xlsx", ".xls", ".xlsm"],
    },
    "Interconnection_Relationship": {
        "label": "端口连线表(007)",
        "keywords": ["007", "端口连线", "端口互联"],
        "from_simulation": True,
    },
    "Device_Info": {
        "label": "设备信息表(001)",
        "keywords": ["001", "设备信息"],
        "from_simulation": True,
    },
    "Location_Information": {
        "label": "设备位置表(004)",
        "keywords": ["004", "设备位置"],
        "from_simulation": True,
    },
    "Test_Case": {
        "label": "测试用例",
        "keywords": ["测试用例", "008", "验收用例", "验收"],
        "from_simulation": True,
        "extensions": [".xlsx", ".xls", ".doc", ".docx"],
    },
}

REQUIRED_DEFAULT: list[str] = [
    "resource",
    "Interconnection_Relationship",
    "Device_Info",
    "Location_Information",
]

PLANNING_REQUIRED: list[str] = ["Interconnection_Relationship", "resource"]


@dataclass
class InputFoundEntry:
    tag: str
    label: str
    path: Path


def label_of(tag: str) -> str:
    return FILE_CONFIG.get(tag, {}).get("label", tag)


def _scan_tag_in_dir(tag: str, directory: Path) -> InputFoundEntry | None:
    cfg = FILE_CONFIG.get(tag)
    if not cfg or not directory.is_dir():
        return None
    allowed = tuple(cfg.get("extensions") or [".xlsx", ".xls"])
    for f in sorted(directory.iterdir()):
        if f.name.startswith("~$") or not f.is_file():
            continue
        if f.suffix.lower() not in allowed:
            continue
        if any(kw in f.name for kw in cfg["keywords"]):
            return InputFoundEntry(tag=tag, label=cfg["label"], path=f)
    return None


def collect_inputs(work_root: Any = None) -> dict[str, InputFoundEntry]:
    """按 tag 扫描各自目录，返回 {tag: InputFoundEntry}（只含已找到的）。

    仿真三表(007/001/004)/测试用例正常由建模仿真落 jmfz/ht；但用户在「输入件准备」
    HITL 槽位手动补传时统一落 upload 目录(input)。故每个 tag 在其主扫描目录未命中时，
    再回扫 upload 目录——保证手动补传的任意输入件都能被识别、刷新交付流程状态。"""
    _ = work_root
    found: dict[str, InputFoundEntry] = {}
    upload_dir = abs_upload_dir()
    for tag in INPUT_TAGS:
        if tag not in FILE_CONFIG:
            continue
        scan_dir = read_scan_dir_for_tag(tag)
        entry = _scan_tag_in_dir(tag, scan_dir)
        if entry is None and upload_dir != scan_dir:
            entry = _scan_tag_in_dir(tag, upload_dir)
        if entry is not None:
            found[tag] = entry
    return found


def missing_required(
    found: dict[str, InputFoundEntry],
    required: list[str] | None = None,
) -> list[str]:
    req = required if required is not None else REQUIRED_DEFAULT
    return [t for t in req if t not in found]
