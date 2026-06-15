#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CLEAR_INPUT=0
RESTART=0

for arg in "$@"; do
  case "$arg" in
    --clear-input) CLEAR_INPUT=1 ;;
    --restart) RESTART=1 ;;
    *)
      echo "unknown argument: $arg" >&2
      echo "usage: scripts/reset_demo.sh [--clear-input] [--restart]" >&2
      exit 2
      ;;
  esac
done

compose() {
  docker compose "$@"
}

clear_dir='clear_dir() { mkdir -p "$1"; find "$1" -mindepth 1 -maxdepth 1 -exec rm -rf {} +; }'

echo "[reset] clearing zhgk runtime data in agent container"
compose exec -T agent sh -lc "
set -eu
$clear_dir
mkdir -p /app/.data/zhgk/ProjectData
clear_dir /app/.data/zhgk/ProjectData/Output
clear_dir /app/.data/zhgk/ProjectData/RunTime
clear_dir /app/.data/zhgk/ProjectData/Images
if [ \"$CLEAR_INPUT\" = \"1\" ]; then
  clear_dir /app/.data/zhgk/ProjectData/Input
fi
mkdir -p /app/.data/runtime
rm -f /app/.data/runtime/checkpoints.db /app/.data/runtime/checkpoints.db-*
"

echo "[reset] clearing mailgw data in mailgw container"
compose exec -T mailgw sh -lc "
set -eu
$clear_dir
clear_dir /app/.data/mailgw
"

echo "[reset] preserving SOG demo assets under data/sog-assets and data/sog-scenes.json"

if [ "$RESTART" = "1" ]; then
  echo "[reset] restarting demo services"
  compose restart agent mailgw frontend
fi

echo "[reset] done"
