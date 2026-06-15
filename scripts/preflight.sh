#!/bin/sh
# AIDA preflight · 守门单一入口
# 本地 pre-push / Gitea Actions / pre-receive 共用同一份清单（避免守门清单散落漂移）。
# AIDA_GUARD_STRICT=1 → 缺依赖/缺文件 = 配置错 = 该红（强制层杜绝假绿，见 agent/scripts/_guard.py）。
#
# 用法：sh scripts/preflight.sh        （本地手跑 / pre-push）
#       覆盖解释器：AIDA_PYTHON=python3 sh scripts/preflight.sh
set -u

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

# venv python 优先（多数守门要 import agent.*；系统 python 常缺依赖）
if [ -n "${AIDA_PYTHON:-}" ]; then PY="$AIDA_PYTHON"
elif [ -x "agent/.venv/Scripts/python.exe" ]; then PY="agent/.venv/Scripts/python.exe"
elif [ -x "agent/.venv/bin/python" ]; then PY="agent/.venv/bin/python"
else PY="python"; fi

export AIDA_GUARD_STRICT=1   # 强制层语义：缺依赖/缺文件该红，不静默放行

fail=0
run() {
  label="$1"; shift
  if ! "$PY" "$@"; then
    echo "   ❌ FAIL · $label（$*）"
    fail=1
  fi
}

echo "── AIDA preflight（AIDA_GUARD_STRICT=1 · $PY）──"
run "禁裸 LLM 调用"          agent/scripts/lint_no_naked_llm.py
run "禁裸外发"              agent/scripts/lint_no_naked_send.py
run "SKILL.md ↔ steps 契约"  agent/scripts/lint_skill_contract.py
run "工具 name/desc/schema"  agent/scripts/lint_tools.py
run "SDUI 三方一致"          agent/scripts/lint_sdui_contract.py
run "SDUI 组件目录新鲜度"     agent/scripts/lint_sdui_gallery.py
run "文档站新鲜度"           agent/scripts/lint_docs_site.py
run "团队门户新鲜度"         agent/scripts/lint_team_portal.py
run "运行时契约 ≡ 代码"      agent/scripts/lint_runtime_contract.py
run "模块边界"              agent/scripts/lint_module_boundaries.py
run "评测回归（zhgk fixture）" agent/evals/eval_zhgk.py --fixture

# 前端守门由独立 job 承担（prebuild = typecheck + lint:no-ts-nocheck → vite build）：
#   cd frontend && npm run build

if [ "$fail" = "1" ]; then
  echo
  echo "❌ preflight 未通过 —— 修复上面 FAIL 项后重试。"
  exit 1
fi
echo
echo "✅ preflight 全绿。"
