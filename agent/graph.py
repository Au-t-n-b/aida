"""
AIDA Agent DAG · LangGraph 编排（registry 驱动 · 多 skill）

5.28 重构：从「手写节点 + 路由」改为基于 BaseSkill 自动生成 DAG。
5.29 Phase 2：checkpointer 从 MemorySaver → AsyncSqliteSaver（run 重启不丢）。
6.04 泛化：从「zhgk 单图写死」改为按 skill_id 经 registry 构图并缓存——
     新业务场景 Skill注册到 registry 后即可拿到 graph，无需改本文件。

每个 skill 的 DAG 由 BaseSkill.build_graph() 自动生成（每 step 一节点 + 串行边）。
每个节点完成后 BaseSkill.execute_step 决定流向：
  - 有 error → END
  - 有 hitl  → END（前端通过 resume 续跑）
  - 否则     → 下一个 step

Checkpointer：
  - FastAPI（异步）走 get_graph_async(skill_id) → AsyncSqliteSaver（共享一个 db）
  - 同步 CLI / 测试走 get_graph(skill_id) → 默认同步 SqliteSaver / MemorySaver
"""
from __future__ import annotations

from typing import Any

from .skills import registry


# 按 skill_id 缓存编译后的图（一个进程内每个 skill 只建一次）
_compiled: dict[str, Any] = {}          # 同步版（CLI / 测试）
_compiled_async: dict[str, Any] = {}    # 异步版（FastAPI）
_async_conn = None                       # 共享的 aiosqlite 连接（shutdown 时关闭）
_async_saver = None                      # 共享的 AsyncSqliteSaver（所有 skill 共用）


def get_graph(skill_id: str = "zhgk"):
    """同步单例 · 用于 CLI / 测试（同步 SqliteSaver，不支持 astream）"""
    if skill_id not in _compiled:
        skill = registry.get(skill_id)
        _compiled[skill_id] = skill.build_graph()
    return _compiled[skill_id]


async def get_graph_async(skill_id: str = "zhgk"):
    """
    异步单例 · FastAPI 用。
    首次调用建立共享的 AsyncSqliteSaver（包一个 awaited aiosqlite 连接，支持 astream）；
    之后每个 skill 各编译一张图，共用同一 checkpointer（thread_id 已隔离各 run）。
    """
    global _async_conn, _async_saver
    if _async_saver is None:
        import aiosqlite
        from pathlib import Path
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from .skills.base import default_checkpoint_db

        db_path = default_checkpoint_db()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _async_conn = await aiosqlite.connect(db_path, check_same_thread=False)
        _async_saver = AsyncSqliteSaver(_async_conn)
        await _async_saver.setup()

    if skill_id not in _compiled_async:
        skill = registry.get(skill_id)
        _compiled_async[skill_id] = skill.build_graph(checkpointer=_async_saver)
    return _compiled_async[skill_id]


async def close_graph_async():
    """FastAPI shutdown 时关闭 aiosqlite 连接"""
    global _async_conn, _async_saver, _compiled_async
    if _async_conn is not None:
        try:
            await _async_conn.close()
        finally:
            _async_conn = None
            _async_saver = None
            _compiled_async = {}
