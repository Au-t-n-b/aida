"""
会话/工勘工具调用本地日志 · Langfuse 未配或 span 无 conv_id 时的评测数据源。

每次 execute_traced 追加一行 JSONL → eval_tools.load_records 优先读取。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_LOG_DIR = Path(__file__).parent / "results" / "session_logs"


def _log_path(key: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)[:120]
    return _LOG_DIR / f"{safe}.jsonl"


def append_tool_record(
    *,
    tool: str,
    ok: bool,
    latency_ms: int,
    scope: str = "",
    step: str = "",
    run_id: str = "",
    conv_id: str = "",
    error: str = "",
) -> None:
    key = conv_id or run_id
    if not key:
        return
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "tool": tool,
        "ok": ok,
        "latency_ms": latency_ms,
        "scope": scope,
        "step": step,
        "run_id": run_id,
        "conv_id": conv_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "error": error[:200] if error else "",
    }
    with _log_path(key).open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_session_records(
    *,
    conv_id: str | None = None,
    run_id: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """按 conv_id 或 run_id 读本地 JSONL（conv 优先）。"""
    key = (conv_id or "").strip() or (run_id or "").strip()
    if not key:
        return []
    path = _log_path(key)
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return records[-limit:]
