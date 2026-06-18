"""
zhgk path_config · 标准目录结构路径配置

路径模型:
  项目根: {AIDA_BUSINESS_ROOT}/project/交付作业/智慧工勘/
    输入文件/     ← BOQ、人员信息、勘测结果表等
    解析结果/     ← 中间文件（project_info.json、gkclaw 等）
    输出结果/     ← 产物（全量勘测结果表、问题清单、风险表、报告）
  组织资产: {AIDA_BUSINESS_ROOT}/org-assets/
    入场评估标准表.xlsx / 工勘常见高风险库.xlsx / 新版项目工勘报告模板.docx
"""
from __future__ import annotations

import os
from pathlib import Path
from .bridge import get_zhgk_root, get_org_assets_root


# ── 动态路径 helpers ──────────────────────────────────────────────────────────

def get_input_dir() -> Path:
    """输入文件/  ← BOQ.xlsx 等用户上传文件"""
    p = get_zhgk_root() / "输入文件"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_output_dir() -> Path:
    """输出结果/  ← 产物文件（全量勘测结果表、问题清单、风险表、报告）"""
    p = get_zhgk_root() / "输出结果"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_parse_dir() -> Path:
    """解析结果/  ← 中间文件（过滤结果、project_info.json 等）"""
    p = get_zhgk_root() / "解析结果"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_images_dir() -> Path:
    """输入文件/勘测图片文件夹/  ← 勘测照片"""
    p = get_input_dir() / "勘测图片文件夹"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_template_dir() -> Path:
    """组织资产根 org-assets/  ← 底表 / 模板"""
    return get_org_assets_root()


# ── 具体文件路径 helpers ───────────────────────────────────────────────────────

def get_base_table_path() -> str:
    """入场评估标准表.xlsx（org-assets/）"""
    return str(get_org_assets_root() / "入场评估标准表.xlsx")


def get_risk_library_path() -> str:
    """工勘常见高风险库.xlsx（org-assets/）"""
    return str(get_org_assets_root() / "工勘常见高风险库.xlsx")


def get_report_template_path() -> str:
    """新版项目工勘报告模板.docx（org-assets/）"""
    return str(get_org_assets_root() / "新版项目工勘报告模板.docx")


def get_boq_path() -> str:
    """BOQ.xlsx（输入文件/，glob 取第一个匹配）"""
    candidates = sorted(get_input_dir().glob("*BOQ*.xlsx"))
    if candidates:
        return str(candidates[0])
    return str(get_input_dir() / "BOQ.xlsx")


def get_exec_log_path() -> str:
    """执行日志 exec_log.json（项目树外，agent/runtime/logs/zhgk/）"""
    log_root = os.environ.get("AIDA_LOG_DIR", "").strip()
    if log_root:
        d = Path(log_root) / "zhgk"
    else:
        d = Path(__file__).resolve().parents[2] / "runtime" / "logs" / "zhgk"
    d.mkdir(parents=True, exist_ok=True)
    return str(d / "exec_log.json")


# ── 模块级常量（供 logger.py lazy import 兼容）──────
EXEC_LOG_PATH: str = get_exec_log_path()
