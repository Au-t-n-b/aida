"""
AIDA Agent · 邮件统一出口（《交付 Claw/Agent 工程范式》铁律③）

与 llm.py 对称：**所有外发邮件唯一经此**，禁止任何地方裸用 smtplib / win32com。
默认 dry-run（不真发）；显式 AIDA_SEND_EMAIL=1 后走真实通道。

配置（agent/.env）：
    AIDA_SEND_EMAIL=1
    AIDA_MAIL_BACKEND=outlook | smtp | outlook_http | mailgw
      outlook      — Windows 本地 Outlook COM（华为内网常用，与 nanobot 一致）
      outlook_http — nanobot outlook_service_full.py（默认 http://127.0.0.1:5123）
      smtp         — SMTP_HOST / SMTP_USER / SMTP_PASSWORD …
      mailgw       — mailgw 邮件网关 HTTP API（MAILGW_BASE / MAILGW_TOKEN；
                     白名单分级管控 + 人工审批，GKCLAW 链路推荐通道）
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=False)


def _mail_backend() -> str:
    b = os.environ.get("AIDA_MAIL_BACKEND", "").strip().lower()
    if b:
        return b
    if sys.platform == "win32" and os.environ.get("AIDA_USE_OUTLOOK", "1").strip() != "0":
        return "outlook"
    return "smtp"


def _send_via_outlook_com(
    recipients: list[str],
    subject: str,
    body: str,
    attachments: list[str] | None,
) -> dict[str, Any]:
    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        return {"ok": False, "error": "pywin32 未安装（pip install pywin32）"}

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = "; ".join(recipients)
        mail.Subject = subject
        mail.Body = body
        attached: list[str] = []
        for ap in attachments or []:
            p = Path(ap)
            if p.is_file():
                mail.Attachments.Add(str(p.resolve()))
                attached.append(str(p))
        mail.Send()
        return {
            "ok": True,
            "via": "outlook",
            "to": recipients,
            "subject": subject,
            "attachments": attached,
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "via": "outlook"}


def _send_via_outlook_http(
    recipients: list[str],
    subject: str,
    body: str,
    attachments: list[str] | None,
) -> dict[str, Any]:
    base = os.environ.get("OUTLOOK_SERVICE_URL", "http://127.0.0.1:5123").rstrip("/")
    payload = {
        "to": "; ".join(recipients),
        "subject": subject,
        "body": body,
        "attachments": attachments or [],
    }
    req = urllib.request.Request(
        f"{base}/mail/send",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if data.get("success") or data.get("ok"):
            return {"ok": True, "via": "outlook_http", "to": recipients, "subject": subject}
        return {"ok": False, "error": data.get("error", str(data)), "via": "outlook_http"}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = err.get("error", str(e))
        except Exception:
            msg = str(e)
        return {"ok": False, "error": msg, "via": "outlook_http"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "via": "outlook_http"}


def _send_via_smtp(
    recipients: list[str],
    subject: str,
    body: str,
    attachments: list[str] | None,
) -> dict[str, Any]:
    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER", "").strip()
    pwd = os.environ.get("SMTP_PASSWORD", "").strip()
    sender = os.environ.get("SMTP_FROM", user).strip()
    use_tls = os.environ.get("SMTP_USE_TLS", "").strip().lower() in ("1", "true", "yes")
    if not (host and user and pwd):
        return {"ok": False, "error": "SMTP 未配置（需 SMTP_HOST / SMTP_USER / SMTP_PASSWORD）"}

    ssl_verify = os.environ.get("SMTP_SSL_VERIFY", "true").strip().lower() not in ("0", "false", "no")
    ctx = ssl.create_default_context()
    if not ssl_verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    for ap in attachments or []:
        p = Path(ap)
        if p.is_file():
            msg.add_attachment(
                p.read_bytes(),
                maintype="application",
                subtype="octet-stream",
                filename=p.name,
            )

    try:
        if use_tls or port == 587:
            with smtplib.SMTP(host, port, timeout=60) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=60) as s:
                s.login(user, pwd)
                s.send_message(msg)
        return {"ok": True, "via": "smtp", "to": recipients, "subject": subject, "attachments": attachments or []}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "via": "smtp"}


def _send_via_mailgw(
    recipients: list[str],
    subject: str,
    body: str,
    attachments: list[str] | None,
) -> dict[str, Any]:
    """经 mailgw 邮件网关发送（白名单外收件人会进入人工审批队列）。

    返回扩展字段：mailgw_task_id / mailgw_status（sent | pending_approval），
    供 GKCLAW 链路登记追踪。attachments 为网关所在机器上的本地绝对路径（同机部署约定）。
    """
    base = os.environ.get("MAILGW_BASE", "http://127.0.0.1:8025").rstrip("/")
    token = os.environ.get("MAILGW_TOKEN", "").strip()
    if not token:
        return {"ok": False, "error": "MAILGW_TOKEN 未配置（mailgw Bearer token）", "via": "mailgw"}
    payload = {"to": recipients, "cc": [], "subject": subject,
               "body": body, "attachments": attachments or []}
    req = urllib.request.Request(
        f"{base}/api/send",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = err.get("detail", str(err))
        except Exception:
            msg = str(e)
        return {"ok": False, "error": msg, "via": "mailgw"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "via": "mailgw"}

    status = data.get("status", "")
    out: dict[str, Any] = {
        "ok": status in ("sent", "pending_approval"),
        "via": "mailgw", "to": recipients, "subject": subject,
        "attachments": attachments or [],
        "mailgw_task_id": data.get("task_id", ""),
        "mailgw_status": status,
        "message": data.get("message", ""),
    }
    if not out["ok"]:
        out["error"] = data.get("message", str(data))
    return out


def send_mail(
    to: str | list[str],
    subject: str,
    body: str,
    *,
    attachments: list[str] | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """统一发信入口。返回结构化结果（不抛栈，便于工具/step 消费）。"""
    recipients = [to] if isinstance(to, str) else list(to)

    if dry_run is None:
        dry_run = os.environ.get("AIDA_SEND_EMAIL", "0").strip() != "1"

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "to": recipients,
            "subject": subject,
            "attachments": attachments or [],
            "note": "dry-run：未真实发送（设 AIDA_SEND_EMAIL=1 才发）",
        }

    backend = _mail_backend()
    if backend == "outlook":
        return _send_via_outlook_com(recipients, subject, body, attachments)
    if backend == "outlook_http":
        return _send_via_outlook_http(recipients, subject, body, attachments)
    if backend == "mailgw":
        return _send_via_mailgw(recipients, subject, body, attachments)
    return _send_via_smtp(recipients, subject, body, attachments)
