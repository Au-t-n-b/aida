"""
zhgk_bridge · zhgk skill 的路径定位（work_root / ProjectData 子目录）。

历史说明：早期的 subprocess 执行链（run_step_streaming / check_step_inputs /
collect_artifacts / read_progress 等）按范式 §2.2「可观测性优先于解耦」已迁为
in-process LangGraph 节点（见 agent/skills/zhgk/steps/），那套 subprocess 死代码
及其唯一调用方 agent/nodes/zhgk_nodes.py 已于清理中移除。

现仅保留被 main.py / skills 使用的路径函数。
"""
from __future__ import annotations

import os
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _AGENT_DIR / ".env"
_NANOBOT_DEFAULT = Path.home() / ".nanobot" / "workspace" / "skills" / "zhgk"


def _load_agent_env() -> None:
    """启动时加载 agent/.env（override=True，避免进程里残留的旧 ZHGK_ROOT）。"""
    try:
        from dotenv import load_dotenv
        if _ENV_FILE.exists():
            load_dotenv(_ENV_FILE, override=True)
    except ImportError:
        pass


_load_agent_env()


def get_zhgk_root() -> Path:
    """获取 zhgk skill 根目录（每次调用读 ZHGK_ROOT，不缓存 import 时刻的环境）。
    不存在则创建，保证 registry.get('zhgk') / lint 不抛（与 guihua 一致）。"""
    raw = os.environ.get("ZHGK_ROOT", "").strip()
    root = Path(raw) if raw else _NANOBOT_DEFAULT
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def get_data_dir(sub: str = "") -> Path:
    """获取 ProjectData/<sub> 路径"""
    return get_zhgk_root() / "ProjectData" / sub if sub else get_zhgk_root() / "ProjectData"
