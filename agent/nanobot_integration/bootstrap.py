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


def _sync_facades(dst_root: Path) -> None:
    """把 A 层门面同步到 ``dst_root/<name>/``（nanobot 工作区 / ~/.claude）。

    两个来源：
      ① 历史布局 ``skills/<name>/`` 整棵树（如 software_deployment 命令树、xtsj）
      ② **就近** ``agent/skills/<name>/`` 的门面（``SKILL.md`` + 可选 ``references/``，
         如 zhgk/guihua/contract_boq/proposal_gen/device_install/system_design 等已迁移 skill）
    ② 后写，确保就近门面为准（与运行时 default_skill_md_path 就近优先一致）。
    """
    dst_root.mkdir(parents=True, exist_ok=True)

    # ① 历史 A 层整棵树
    legacy = _repo_root() / "skills"
    if legacy.is_dir():
        for item in legacy.iterdir():
            if not item.is_dir() or item.name.startswith("_"):
                continue
            target = dst_root / item.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)

    # ② 就近门面：agent/skills/<name>/SKILL.md (+ references/)
    agent_skills = _repo_root() / "agent" / "skills"
    if agent_skills.is_dir():
        for d in agent_skills.iterdir():
            if not d.is_dir() or d.name.startswith("_"):
                continue
            md = d / "SKILL.md"
            if not md.is_file():
                continue
            target = dst_root / d.name
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md, target / "SKILL.md")
            refs = d / "references"
            if refs.is_dir():
                refs_dst = target / "references"
                if refs_dst.exists():
                    shutil.rmtree(refs_dst)
                shutil.copytree(refs, refs_dst)


def _agent_env() -> dict[str, str]:
    env_path = _repo_root() / "agent" / ".env"
    out: dict[str, str] = {}
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    # 容器运行时 docker --env-file / -e 注入优先于文件
    for key in (
        "ZHIPU_API_KEY",
        "ZHIPU_BASE_URL",
        "ZHIPU_MODEL",
        "DATA_CENTER_BASE_URL",
        "MAILGW_BASE_URL",
    ):
        v = os.environ.get(key, "").strip()
        if v:
            out[key] = v
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
    skip_skill_sync: bool = False,
    skip_claude_sync: bool = False,
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

    if not skip_skill_sync:
        # 同步 AIDA A 层 skills（历史 skills/ 树 + 就近 agent/skills/<name>/ 门面）
        _sync_facades(skills_dst)

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

    # ~/.claude/skills 兼容 AIDA lint（容器运行时跳过，省一次全盘拷贝）
    if not skip_claude_sync:
        claude_skills = Path.home() / ".claude" / "skills"
        _sync_facades(claude_skills)

    return config_path
