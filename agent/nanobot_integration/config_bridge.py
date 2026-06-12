"""
从 nanobot config.json 同步 LLM 配置到 AIDA agent/llm.py 使用的环境变量。

不强制 import nanobot 包（兼容 Python 3.10）；直接解析 JSON。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# nanobot ProviderSpec.default_api_base 子集（与 registry 对齐）
_PROVIDER_DEFAULT_BASE: dict[str, str] = {
    "minimax": "https://api.minimaxi.com/v1",
    "minimax_anthropic": "https://api.minimaxi.com/anthropic",
    "zhipu": "https://open.bigmodel.cn/api/coding/paas/v4",
    "openrouter": "https://openrouter.ai/api/v1",
    "custom": "",
}


def _config_path() -> Path:
    raw = os.environ.get("NANOBOT_CONFIG", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".nanobot" / "config.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _provider_block(providers: dict[str, Any], name: str) -> dict[str, Any]:
    block = providers.get(name) or {}
    return block if isinstance(block, dict) else {}


def _resolve_preset(data: dict[str, Any]) -> tuple[str, str]:
    """返回 (model, provider_name)。"""
    agents = data.get("agents") or {}
    defaults = agents.get("defaults") or {}
    preset_name = defaults.get("modelPreset") or defaults.get("model_preset")
    presets = data.get("modelPresets") or data.get("model_presets") or {}
    if preset_name and preset_name in presets:
        p = presets[preset_name]
        model = str(p.get("model") or defaults.get("model") or "MiniMax-M2.5")
        provider = str(p.get("provider") or defaults.get("provider") or "auto")
        return model, provider
    model = str(defaults.get("model") or "MiniMax-M2.5")
    provider = str(defaults.get("provider") or "auto")
    return model, provider


def _detect_provider(model: str, provider: str, providers: dict[str, Any]) -> str:
    if provider and provider != "auto":
        return provider
    m = model.lower()
    if "minimax" in m or m.startswith("m2-") or m.startswith("abab"):
        return "minimax"
    if "glm" in m or "zhipu" in m:
        return "zhipu"
    # 有 key 的第一个 provider
    for name, block in providers.items():
        if isinstance(block, dict) and block.get("apiKey") or block.get("api_key"):
            return name
    return "minimax"


def _api_key_and_base(providers: dict[str, Any], provider_name: str) -> tuple[str, str]:
    block = _provider_block(providers, provider_name)
    # camelCase / snake_case
    api_key = (block.get("apiKey") or block.get("api_key") or "").strip()
    api_base = (block.get("apiBase") or block.get("api_base") or "").strip()
    if not api_base:
        api_base = _PROVIDER_DEFAULT_BASE.get(provider_name, "")
    return api_key, api_base


def apply_nanobot_llm_to_env(*, force: bool = False) -> bool:
    """
    将 nanobot 默认 preset 的 LLM 配置写入 ZHIPU_* 环境变量（llm.py 复用）。

    Returns:
        True 若成功从 nanobot 配置加载；False 则回退 agent/.env。
    """
    if os.environ.get("AIDA_USE_NANOBOT_LLM", "1").strip().lower() in ("0", "false", "no"):
        return False

    path = _config_path()
    data = _load_json(path)
    if not data:
        return False

    providers = data.get("providers") or {}
    model, provider = _resolve_preset(data)
    provider_name = _detect_provider(model, provider, providers)
    api_key, api_base = _api_key_and_base(providers, provider_name)
    if not api_key:
        return False

    if force or not os.environ.get("ZHIPU_API_KEY", "").strip():
        os.environ["ZHIPU_API_KEY"] = api_key
    if api_base and (force or not os.environ.get("ZHIPU_BASE_URL", "").strip()):
        os.environ["ZHIPU_BASE_URL"] = api_base
    if force or not os.environ.get("ZHIPU_MODEL", "").strip():
        os.environ["ZHIPU_MODEL"] = model

    os.environ.setdefault("AIDA_LLM_SOURCE", "nanobot")
    return True


def nanobot_status() -> dict[str, Any]:
    path = _config_path()
    data = _load_json(path)
    if not data:
        return {"enabled": False, "config_path": str(path), "reason": "config not found"}
    model, provider = _resolve_preset(data)
    providers = data.get("providers") or {}
    provider_name = _detect_provider(model, provider, providers)
    api_key, api_base = _api_key_and_base(providers, provider_name)
    workspace = (data.get("agents") or {}).get("defaults", {}).get("workspace", "~/.nanobot/workspace")
    return {
        "enabled": True,
        "config_path": str(path),
        "model": model,
        "provider": provider_name,
        "api_base": api_base,
        "api_key_set": bool(api_key),
        "workspace": workspace,
        "aida_llm_source": os.environ.get("AIDA_LLM_SOURCE", "env"),
    }
