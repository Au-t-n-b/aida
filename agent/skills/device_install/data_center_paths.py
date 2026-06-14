"""
data_center_paths · 按业务数据规范推导项目级物理路径。

逻辑路径 → 物理路径（§1.3）：
  {AIDA_BUSINESS_ROOT}/projects/{project_id}/ + path_config._REL_PLAN_UPSTREAM  ← 上游 xlsx
  {AIDA_BUSINESS_ROOT}/projects/{project_id}/交付作业/设备安装                   ← skill 工作根
  {AIDA_BUSINESS_ROOT}/projects/{project_id}/ + path_config._REL_INSTALL_OUTPUT ← 作业产物
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .path_config import (
    SERVER_BUSINESS_ROOT as _LINUX_DEFAULT_BUSINESS_ROOT,
    SERVER_PROJECT_ID as DEFAULT_SERVER_PROJECT_ID,
    _REL_INSTALL_OUTPUT,
    _REL_PLAN_UPSTREAM,
)

_REL_SOURCE = _REL_PLAN_UPSTREAM
_REL_WORK = Path("交付作业") / "设备安装"
_REL_OUTPUT = _REL_INSTALL_OUTPUT


def get_business_root() -> Path | None:
    """数据中心业务根目录。优先 AIDA_BUSINESS_ROOT，其次 Linux 默认 /opt/aida/...。"""
    raw = os.environ.get("AIDA_BUSINESS_ROOT", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_dir() else None
    if _LINUX_DEFAULT_BUSINESS_ROOT.is_dir():
        return _LINUX_DEFAULT_BUSINESS_ROOT
    return None


def resolve_project_id(project: dict[str, Any] | None = None) -> str:
    """从 run project 或 AIDA_DEFAULT_PROJECT_ID 解析 project_id（UUID32）。

    Linux 服务器（business 根存在）且未显式指定时，回退 DEFAULT_SERVER_PROJECT_ID。
    """
    if project:
        for key in ("project_id", "project_code"):
            v = str(project.get(key) or "").strip()
            if v:
                return v
    env = os.environ.get("AIDA_DEFAULT_PROJECT_ID", "").strip()
    if env:
        return env
    if get_business_root() is not None:
        return DEFAULT_SERVER_PROJECT_ID
    return ""


def project_base(project: dict[str, Any] | None = None) -> Path | None:
    root = get_business_root()
    pid = resolve_project_id(project)
    if not root or not pid:
        return None
    return root / "projects" / pid


def get_dc_upstream_input_dir(project: dict[str, Any] | None = None) -> Path | None:
    """上游 xlsx 目录（交付计划表 / 设备位置表 / 到货信息表）。"""
    base = project_base(project)
    return (base / _REL_PLAN_UPSTREAM) if base else None


def get_dc_source_dir(project: dict[str, Any] | None = None) -> Path | None:
    """《设备安装实施计划》上游源目录（与 upstream input 同层，plan_receive 专用）。"""
    return get_dc_upstream_input_dir(project)


def get_dc_work_root(project: dict[str, Any] | None = None) -> Path | None:
    base = project_base(project)
    return (base / _REL_WORK) if base else None


def get_dc_output_dir(project: dict[str, Any] | None = None) -> Path | None:
    base = project_base(project)
    return (base / _REL_OUTPUT) if base else None


def iter_project_dirs() -> list[tuple[str, Path]]:
    """列出 business/projects/ 下全部项目目录 (project_id, path)。"""
    root = get_business_root()
    if not root:
        return []
    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for p in sorted(projects_dir.iterdir()):
        if p.is_dir():
            out.append((p.name, p))
    return out
