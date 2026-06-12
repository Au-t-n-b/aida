"""system_design 进程内业务模块（不 subprocess、不进 DEFAULT_TOOLS）。

对齐 AGENTS.md 铁律②：a3 离线 pipeline 已 vendoring 进 a3_engine/，
由 a3_bridge.run_command / run_dispatch 进程内 runpy 执行。
本目录放 AIDA 侧编排辅助（输入件配置、平面规格、执行日志、交付路由等）。
"""
