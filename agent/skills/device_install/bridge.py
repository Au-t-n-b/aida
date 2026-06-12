"""
device_install bridge · skill 根目录定位（work_root / ProjectData 子目录）。

对齐 zhgk/bridge.py：仅保留路径函数。真实执行走 in-process LangGraph 节点
（见 agent/skills/device_install/steps/），数据根默认指向 nanobot workspace，
可用环境变量 DEVICE_INSTALL_ROOT 覆盖。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _AGENT_DIR / ".env"
_NANOBOT_DEFAULT = (
    Path.home() / ".nanobot" / "workspace" / "skills" / "device_install"
)


def _load_agent_env() -> None:
    """启动时加载 agent/.env（override=True，避免进程里残留的旧 ROOT）。"""
    try:
        from dotenv import load_dotenv
        if _ENV_FILE.exists():
            load_dotenv(_ENV_FILE, override=True)
    except ImportError:
        pass


_load_agent_env()


def get_device_install_root(project: dict[str, Any] | None = None) -> Path:
    """获取 device_install skill 根目录（每次调用读环境变量，不缓存 import 时刻）。

    优先级：
      1. DEVICE_INSTALL_ROOT
      2. 数据中心 .../交付作业/设备安装（需 AIDA_BUSINESS_ROOT + project_id）
      3. 扫描 business/projects 找到含实施计划的项目
      4. ~/.nanobot/workspace/skills/device_install（本地开发）
    """
    raw = os.environ.get("DEVICE_INSTALL_ROOT", "").strip()
    if raw:
        root = Path(raw)
    else:
        from .data_center_paths import get_dc_work_root, resolve_project_id, get_business_root
        from .services.source_files import _scan_source_dir_with_plan

        dc = get_dc_work_root(project)
        if dc is not None and get_business_root() and resolve_project_id(project):
            root = dc
        elif get_business_root():
            scanned = _scan_source_dir_with_plan()
            if scanned is not None:
                # .../projects/{id}/项目管理/计划/输出结果 → .../projects/{id}/交付作业/设备安装
                root = scanned.parents[2] / "交付作业" / "设备安装"
            else:
                root = _NANOBOT_DEFAULT
        else:
            root = _NANOBOT_DEFAULT
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def get_data_dir(sub: str = "") -> Path:
    """获取 ProjectData/<sub> 路径"""
    base = get_device_install_root() / "ProjectData"
    return base / sub if sub else base
