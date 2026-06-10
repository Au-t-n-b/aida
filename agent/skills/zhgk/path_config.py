"""
zhgk path_config · v4 路径配置

统一管理 ProjectData 各子目录路径，供 steps + services 使用。
bridge.py 提供根目录定位，本模块负责子路径组合。
"""
from __future__ import annotations

from pathlib import Path
from .bridge import get_zhgk_root, get_data_dir


# ── 动态路径 helpers ──────────────────────────────────────────────────────────

def get_template_dir() -> Path:
    """Template/  ← 入场评估标准表.xlsx + 工勘常见高风险库.xlsx + 报告模板.docx"""
    p = get_data_dir("Template")
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_input_dir() -> Path:
    """Input/  ← BOQ.xlsx 等用户上传文件"""
    p = get_data_dir("Input")
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_output_dir() -> Path:
    """Output/  ← 产物文件（全量勘测结果表、问题清单、风险表、报告）"""
    p = get_data_dir("Output")
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_runtime_dir() -> Path:
    """RunTime/  ← 中间文件（过滤结果、project_info.json 等）"""
    p = get_data_dir("RunTime")
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_images_dir() -> Path:
    """Images/  ← 勘测照片"""
    p = get_data_dir("Images")
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── 具体文件路径 helpers ───────────────────────────────────────────────────────

def get_base_table_path() -> str:
    """入场评估标准表.xlsx（Template/）"""
    return str(get_template_dir() / "入场评估标准表.xlsx")


def get_risk_library_path() -> str:
    """工勘常见高风险库.xlsx（Template/）"""
    return str(get_template_dir() / "工勘常见高风险库.xlsx")


def get_report_template_path() -> str:
    """新版项目工勘报告模板.docx（Template/）"""
    return str(get_template_dir() / "新版项目工勘报告模板.docx")


def get_boq_path() -> str:
    """BOQ.xlsx（Input/，glob 取第一个匹配）"""
    candidates = sorted(get_input_dir().glob("*BOQ*.xlsx"))
    if candidates:
        return str(candidates[0])
    return str(get_input_dir() / "BOQ.xlsx")


def get_exec_log_path() -> str:
    """执行日志 exec_log.json（根目录）"""
    return str(get_zhgk_root() / "exec_log.json")


# ── 模块级常量（供 smart_survey services 里的 logger.py lazy import 兼容）──────
# 注意：此处在 import 时计算一次；如果 ZHGK_ROOT 在 import 后变化，
#       请用 get_exec_log_path() 替代。
EXEC_LOG_PATH: str = get_exec_log_path()
