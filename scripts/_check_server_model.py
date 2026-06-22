#!/usr/bin/env python3
"""Read LLM model config from server 231."""
from __future__ import annotations

import json
import re

import paramiko

HOST, USER, PASSWORD = "10.143.2.231", "root", "Xvz!DI0g"
ENV_PATH = "/opt/aida_liwen/agent/.env"
NANOBOT_CFG = "/root/.nanobot/config.json"

KEYS = (
    "ZHIPU_MODEL",
    "ZHIPU_BASE_URL",
    "BAILIAN_",
    "AIDA_USE_NANOBOT",
    "AIDA_CHAT_VIA_NANOBOT",
    "NANOBOT_API",
    "OPENAI_MODEL",
    "LLM_MODEL",
    "MODEL",
    "PROVIDER",
)


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    _, out, _ = c.exec_command(f"cat {ENV_PATH} 2>/dev/null", timeout=30)
    env_text = out.read().decode("utf-8", errors="replace")

    print("=== agent/.env (model-related) ===")
    for line in env_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key = s.split("=", 1)[0]
        if any(k in key for k in KEYS):
            val = s.split("=", 1)[1].strip().strip('"').strip("'")
            if "KEY" in key or "SECRET" in key or "TOKEN" in key:
                val = val[:8] + "..." if len(val) > 8 else "***"
            print(f"{key}={val}")

    _, out2, _ = c.exec_command(f"cat {NANOBOT_CFG} 2>/dev/null", timeout=30)
    cfg_raw = out2.read().decode("utf-8", errors="replace")
    print("\n=== nanobot config (model/provider) ===")
    try:
        cfg = json.loads(cfg_raw)
        for k, v in cfg.items():
            kl = k.lower()
            if "model" in kl or "provider" in kl or kl in ("llm", "default"):
                print(f"{k}: {v}")
        # nested providers
        if isinstance(cfg.get("providers"), dict):
            for pname, pcfg in cfg["providers"].items():
                if isinstance(pcfg, dict):
                    model = pcfg.get("model") or pcfg.get("default_model")
                    base = pcfg.get("base_url") or pcfg.get("api_base")
                    if model or base:
                        print(f"providers.{pname}: model={model}, base_url={base}")
    except json.JSONDecodeError:
        print(cfg_raw[:2000])

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
