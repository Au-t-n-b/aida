@echo off
REM AIDA 派生制品 git 工作流护栏 · 一次性启用（Windows 双击或命令行跑一次）
git config core.hooksPath .githooks
git config merge.ours.driver true
echo.
echo [OK] AIDA git 护栏已启用:
echo    - core.hooksPath = .githooks (pre-commit 自动重生成派生制品; post-merge 对齐)
echo    - merge.ours.driver = true (docs/site/*.html 合并永不冲突)
echo.
echo    验证: git config --get core.hooksPath  ^&  git config --get merge.ours.driver
