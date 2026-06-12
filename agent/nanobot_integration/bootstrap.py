"""
初始化 nanobot 工作区：从 agent/.env 生成 config.json，同步 AIDA skills。
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _agent_env() -> dict[str, str]:
    env_path = _repo_root() / "agent" / ".env"
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


# nanobot 内置 skill 名（删除目录后仍通过 disabledSkills 双保险）
_BUILTIN_SKILL_NAMES = [
    "weather", "cron", "github", "image-generation", "long-goal", "memory",
    "my", "skill-creator", "summarize", "tmux", "update-setup", "clawhub",
]


def _default_config(api_key: str, api_base: str, model: str, workspace: Path) -> dict[str, Any]:
    return {
        "agents": {
            "defaults": {
                "workspace": str(workspace),
                "model": model,
                "provider": "minimax",
                "modelPreset": "aida-default",
                "temperature": 0.2,
                "disabledSkills": _BUILTIN_SKILL_NAMES,
            }
        },
        "api": {
            "host": "127.0.0.1",
            "port": 8900,
            "timeout": 300,
        },
        "modelPresets": {
            "aida-default": {
                "label": "AIDA Default",
                "model": model,
                "provider": "minimax",
                "temperature": 0.2,
            }
        },
        "providers": {
            "minimax": {
                "apiKey": api_key,
                "apiBase": api_base,
            }
        },
        "gateway": {"host": "0.0.0.0", "port": 8765},
        "channels": {
            "websocket": {"enabled": True, "host": "0.0.0.0", "port": 8765}
        },
        "tools": {
            "aida_agent": {"enable": True, "base_url": "http://127.0.0.1:7401"}
        },
    }


def bootstrap_nanobot_workspace(
    *,
    config_path: Path | None = None,
    workspace: Path | None = None,
    overwrite_config: bool = False,
) -> Path:
    """
    确保 ~/.nanobot/config.json 与 workspace/skills 就绪。
    返回 config.json 路径。
    """
    config_path = config_path or Path(
        os.environ.get("NANOBOT_CONFIG", str(Path.home() / ".nanobot" / "config.json"))
    ).expanduser()
    workspace = workspace or Path(
        os.environ.get("NANOBOT_WORKSPACE", str(Path.home() / ".nanobot" / "workspace"))
    ).expanduser()

    config_path.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    skills_dst = workspace / "skills"
    skills_dst.mkdir(parents=True, exist_ok=True)

    # 同步 AIDA A 层 skills
    skills_src = _repo_root() / "skills"
    if skills_src.is_dir():
        for item in skills_src.iterdir():
            if not item.is_dir() or item.name.startswith("_"):
                continue
            target = skills_dst / item.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)

    env = _agent_env()
    api_key = env.get("ZHIPU_API_KEY", "")
    api_base = env.get("ZHIPU_BASE_URL", "https://api.minimaxi.com/v1")
    model = env.get("ZHIPU_MODEL", "MiniMax-M2.5")

    if not config_path.exists() or overwrite_config:
        if not api_key:
            raise RuntimeError("agent/.env 缺少 ZHIPU_API_KEY，无法生成 nanobot config")
        cfg = _default_config(api_key, api_base, model, workspace)
        config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif api_key:
        # 合并已有 config 的 minimax key（不覆盖用户手改的其他字段）
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = _default_config(api_key, api_base, model, workspace)
        else:
            data.setdefault("providers", {})
            data["providers"].setdefault("minimax", {})
            data["providers"]["minimax"]["apiKey"] = api_key
            if api_base:
                data["providers"]["minimax"]["apiBase"] = api_base
            data.setdefault("agents", {}).setdefault("defaults", {})
            data["agents"]["defaults"]["workspace"] = str(workspace)
            data["agents"]["defaults"]["model"] = model
            data["agents"]["defaults"]["disabledSkills"] = _BUILTIN_SKILL_NAMES
            data.setdefault("api", {"host": "127.0.0.1", "port": 8900, "timeout": 300})
        config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ~/.claude/skills 兼容 AIDA lint
    claude_skills = Path.home() / ".claude" / "skills"
    claude_skills.mkdir(parents=True, exist_ok=True)
    if skills_src.is_dir():
        for item in skills_src.iterdir():
            if item.is_dir():
                t = claude_skills / item.name
                if t.exists():
                    shutil.rmtree(t)
                shutil.copytree(item, t)

    return config_path
