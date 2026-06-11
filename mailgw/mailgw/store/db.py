"""SQLite 访问层。每次操作开新连接（WAL），JSON 字段自动序列化/反序列化。"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  caller TEXT NOT NULL,
  to_addrs TEXT NOT NULL,
  cc_addrs TEXT NOT NULL DEFAULT '[]',
  subject TEXT NOT NULL,
  body_text TEXT NOT NULL,
  body_html TEXT,
  attachments TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL,
  verdict_reason TEXT,
  reject_reason TEXT,
  approved_by TEXT,
  approved_at TEXT,
  sent_at TEXT,
  smtp_message_id TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE TABLE IF NOT EXISTS inbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uidl TEXT NOT NULL UNIQUE,
  from_addr TEXT NOT NULL,
  to_addrs TEXT NOT NULL DEFAULT '[]',
  subject TEXT NOT NULL DEFAULT '',
  date TEXT,
  body_text TEXT NOT NULL DEFAULT '',
  body_html TEXT,
  snippet TEXT NOT NULL DEFAULT '',
  attachments_meta TEXT NOT NULL DEFAULT '[]',
  fetched_at TEXT NOT NULL,
  is_read INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '{}'
);
"""

_OUTBOX_JSON = ("to_addrs", "cc_addrs", "attachments")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        with self._conn() as con:
            con.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    # ---- outbox ----
    def create_outbox_task(self, *, caller, to_addrs, cc_addrs, subject, body_text,
                           body_html, attachments, status, verdict_reason) -> str:
        task_id = uuid.uuid4().hex
        with self._conn() as con:
            con.execute(
                "INSERT INTO outbox (id, created_at, caller, to_addrs, cc_addrs, subject,"
                " body_text, body_html, attachments, status, verdict_reason)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, _now(), caller, json.dumps(to_addrs), json.dumps(cc_addrs),
                 subject, body_text, body_html, json.dumps(attachments), status, verdict_reason),
            )
        return task_id

    def get_outbox_task(self, task_id: str) -> dict | None:
        with self._conn() as con:
            row = con.execute("SELECT * FROM outbox WHERE id=?", (task_id,)).fetchone()
        return self._outbox_row(row)

    def update_outbox(self, task_id: str, **fields) -> None:
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._conn() as con:
            con.execute(f"UPDATE outbox SET {cols} WHERE id=?", (*fields.values(), task_id))

    def list_outbox_by_status(self, status: str) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM outbox WHERE status=? ORDER BY created_at", (status,)).fetchall()
        return [self._outbox_row(r) for r in rows]

    def list_outbox_recent(self, limit: int = 50) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM outbox ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._outbox_row(r) for r in rows]

    def count_sent_since(self, since_iso: str) -> int:
        with self._conn() as con:
            row = con.execute(
                "SELECT COUNT(*) AS n FROM outbox WHERE status='sent' AND sent_at>=?",
                (since_iso,)).fetchone()
        return row["n"]

    def _outbox_row(self, row) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        for key in _OUTBOX_JSON:
            d[key] = json.loads(d[key])
        return d

    # ---- inbox ----
    def insert_inbox(self, *, uidl, from_addr, to_addrs, subject, date,
                     body_text, body_html, snippet, attachments_meta) -> int:
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO inbox (uidl, from_addr, to_addrs, subject, date, body_text,"
                " body_html, snippet, attachments_meta, fetched_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (uidl, from_addr, json.dumps(to_addrs), subject, date, body_text,
                 body_html, snippet, json.dumps(attachments_meta), _now()),
            )
            return cur.lastrowid

    def known_uidls(self) -> set[str]:
        with self._conn() as con:
            rows = con.execute("SELECT uidl FROM inbox").fetchall()
        return {r["uidl"] for r in rows}

    def list_inbox(self, *, limit: int = 20, unread_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM inbox"
        if unread_only:
            sql += " WHERE is_read=0"
        sql += " ORDER BY id DESC LIMIT ?"
        with self._conn() as con:
            rows = con.execute(sql, (limit,)).fetchall()
        return [self._inbox_row(r) for r in rows]

    def get_inbox(self, mail_id: int) -> dict | None:
        with self._conn() as con:
            row = con.execute("SELECT * FROM inbox WHERE id=?", (mail_id,)).fetchone()
        return self._inbox_row(row)

    def mark_read(self, mail_id: int) -> None:
        with self._conn() as con:
            con.execute("UPDATE inbox SET is_read=1 WHERE id=?", (mail_id,))

    def update_inbox_attachments(self, mail_id: int, attachments_meta: list[dict]) -> None:
        with self._conn() as con:
            con.execute("UPDATE inbox SET attachments_meta=? WHERE id=?",
                        (json.dumps(attachments_meta), mail_id))

    def _inbox_row(self, row) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        d["to_addrs"] = json.loads(d["to_addrs"])
        d["attachments_meta"] = json.loads(d["attachments_meta"])
        return d

    # ---- audit ----
    def add_audit(self, *, actor: str, action: str, detail: dict) -> None:
        with self._conn() as con:
            con.execute("INSERT INTO audit_log (ts, actor, action, detail) VALUES (?,?,?,?)",
                        (_now(), actor, action, json.dumps(detail, ensure_ascii=False)))

    def list_audit(self, limit: int = 100) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["detail"] = json.loads(d["detail"])
            out.append(d)
        return out
