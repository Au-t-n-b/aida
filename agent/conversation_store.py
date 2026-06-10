"""
会话多轮记忆存储 ·《交付 Claw/Agent 工程范式》§3.5

会话用 conv_id（≈ 任务图的 thread_id）存多轮记忆。轻量 sqlite 持久化：
零运维、重启不丢，与任务图的 AsyncSqliteSaver 同源理念。

只存 user / assistant 的最终文本对（工具中间消息不持久化——每轮按需重跑），
重建 history 时还原为 HumanMessage / AIMessage 喂回模型。
未来若会话也图化，可统一到同一个 LangGraph checkpointer。
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from threading import Lock


def _default_db() -> str:
    env = os.environ.get("AIDA_CONV_DB", "").strip()
    if env:
        return env
    return str(Path(__file__).resolve().parent / "runtime" / "conversations.db")


class ConversationStore:
    """conv_id → 有序的 (role, content) 文本对。"""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or _default_db()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS conv "
                "(conv_id TEXT, seq INTEGER, role TEXT, content TEXT)"
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_conv ON conv(conv_id, seq)")

    def load(self, conv_id: str) -> list[dict]:
        """按顺序返回 [{"role": "user"|"assistant", "content": str}, ...]。"""
        if not conv_id:
            return []
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT role, content FROM conv WHERE conv_id=? ORDER BY seq",
                (conv_id,),
            ).fetchall()
        return [{"role": r, "content": ct} for r, ct in rows]

    def append(self, conv_id: str, role: str, content: str) -> None:
        if not conv_id:
            return
        with self._lock, sqlite3.connect(self.db_path) as c:
            row = c.execute(
                "SELECT COALESCE(MAX(seq), -1) + 1 FROM conv WHERE conv_id=?",
                (conv_id,),
            ).fetchone()
            seq = row[0] if row else 0
            c.execute(
                "INSERT INTO conv(conv_id, seq, role, content) VALUES (?, ?, ?, ?)",
                (conv_id, seq, role, content),
            )


_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    """进程级单例。"""
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
