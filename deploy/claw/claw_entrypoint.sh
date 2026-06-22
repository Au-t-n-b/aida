#!/bin/bash
# Claw 容器入口：准备挂载目录 → bootstrap nanobot → 启动 supervisord
set -euo pipefail

export AIDA_USE_NANOBOT_LLM="${AIDA_USE_NANOBOT_LLM:-1}"
export AIDA_CHAT_VIA_NANOBOT="${AIDA_CHAT_VIA_NANOBOT:-1}"
export NANOBOT_API_URL="${NANOBOT_API_URL:-http://127.0.0.1:8900}"
export NANOBOT_CONFIG="${NANOBOT_CONFIG:-/root/.nanobot/config.json}"
export NANOBOT_WORKSPACE="${NANOBOT_WORKSPACE:-/root/.nanobot/workspace}"
export NO_PROXY="${NO_PROXY:-127.0.0.1,localhost}"
export no_proxy="${no_proxy:-127.0.0.1,localhost}"
export AIDA_CLAW_CONTAINER="${AIDA_CLAW_CONTAINER:-1}"

business_root="${AIDA_BUSINESS_ROOT:-/opt/aida/aida-data/business}"
checkpoint_db="${AIDA_CHECKPOINT_DB:-/opt/aida/aida-data/runtime/checkpoints/claw.db}"

mkdir -p "$business_root" "$(dirname "$checkpoint_db")" \
    "$(dirname "$NANOBOT_CONFIG")" "$NANOBOT_WORKSPACE/skills"

echo "[claw-entrypoint] AIDA_BUSINESS_ROOT=$business_root" >&2
echo "[claw-entrypoint] AIDA_CHECKPOINT_DB=$checkpoint_db" >&2

python3 /app/deploy/claw/claw_bootstrap.py

exec "$@"
