#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CLEAR_INPUT=0
CLEAR_TEMPLATE=0
CLEAR_CHECKPOINTS=0
FULL=0
RESTART=0
DRY_RUN=0

usage() {
  cat <<'EOF'
usage: scripts/reset_demo.sh [options]

清空 zhgk 工勘运行时数据（Docker 部署）。默认仅清 Output/RunTime/Images；
保留 Template 底表。加 --full 可彻底重置并清 checkpoint。

options:
  --clear-input       同时清空 ProjectData/Input
  --clear-template    同时清空 ProjectData/Template（底表）
  --clear-checkpoints 删除 LangGraph checkpoints.db
  --full              等价于上述三项全开
  --dry-run           仅打印将清除的路径
  --restart           重置后 restart agent mailgw frontend
EOF
}

compose() {
  docker compose "$@"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --clear-input) CLEAR_INPUT=1 ;;
    --clear-template) CLEAR_TEMPLATE=1 ;;
    --clear-checkpoints) CLEAR_CHECKPOINTS=1 ;;
    --full) FULL=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --restart) RESTART=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

reset_args=(python agent/scripts/reset_zhgk_workspace.py --zhgk-root /app/.data/zhgk)
if [ "$CLEAR_INPUT" = "1" ]; then reset_args+=(--clear-input); fi
if [ "$CLEAR_TEMPLATE" = "1" ]; then reset_args+=(--clear-template); fi
if [ "$CLEAR_CHECKPOINTS" = "1" ]; then reset_args+=(--clear-checkpoints); fi
if [ "$FULL" = "1" ]; then reset_args+=(--full); fi
if [ "$DRY_RUN" = "1" ]; then reset_args+=(--dry-run); fi

echo "[reset] resetting zhgk workspace in agent container"
compose exec -T agent "${reset_args[@]}"

echo "[reset] clearing mailgw data in mailgw container"
compose exec -T mailgw sh -lc '
set -eu
mkdir -p /app/.data/mailgw
find /app/.data/mailgw -mindepth 1 -maxdepth 1 -exec rm -rf {} +
'

echo "[reset] preserving SOG demo assets under data/sog-assets and data/sog-scenes.json"

if [ "$RESTART" = "1" ]; then
  echo "[reset] restarting demo services"
  compose restart agent mailgw frontend
fi

echo "[reset] done"
