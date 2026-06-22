#!/usr/bin/env python3
"""Claw 容器冷启动：从挂载的 /app/agent/skills 同步 nanobot 门面并生成 config.json。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("AIDA_USE_NANOBOT_LLM", "1")
os.environ.setdefault("AIDA_CHAT_VIA_NANOBOT", "1")
os.environ.setdefault("NANOBOT_API_URL", "http://127.0.0.1:8900")
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

from agent.nanobot_integration.bootstrap import bootstrap_nanobot_workspace  # noqa: E402


def main() -> int:
    in_container = os.environ.get("AIDA_CLAW_CONTAINER", "").strip() == "1"
    skills_src = Path(os.environ.get("CLAW_SKILLS_CONTAINER", "/app/agent/skills"))
    if in_container and not (skills_src / "discovery.py").is_file():
        print(f"[claw-bootstrap] WARN: mounted skills missing at {skills_src}", flush=True)

    cfg = bootstrap_nanobot_workspace(
        skip_skill_sync=False,
        skip_claude_sync=in_container,
    )
    os.environ["NANOBOT_CONFIG"] = str(cfg)
    print(f"[claw-bootstrap] nanobot config: {cfg}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
