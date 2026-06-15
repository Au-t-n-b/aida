#!/bin/sh
# AIDA preflight · 红线秒级子集（给 Gitea pre-receive 用：服务端、要快、零 agent 依赖）
# 只跑「纯文本扫描 / stdlib 重生成」的守门——不 import agent.*，故服务器无 venv 也能跑。
# 完整守门（含 import-heavy 契约 + eval）走 Gitea Actions 的 preflight.sh。
set -u

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"
PY="${AIDA_PYTHON:-python}"
export AIDA_GUARD_STRICT=1

fail=0
run() {
  label="$1"; shift
  if ! "$PY" "$@"; then echo "   ❌ FAIL · $label"; fail=1; fi
}

echo "── AIDA preflight 红线（pre-receive）──"
run "禁裸 LLM 调用"    agent/scripts/lint_no_naked_llm.py       # 纯正则
run "禁裸外发"        agent/scripts/lint_no_naked_send.py      # 纯正则
run "文档站新鲜度"     agent/scripts/lint_docs_site.py          # stdlib 重生成
run "团队门户新鲜度"   agent/scripts/lint_team_portal.py        # stdlib 重生成
run "模块边界"        agent/scripts/lint_module_boundaries.py   # 纯文本扫描

[ "$fail" = "1" ] && { echo "❌ 红线未过，拒绝 push。"; exit 1; }
echo "✅ 红线通过。"
