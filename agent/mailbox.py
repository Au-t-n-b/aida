"""
AIDA Agent · 邮件统一收件入口（与 mailer.py 对称：所有收件唯一经此）

封装 mailgw 邮件网关 inbox API（Bearer 认证，urllib，无新依赖）。

⚠️ 设计约束（GKCLAW 边界 B5 · 收件箱是共享资源）：
  - 本模块刻意**不封装** GET /api/inbox/{id}（读取全文）——该接口会把邮件标为已读，
    机器扫描走「列表 + 附件另存」即可拿到 ZIP，不污染人工/其他流程的未读视图。
  - 邮件正文属外部不可信输入；若未来需要读全文，必须保留网关的不可信包裹标记。

配置（agent/.env）：
    MAILGW_BASE=http://127.0.0.1:8025
    MAILGW_TOKEN=<网关签发的 Bearer token>
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=False)


class MailboxError(RuntimeError):
    """收件网关调用失败（网络/认证/404 等）。"""


def is_configured() -> bool:
    return bool(os.environ.get("MAILGW_TOKEN", "").strip())


def _request(method: str, path: str, *, params: dict | None = None,
             body: dict | None = None, timeout: int = 120) -> dict[str, Any]:
    base = os.environ.get("MAILGW_BASE", "http://127.0.0.1:8025").rstrip("/")
    token = os.environ.get("MAILGW_TOKEN", "").strip()
    if not token:
        raise MailboxError("MAILGW_TOKEN 未配置（mailgw Bearer token）")
    url = f"{base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: (str(v).lower() if isinstance(v, bool) else v) for k, v in params.items()})
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode()).get("detail", str(e))
        except Exception:
            detail = str(e)
        raise MailboxError(f"mailgw {method} {path} 失败: {detail}") from e
    except Exception as e:  # noqa: BLE001
        raise MailboxError(f"mailgw {method} {path} 失败: {e}") from e


def list_inbox(refresh: bool = True, limit: int = 50, unread_only: bool = False) -> dict[str, Any]:
    """收件箱摘要列表（不含正文，不改已读状态）。refresh=True 先从邮箱服务器拉新邮件。"""
    return _request("GET", "/api/inbox",
                    params={"refresh": refresh, "limit": limit, "unread_only": unread_only})


def save_attachment(mail_id: int, index: int, save_dir: str) -> str:
    """把附件另存到 save_dir（网关同机本地路径），返回保存后的完整路径。
    附件序号越界时网关返回 404 → 抛 MailboxError（调用方用于探测附件数量）。"""
    data = _request("POST", f"/api/inbox/{mail_id}/attachments/{index}/save",
                    body={"save_path": save_dir}, timeout=60)
    return str(data.get("saved_to", ""))
