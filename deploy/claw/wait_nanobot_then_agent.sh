#!/bin/bash
# supervisord 子进程：等 nanobot /health 就绪后再起 agent
set -euo pipefail

url="${NANOBOT_HEALTH_URL:-http://127.0.0.1:8900/health}"
max_wait="${NANOBOT_WAIT_SECS:-120}"

echo "[wait-nanobot] waiting for $url (max ${max_wait}s)" >&2
elapsed=0
while [ "$elapsed" -lt "$max_wait" ]; do
  if curl -sf "$url" >/dev/null 2>&1; then
    echo "[wait-nanobot] ready after ${elapsed}s" >&2
    exec python -m uvicorn agent.main:app --host 0.0.0.0 --port 7401 --workers 1
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

echo "[wait-nanobot] timeout after ${max_wait}s" >&2
exit 1
