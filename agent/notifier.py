"""
AIDA Agent · 即时消息统一出口（《交付 Claw/Agent 工程范式》规范 4 · 副作用统一）

与 mailer.py 对称：所有 WeLink / 小鲁班 等 IM 外发**唯一经此**，禁止任何地方裸调
welink 网关（守门见 scripts/lint_no_naked_send.py）。

特性：
  - 默认 dry-run（防误发）：AIDA_SEND_IM=1 才真发；
  - 进程内限流：滑动窗口（默认 20/min）+ 日计数（默认 200/day），与官方 30/min、300/day 留余量；
  - 鉴权优先级：env XIAOLUBAN_AUTH / WELINK_XLB_AUTH > （未来可接 config）；
  - 富文本（HTML span）+ 表格（等宽文本，不引 PrettyTable）。

配置（agent/.env）：
    AIDA_SEND_IM=1            打开真实发送（默认 0 = dry-run）
    XIAOLUBAN_URL            小鲁班网关 URL
    XIAOLUBAN_AUTH           鉴权 token（或 WELINK_XLB_AUTH）
    WELINK_RATE_PER_MIN      限频/分钟（默认 20）
    WELINK_RATE_PER_DAY      限频/天（默认 200）
"""
from __future__ import annotations

import os
import time
from datetime import date
from threading import Lock
from typing import Any

# ── 进程内限流状态 ──
_send_timestamps: list[float] = []   # 滑动窗口（秒级时间戳）
_daily_count: dict[str, int] = {}    # {YYYY-MM-DD: count}
_lock = Lock()


def _rate_per_min() -> int:
    return int(os.environ.get("WELINK_RATE_PER_MIN", "20"))


def _rate_per_day() -> int:
    return int(os.environ.get("WELINK_RATE_PER_DAY", "200"))


def check_rate(consume: bool = True) -> tuple[bool, str]:
    """滑动窗口（60s）+ 日计数限流。consume=True 时通过则预占额度。返回 (ok, reason)。"""
    now = time.time()
    today = date.today().isoformat()
    with _lock:
        cutoff = now - 60
        global _send_timestamps
        _send_timestamps = [t for t in _send_timestamps if t > cutoff]
        if len(_send_timestamps) >= _rate_per_min():
            return False, f"超过每分钟限频（{_rate_per_min()}/min）"
        if _daily_count.get(today, 0) >= _rate_per_day():
            return False, f"超过每日限频（{_rate_per_day()}/day）"
        if consume:
            _send_timestamps.append(now)
            _daily_count[today] = _daily_count.get(today, 0) + 1
    return True, ""


def _reset_rate_limit() -> None:
    """仅供测试：清空限流状态。"""
    with _lock:
        _send_timestamps.clear()
        _daily_count.clear()


def format_table(headers: list[str], rows: list[list[Any]]) -> str:
    """等宽文本表格（Consolas 包裹的 <pre>），不引 PrettyTable。"""
    cols = len(headers)
    widths = [len(str(headers[i])) for i in range(cols)]
    for r in rows:
        for i in range(cols):
            cell = str(r[i]) if i < len(r) else ""
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cells: list[Any]) -> str:
        return " | ".join(
            (str(cells[i]) if i < len(cells) else "").ljust(widths[i]) for i in range(cols)
        )

    sep = "-+-".join("-" * w for w in widths)
    body = "\n".join([fmt_row(headers), sep, *[fmt_row(r) for r in rows]])
    return f'<pre style="font-family:Consolas,monospace">{body}</pre>'


def _auth() -> str:
    return (os.environ.get("XIAOLUBAN_AUTH", "") or os.environ.get("WELINK_XLB_AUTH", "")).strip()


def send_welink(
    receiver: str,
    content: str = "",
    *,
    table_headers: list[str] | None = None,
    table_rows: list[list[Any]] | None = None,
    sender: str | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """统一 IM 发送入口。返回结构化结果（不抛栈，便于工具/step 消费）。"""
    if not receiver:
        return {"ok": False, "error": "receiver 不能为空（群 ID 或工号）"}

    # 组装正文：表格拼到 content 之后
    body = content or ""
    if table_headers and table_rows:
        body = (body + "\n" if body else "") + format_table(table_headers, table_rows)
    if not body:
        return {"ok": False, "error": "content / table 至少给一个"}

    # dry-run 判定：显式参数 > 环境开关（默认关 = dry-run）
    if dry_run is None:
        dry_run = os.environ.get("AIDA_SEND_IM", "0").strip() != "1"

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "receiver": receiver,
            "preview": body[:200],
            "note": "dry-run：未真实发送（设 AIDA_SEND_IM=1 才发）",
        }

    url = os.environ.get("XIAOLUBAN_URL", "").strip()
    auth = _auth()
    if not (url and auth):
        return {"ok": False, "error": "小鲁班未配置（需 XIAOLUBAN_URL + XIAOLUBAN_AUTH）"}

    ok, reason = check_rate(consume=True)
    if not ok:
        return {"ok": False, "error": f"限流：{reason}"}

    payload: dict[str, Any] = {"content": body, "receiver": receiver, "auth": auth}
    if sender:
        payload["sender"] = sender
    try:
        import httpx
        resp = httpx.post(url, json=payload, timeout=15)
        return {
            "ok": resp.status_code == 200,
            "receiver": receiver,
            "status": resp.status_code,
            "response": resp.text[:300],
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
