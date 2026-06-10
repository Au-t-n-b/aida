# tests/test_service.py
from email.message import EmailMessage

import pytest

from mailgw.config import AppConfig, PolicyConfig, Pop3Config, SmtpConfig
from mailgw.core.receiver import RawMail
from mailgw.service import deliver_task, refresh_inbox, submit_send

from tests.conftest import FakeReceiver, FakeSender


def _receiver(mails) -> FakeReceiver:
    r = FakeReceiver()
    r.mails = mails
    return r


@pytest.fixture
def config(tmp_path) -> AppConfig:
    return AppConfig(
        smtp=SmtpConfig(host="h", port=465, ssl=True, username="bot@corp.com",
                        from_addr="bot@corp.com", password="p"),
        pop3=Pop3Config(host="h", port=995, ssl=True, username="bot@corp.com", password="p"),
        policy=PolicyConfig(whitelist_domains=["corp.com"], hourly_limit=2,
                            daily_limit=10, max_attachment_mb=1, max_recipients=3),
        data_dir=tmp_path / "data",
        tokens={"aida": "tok"},
        admin_password="admin",
    )


def _send(db, config, sender, **kw):
    args = dict(caller="aida", to=["a@corp.com"], cc=[], subject="s",
                body_text="b", body_html=None, attachments=[])
    args.update(kw)
    return submit_send(db=db, config=config, sender=sender, **args)


def test_whitelist_hit_sends_immediately(db, config):
    sender = FakeSender()
    result = _send(db, config, sender)
    assert result["status"] == "sent"
    assert len(sender.sent) == 1
    assert db.get_outbox_task(result["task_id"])["smtp_message_id"] == "<mid@test>"
    actions = [r["action"] for r in db.list_audit()]
    assert "send_request" in actions and "auto_sent" in actions


def test_whitelist_miss_queues(db, config):
    sender = FakeSender()
    result = _send(db, config, sender, to=["a@corp.com", "out@other.com"])
    assert result["status"] == "pending_approval"
    assert "out@other.com" in result["message"]      # 提示语包含未命中地址
    assert result["task_id"] in result["message"]    # 提示语包含 task_id
    assert sender.sent == []
    assert db.get_outbox_task(result["task_id"])["status"] == "pending_approval"


def test_validation_rejects(db, config, tmp_path):
    sender = FakeSender()
    assert _send(db, config, sender, to=["bad-address"])["status"] == "rejected"
    assert _send(db, config, sender, attachments=["D:/不存在.docx"])["status"] == "rejected"
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB > 1MB 上限
    assert _send(db, config, sender, attachments=[str(big)])["status"] == "rejected"
    assert _send(db, config, sender,
                 to=["a@corp.com", "b@corp.com", "c@corp.com", "d@corp.com"]
                 )["status"] == "rejected"  # 超 max_recipients=3
    assert sender.sent == []


def test_rate_limit(db, config):
    sender = FakeSender()
    assert _send(db, config, sender)["status"] == "sent"
    assert _send(db, config, sender)["status"] == "sent"
    third = _send(db, config, sender)               # hourly_limit=2
    assert third["status"] == "rejected"
    assert "上限" in third["message"]


def test_send_failure_marks_failed(db, config):
    sender = FakeSender()
    sender.fail = True
    result = _send(db, config, sender)
    assert result["status"] == "failed"
    task = db.get_outbox_task(result["task_id"])
    assert "connection refused" in task["last_error"]


def test_deliver_task_for_approved(db, config):
    """审批通过后调用 deliver_task 走同一发送路径。"""
    sender = FakeSender()
    queued = _send(db, config, sender, to=["out@other.com"])
    task = deliver_task(db=db, sender=sender, task_id=queued["task_id"])
    assert task["status"] == "sent"
    assert len(sender.sent) == 1


def _raw_mail(uidl: str, attach: bool = False) -> RawMail:
    msg = EmailMessage()
    msg["From"] = "expert@corp.com"
    msg["To"] = "bot@corp.com"
    msg["Subject"] = "回复：报告"
    msg.set_content("同意。")
    if attach:
        msg.add_attachment(b"data", maintype="application",
                           subtype="octet-stream", filename="底表.xlsx")
    return RawMail(uidl=uidl, content=msg.as_bytes())


def test_refresh_inbox_saves_mail_and_attachments(db, config):
    receiver = _receiver([_raw_mail("u1", attach=True)])
    assert refresh_inbox(db=db, receiver=receiver, data_dir=config.data_dir) == 1
    assert refresh_inbox(db=db, receiver=receiver, data_dir=config.data_dir) == 0  # 去重
    mail = db.list_inbox(limit=10)[0]
    assert mail["subject"] == "回复：报告"
    meta = db.get_inbox(mail["id"])["attachments_meta"]
    assert meta[0]["filename"] == "底表.xlsx"
    saved = config.data_dir / "attachments" / str(mail["id"]) / "底表.xlsx"
    assert saved.read_bytes() == b"data"


def test_refresh_inbox_isolates_broken_mail(db, config):
    broken = RawMail(uidl="bad", content=b"\xff\xfe not a mail")
    receiver = _receiver([broken, _raw_mail("u2")])
    assert refresh_inbox(db=db, receiver=receiver, data_dir=config.data_dir) >= 1
    assert "u2" in db.known_uidls()  # 坏邮件不中断整次拉取
