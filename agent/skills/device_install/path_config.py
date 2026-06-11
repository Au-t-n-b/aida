"""
device_install path_config · 路径配置

统一管理 ProjectData 各子目录路径，供 steps + services 使用。
bridge.py 提供根目录定位，本模块负责子路径组合。
"""
from __future__ import annotations

from pathlib import Path

from .bridge import get_device_install_root, get_data_dir


# ── 动态路径 helpers ──────────────────────────────────────────────────────────

def get_input_dir() -> Path:
    """Input/  ← 任务计划表 / 责任人信息表 / 到货信息表 / 设备位置表 / SN 扫码表（用户上传）"""
    p = get_data_dir("Input")
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_output_dir() -> Path:
    """Output/  ← 产物（责任人模板、全量任务、实施计划、SN 扫码表、完工清单/报告）"""
    p = get_data_dir("Output")
    p.mkdir(parents=True, exist_ok=True)
    return p


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
