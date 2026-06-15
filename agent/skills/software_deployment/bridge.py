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
    """skill 工作区根：runtime/ + data/ + ProjectData/ 均在此目录下。

    仅认 SOFTWARE_DEPLOYMENT_ROOT 或仓库内 skills/software_deployment/，
    不回落 ~/.nanobot（AIDA 与 nanobot 工作区应分离）。
    """
    raw = os.environ.get("SOFTWARE_DEPLOYMENT_ROOT", "").strip()
    root = Path(raw).expanduser() if raw else _REPO_DEFAULT
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


def _gateway_has_creds(data: dict) -> bool:
    apigw = str(data.get("apigw_url") or os.environ.get("CLOUDOPS_APIGW_URL") or "").strip()
    key = str(data.get("gateway_key") or os.environ.get("CLOUDOPS_GATEWAY_KEY") or "").strip()
    app_id = str(data.get("hw_app_id") or os.environ.get("CLOUDOPS_HW_APP_ID") or "").strip()
    return bool(apigw and key and app_id)


def ensure_gateway_config(root: Path) -> bool:
    """确保步骤 8 可读 APIGW 凭证：优先环境变量，其次 gateway.json；缺失时尝试从 nanobot 工作区补齐。"""
    import json
    import shutil

    if _gateway_has_creds({}):
        return True

    gw_path = root / "ProjectData" / "plan" / "RunTime" / "gateway.json"
    if gw_path.is_file():
        try:
            raw = json.loads(gw_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and _gateway_has_creds(raw):
                return True
        except Exception:
            pass

    nb_gw = (
        Path.home()
        / ".nanobot"
        / "workspace"
        / "skills"
        / "software_deployment"
        / "ProjectData"
        / "plan"
        / "RunTime"
        / "gateway.json"
    )
    if nb_gw.is_file():
        gw_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nb_gw, gw_path)
        try:
            raw = json.loads(gw_path.read_text(encoding="utf-8"))
            return isinstance(raw, dict) and _gateway_has_creds(raw)
        except Exception:
            return False
    return False


def import_sd_script(root: Path, step_folder: str, module_stem: str) -> ModuleType:
    ensure_runtime(root)
    from sd_script_import import import_sd_script as _imp  # noqa: WPS433

    return _imp(root, step_folder, module_stem)


def import_runtime_module(root: Path, name: str) -> ModuleType:
    ensure_runtime(root)
    return __import__(name)
