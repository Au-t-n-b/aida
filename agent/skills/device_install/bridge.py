"""
device_install bridge · skill 根目录定位（work_root / ProjectData 子目录）。

对齐 zhgk/bridge.py：仅保留路径函数。真实执行走 in-process LangGraph 节点
（见 agent/skills/device_install/steps/），数据根默认指向 nanobot workspace，
可用环境变量 DEVICE_INSTALL_ROOT 覆盖。
"""
from __future__ import annotations

import os
from pathlib import Path

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


def get_device_install_root() -> Path:
    """获取 device_install skill 根目录（每次调用读环境变量，不缓存 import 时刻）。
    不存在则创建，保证 registry.get('device_install') / lint 不抛。"""
    raw = os.environ.get("DEVICE_INSTALL_ROOT", "").strip()
    root = Path(raw) if raw else _NANOBOT_DEFAULT
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def get_data_dir(sub: str = "") -> Path:
    """获取 ProjectData/<sub> 路径"""
    base = get_device_install_root() / "ProjectData"
    return base / sub if sub else base
