"""
guihua path_config · 标准目录结构路径配置

路径模型:
  项目根: {AIDA_BUSINESS_ROOT}/project/交付作业/规划设计/
    输入文件/     ← 建模仿真资料包（设备信息表.md / 机房机柜信息表.xlsx 等）
    解析结果/     ← 中间文件（compat_table.md、combo_created.json、move_progress.json 等）
    输出结果/建模仿真/  ← 产物（结题报告）
  组织资产: {AIDA_BUSINESS_ROOT}/org-assets/
"""
from __future__ import annotations

import os
from pathlib import Path

from .bridge import get_guihua_root, get_org_assets_root


# ── 动态路径 helpers ──────────────────────────────────────────────────────────

def get_input_dir() -> Path:
    """输入文件/  ← 用户上传的资料包（设备信息表、机房机柜信息表等）"""
    p = get_guihua_root() / "输入文件"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_parse_dir() -> Path:
    """解析结果/  ← 中间文件（compat_table.md、combo_created.json 等）"""
    p = get_guihua_root() / "解析结果"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_output_dir() -> Path:
    """输出结果/建模仿真/  ← 建模仿真产物（结题报告等）"""
    p = get_guihua_root() / "输出结果" / "建模仿真"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_template_dir() -> Path:
    """组织资产根 org-assets/  ← 底表 / 模板"""
    return get_org_assets_root()


def get_exec_log_path() -> str:
    """执行日志 exec_log.json（项目树外，agent/runtime/logs/guihua/）"""
    log_root = os.environ.get("AIDA_LOG_DIR", "").strip()
    if log_root:
        d = Path(log_root) / "guihua"
    else:
        d = Path(__file__).resolve().parents[2] / "runtime" / "logs" / "guihua"
    d.mkdir(parents=True, exist_ok=True)
    return str(d / "exec_log.json")
