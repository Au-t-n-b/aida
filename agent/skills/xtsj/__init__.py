"""系统设计（a3 智能网络开局）skill 包 · dispatch 模型 PoC。

对比 guihua（线性 5 段）：本 skill dispatch_mode=True，用户按命令任意顺序触发，
每条命令 = 一个 step（key = 命令 id）。移植方案见 agent/docs/A3-MIGRATION-PLAN.md。
注册见 agent/skills/__init__.py。
"""
