"""software_deployment · 工作区根目录与 Raw Skill 运行时桥接。

默认使用仓库内 ``skills/software_deployment/``；
可用 ``SOFTWARE_DEPLOYMENT_ROOT`` 覆盖（服务器挂载 / 数据中心 run 目录）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType

_AGENT_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _AGENT_DIR / ".env"
_REPO_DEFAULT = Path(__file__).resolve().parents[3] / "skills" / "software_deployment"


def _load_agent_env() -> None:
    try:
        from dotenv import load_dotenv

        if _ENV_FILE.exists():
            load_dotenv(_ENV_FILE, override=True)
    except ImportError:
        pass


_load_agent_env()


def get_sd_root() -> Path:
    """skill 工作区根：runtime/ + data/ + ProjectData/ 均在此目录下。"""
    raw = os.environ.get("SOFTWARE_DEPLOYMENT_ROOT", "").strip()
    root = Path(raw) if raw else _REPO_DEFAULT
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def ensure_runtime(root: Path) -> Path:
    """Add skill runtime to sys.path and set SD_SKILL_ROOT for nested script imports."""
    resolved = root.resolve()
    os.environ.setdefault("SD_SKILL_ROOT", str(resolved))
    rt = resolved / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    return rt


def import_sd_script(root: Path, step_folder: str, module_stem: str) -> ModuleType:
    ensure_runtime(root)
    from sd_script_import import import_sd_script as _imp  # noqa: WPS433

    return _imp(root, step_folder, module_stem)


def import_runtime_module(root: Path, name: str) -> ModuleType:
    ensure_runtime(root)
    return __import__(name)
