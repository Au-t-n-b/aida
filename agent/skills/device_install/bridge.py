"""
device_install bridge · 路径定位（数据中心 API 化后只保留前缀 + scratch 根）。

路径模型（《数据访问路径整改通用规范》）：
  - 业务数据一律走数据中心 HTTP API（语义寻址 moduleCode+fileStage+projectId，见 dc_io.py）；
    DC 不可达时降级到挂载盘 {AIDA_BUSINESS_ROOT}/project/<域>/<模块>/<阶段>/。
  - 组织资产: {AIDA_BUSINESS_ROOT}/org-assets/
  - 本地 scratch（openpyxl 缓冲 + 运行态 JSON）落在业务树之外：
    {AIDA_SCRATCH_DIR | agent/runtime/scratch}/device_install/
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parents[2]  # agent/
_ENV_FILE = _AGENT_DIR / ".env"


def _load_agent_env() -> None:
    """启动时加载 agent/.env（override=True，避免进程残留旧值）。"""
    try:
        from dotenv import load_dotenv
        if _ENV_FILE.exists():
            load_dotenv(_ENV_FILE, override=True)
    except ImportError:
        pass


_load_agent_env()


def business_root() -> Path:
    """数据中心业务根（挂载盘降级用）。AIDA_BUSINESS_ROOT，缺省 /opt/aida/aida-data/business。"""
    raw = os.environ.get("AIDA_BUSINESS_ROOT", "").strip()
    return Path(raw) if raw else Path("/opt/aida/aida-data/business")


def get_org_assets_root() -> Path:
    """组织资产根: {AIDA_BUSINESS_ROOT}/org-assets/"""
    p = business_root() / "org-assets"
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def get_scratch_root() -> Path:
    """本地 scratch 根（业务树之外）。AIDA_SCRATCH_DIR 覆盖，缺省 agent/runtime/scratch/device_install。"""
    raw = os.environ.get("AIDA_SCRATCH_DIR", "").strip()
    base = Path(raw) if raw else (_AGENT_DIR / "runtime" / "scratch")
    p = base / "device_install"
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def get_device_install_root(project: dict[str, Any] | None = None) -> Path:
    """框架 work_root = 本地 scratch 根（业务数据走数据中心 API，见 dc_io）。

    保留 project 形参仅为兼容旧签名；scratch 与项目无关（按 run_id 再分子目录）。
    """
    return get_scratch_root()
