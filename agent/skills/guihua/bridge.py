"""
guihua bridge · 规划设计 Skill 的路径定位（标准目录结构）。

路径模型：全路径 = 可配置前缀(AIDA_BUSINESS_ROOT) + 标准相对路径
  项目根: {前缀}/project/交付作业/规划设计/
  组织资产: {前缀}/org-assets/
"""
from __future__ import annotations

import os
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _AGENT_DIR / ".env"


def _load_agent_env() -> None:
    try:
        from dotenv import load_dotenv
        if _ENV_FILE.exists():
            load_dotenv(_ENV_FILE, override=True)
    except ImportError:
        pass


_load_agent_env()


def _business_root() -> Path:
    raw = os.environ.get("AIDA_BUSINESS_ROOT", "").strip()
    return Path(raw) if raw else Path("/opt/aida/aida-data/business")


def get_guihua_root() -> Path:
    """规划设计项目根: {AIDA_BUSINESS_ROOT}/project/交付作业/规划设计"""
    root = _business_root() / "project" / "交付作业" / "规划设计"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def get_org_assets_root() -> Path:
    """组织资产根: {AIDA_BUSINESS_ROOT}/org-assets/"""
    p = _business_root() / "org-assets"
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()
