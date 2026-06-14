"""mailgw → AIDA Agent GKCLAW 入站回调（127.0.0.1 · Bearer）。"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Callable

log = logging.getLogger(__name__)

_TASK_ID_RE = re.compile(r"task-\d{8,20}-[A-Z0-9]+(?:-\d+)?", re.I)
_GKCLAW_HINT = re.compile(r"task\.(import_ack|result|error)|\[gkclaw\]", re.I)


def _parse_task_id(subject: str) -> str | None:
    m = _TASK_ID_RE.search(subject or "")
    return m.group(0) if m else None


def is_gkclaw_subject(subject: str) -> bool:
    return bool(_GKCLAW_HINT.search(subject or ""))


def notify_agent_inbound(
    *,
    mail_id: int,
    subject: str,
    base_url: str,
    token: str,
    skill: str = "zhgk",
    timeout: int = 30,
    attempts: int = 3,
    retry_sleep_sec: float = 5.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict | None:
    """POST Agent /agent/{skill}/gkclaw/inbound。失败只打日志，不抛栈。"""
    if not base_url or not token:
        return None
    if not is_gkclaw_subject(subject):
        return None
    task_id = _parse_task_id(subject)
    url = f"{base_url.rstrip('/')}/agent/{skill}/gkclaw/inbound"
    body = {"mail_id": mail_id, "task_id": task_id, "subject": subject}
    max_attempts = max(1, int(attempts or 1))
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
                if result.get("deferred") and attempt < max_attempts:
                    sleep_fn(float(result.get("retry_after_sec") or retry_sleep_sec))
                    continue
                return result
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode()
            except Exception:
                detail = str(e)
            log.warning("agent inbound HTTP %s: %s", e.code, detail[:200])
        except Exception as exc:  # noqa: BLE001
            log.warning("agent inbound failed mail#%s: %s", mail_id, exc)
        if attempt < max_attempts:
            sleep_fn(retry_sleep_sec)
    return None


def load_notify_config(raw: dict | None) -> dict:
    """config.yaml agent_notify 段 + 环境变量兜底。"""
    raw = raw or {}
    return {
        "enabled": bool(raw.get("enabled", True)),
        "base_url": (
            os.environ.get("AGENT_NOTIFY_BASE")
            or raw.get("base_url")
            or "http://127.0.0.1:7401"
        ),
        "token": (
            raw.get("token")
            or os.environ.get("AGENT_NOTIFY_TOKEN")
            or os.environ.get("MAILGW_TOKEN_AIDA")
            or ""
        ),
        "skill": raw.get("skill") or "zhgk",
    }
