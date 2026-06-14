"""
device_install path_config · 路径配置

统一管理 ProjectData 各子目录路径，供 steps + services 使用。
bridge.py 提供根目录定位，本模块负责子路径组合。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .bridge import get_device_install_root, get_data_dir


# Linux 服务器固定落点（业务数据规范 · 单项目）
SERVER_BUSINESS_ROOT = Path("/opt/aida/aida-data/business")
SERVER_PROJECT_ID = "1b9bb4a0d0ce4863925e787bc057ecaf"
SERVER_UPSTREAM_INPUT_DIR = (
    SERVER_BUSINESS_ROOT / "projects" / SERVER_PROJECT_ID / "项目管理" / "计划" / "输出结果"
)
SERVER_OUTPUT_DIR = (
    SERVER_BUSINESS_ROOT / "projects" / SERVER_PROJECT_ID / "交付作业" / "设备安装" / "输出结果"
)


# ── 动态路径 helpers ──────────────────────────────────────────────────────────

def get_input_dir() -> Path:
    """ProjectData/Input/（本地开发上传区；服务器读上游目录见 get_upstream_input_dir）。"""
    p = get_data_dir("Input")
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_upstream_input_dir(project: dict[str, Any] | None = None) -> Path:
    """上游输入 xlsx 读取目录（交付计划表 / 设备位置表 / 到货信息表）。

    优先级：DEVICE_INSTALL_SOURCE_ROOT → 数据中心 .../项目管理/计划/输出结果 → ProjectData/Input/
    """
    from .services.source_files import get_source_dir

    p = get_source_dir(get_device_install_root(project), project)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_output_dir(project: dict[str, Any] | None = None) -> Path:
    """作业产物输出目录（责任人表、全量任务、实施计划、SN 扫码表、完工清单/报告）。

    优先级：
      1. 环境变量 DEVICE_INSTALL_OUTPUT_ROOT
      2. 数据中心 .../交付作业/设备安装/输出结果（business 根存在时强制）
      3. 默认 <work_root>/ProjectData/Output（本地开发/评测）
    """
    raw = os.environ.get("DEVICE_INSTALL_OUTPUT_ROOT", "").strip()
    if raw:
        p = Path(raw)
    else:
        from .data_center_paths import get_dc_output_dir, get_business_root

        dc = get_dc_output_dir(project)
        if dc is not None and get_business_root() is not None:
            p = dc
        else:
            p = get_data_dir("Output")
    p.mkdir(parents=True, exist_ok=True)
    return p


def output_rel(work_root: Path | str, path: Path | str) -> str:
    """产物路径 → 相对 work_root 字符串（供 /artifact 下载）。

    输出目录被 DEVICE_INSTALL_OUTPUT_ROOT 指到 work_root 之外时，
    回退为绝对路径，避免 SkillContext.rel 抛 ValueError 而中断 step
    （此时 /artifact 端点无法下载该产物，文件仍按要求落盘到指定目录）。
    """
    p = Path(path).resolve()
    try:
        return str(p.relative_to(Path(work_root).resolve()))
    except ValueError:
        return str(p)


def get_runtime_dir() -> Path:
    """RunTime/  ← 中间文件（tasks_state.json、sn_tables.json 等）"""
    p = get_data_dir("RunTime")
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── 具体文件路径 helpers ───────────────────────────────────────────────────────

def get_tasks_state_path() -> str:
    """任务状态单一事实源 tasks_state.json（RunTime/）"""
    return str(get_runtime_dir() / "tasks_state.json")


def get_sn_tables_path() -> str:
    """SN 扫码表分组元数据 sn_tables.json（RunTime/）"""
    return str(get_runtime_dir() / "sn_tables.json")


def get_sn_pool_path() -> str:
    """SN 全量池 sn_pool.json（RunTime/ · plan_receive 解析上游 Sheet2）"""
    return str(get_runtime_dir() / "sn_pool.json")


def get_principal_table_path() -> str:
    """责任人信息表.xlsx（Output/）"""
    return str(get_output_dir() / "责任人信息表.xlsx")


def get_full_tasks_path() -> str:
    """设备安装全量任务.xlsx（Output/）"""
    return str(get_output_dir() / "设备安装全量任务.xlsx")


def get_dispatch_plan_path() -> str:
    """设备安装实施计划.xlsx（Output/）"""
    return str(get_output_dir() / "设备安装实施计划.xlsx")
