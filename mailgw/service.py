"""编排层：发送流程（spec §5.2）、审批后投递、收件刷新（spec §6）。"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mailgw.config import AppConfig
from mailgw.core.parser import make_snippet, parse_raw, sanitize_filename
from mailgw.core.policy import check_whitelist
from mailgw.core.receiver import MailReceiver
from mailgw.core.sender import SendError, SmtpSender
from mailgw.store.db import Database

_ADDR_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate(*, to, cc, attachments, policy) -> str | None:
    """返回 None 表示通过，否则返回中文拒绝原因。"""
    recipients = to + cc
    if not recipients:
        return "收件人不能为空。"
    if len(recipients) > policy.max_recipients:
        return f"收件人数 {len(recipients)} 超过单封上限 {policy.max_recipients}。"
    for addr in recipients:
        if not _ADDR_RE.match(addr.strip()):
            return f"收件人地址格式不正确：{addr}。"
    total = 0
    for p in attachments:
        path = Path(p)
        if not path.is_file():
            return f"附件不存在：{p}。请确认路径（网关与调用方需在同一台机器上）。"
        total += path.stat().st_size
    if total > policy.max_attachment_mb * 1024 * 1024:
        return f"附件总大小超过 {policy.max_attachment_mb}MB 上限。"
    return None


def _check_rate(db: Database, policy) -> str | None:
    hour_ago = (_now() - timedelta(hours=1)).isoformat()
    day_ago = (_now() - timedelta(days=1)).isoformat()
    if db.count_sent_since(hour_ago) >= policy.hourly_limit:
        return f"已达每小时发送上限（{policy.hourly_limit} 封/小时），请稍后再试。"
    if db.count_sent_since(day_ago) >= policy.daily_limit:
        return f"已达每日发送上限（{policy.daily_limit} 封/天），请明天再试。"
    return None


def submit_send(*, db: Database, config: AppConfig, sender: SmtpSender, caller: str,
                to: list[str], cc: list[str], subject: str, body_text: str,
                body_html: str | None, attachments: list[str]) -> dict:
    to = [a.strip().lower() for a in to]
    cc = [a.strip().lower() for a in cc]
    db.add_audit(actor=caller, action="send_request",
                 detail={"to": to, "cc": cc, "subject": subject})

    reason = (_validate(to=to, cc=cc, attachments=attachments, policy=config.policy)
              or _check_rate(db, config.policy))
    if reason:
        task_id = db.create_outbox_task(
            caller=caller, to_addrs=to, cc_addrs=cc, subject=subject,
            body_text=body_text, body_html=body_html, attachments=attachments,
            status="rejected", verdict_reason=reason)
        db.update_outbox(task_id, reject_reason=reason)
        db.add_audit(actor=caller, action="rejected", detail={"task_id": task_id, "reason": reason})
        return {"task_id": task_id, "status": "rejected", "message": reason}

    verdict = check_whitelist(to + cc, config.policy)
    if verdict.allowed:
        task_id = db.create_outbox_task(
            caller=caller, to_addrs=to, cc_addrs=cc, subject=subject,
            body_text=body_text, body_html=body_html, attachments=attachments,
            status="pending_approval", verdict_reason="白名单全部命中，直发")
        task = deliver_task(db=db, sender=sender, task_id=task_id)
        if task["status"] == "sent":
            db.add_audit(actor=caller, action="auto_sent", detail={"task_id": task_id})
            return {"task_id": task_id, "status": "sent",
                    "message": f"邮件已发出（task_id={task_id}）。"}
        return {"task_id": task_id, "status": "failed",
                "message": f"发送失败：{task['last_error']}（task_id={task_id}，"
                           f"可用 check_send_status 查询，稍后重试或联系管理员）。"}

    misses = "、".join(verdict.misses)
    task_id = db.create_outbox_task(
        caller=caller, to_addrs=to, cc_addrs=cc, subject=subject,
        body_text=body_text, body_html=body_html, attachments=attachments,
        status="pending_approval", verdict_reason=f"未命中白名单：{misses}")
    db.add_audit(actor=caller, action="queued", detail={"task_id": task_id, "misses": verdict.misses})
    return {"task_id": task_id, "status": "pending_approval",
            "message": f"收件人 {misses} 不在白名单，邮件已转入待审批队列"
                       f"（task_id={task_id}），审批通过后将自动发出，"
                       f"可用 check_send_status 查询进度。"}


def deliver_task(*, db: Database, sender: SmtpSender, task_id: str) -> dict:
    """实际投递（直发与审批通过共用）。返回更新后的任务。"""
    task = db.get_outbox_task(task_id)
    try:
        message_id = sender.send(to=task["to_addrs"], cc=task["cc_addrs"],
                                 subject=task["subject"], body_text=task["body_text"],
                                 body_html=task["body_html"], attachments=task["attachments"])
        db.update_outbox(task_id, status="sent", sent_at=_now().isoformat(),
                         smtp_message_id=message_id)
    except SendError as exc:
        db.update_outbox(task_id, status="failed", last_error=str(exc))
        db.add_audit(actor="system", action="send_failed",
                     detail={"task_id": task_id, "error": str(exc)})
    return db.get_outbox_task(task_id)


def refresh_inbox(*, db: Database, receiver: MailReceiver, data_dir: Path) -> int:
    """拉取新邮件入库，附件落盘。单封解析失败隔离（记审计、跳过）。"""
    new_count = 0
    for raw in receiver.fetch_new(db.known_uidls()):
        try:
            mail = parse_raw(raw.content)
            mail_id = db.insert_inbox(
                uidl=raw.uidl, from_addr=mail.from_addr, to_addrs=mail.to_addrs,
                subject=mail.subject, date=mail.date, body_text=mail.body_text,
                body_html=mail.body_html, snippet=make_snippet(mail.body_text),
                attachments_meta=[])
            meta = []
            attach_dir = data_dir / "attachments" / str(mail_id)
            for att in mail.attachments:
                attach_dir.mkdir(parents=True, exist_ok=True)
                safe_name = sanitize_filename(att.filename)
                (attach_dir / safe_name).write_bytes(att.content)
                meta.append({"filename": safe_name, "size": len(att.content),
                             "path": str(attach_dir / safe_name)})
            if meta:
                db.update_inbox_attachments(mail_id, meta)
            new_count += 1
        except Exception as exc:  # noqa: BLE001 —— 单封隔离
            db.add_audit(actor="system", action="fetch_error",
                         detail={"uidl": raw.uidl, "error": str(exc)})
    db.add_audit(actor="system", action="fetch", detail={"new_count": new_count})
    return new_count
