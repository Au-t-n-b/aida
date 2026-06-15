#!/bin/sh
# AIDA 派生制品 git 工作流护栏 · 一次性启用（每个 clone 跑一次）
# 作用：① 钩子目录指向 .githooks/（pre-commit 自动重生成、post-merge 对齐）
#       ② 注册 merge=ours 驱动 → 派生制品合并永不冲突
set -eu

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

git config core.hooksPath .githooks
git config merge.ours.driver true
chmod +x .githooks/pre-commit .githooks/post-merge 2>/dev/null || true

echo "✅ AIDA git 护栏已启用："
echo "   - core.hooksPath = .githooks（pre-commit 源改→自动重生成派生制品并入库；post-merge 合并后对齐）"
echo "   - merge.ours.driver = true（docs/site/*.html 合并永不 3-way 冲突）"
echo
echo "   验证：git config --get core.hooksPath ; git config --get merge.ours.driver"
