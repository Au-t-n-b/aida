# tests/test_db.py
from datetime import datetime, timedelta, timezone

import pytest

from mailgw.store.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_outbox_roundtrip(db):
    task_id = db.create_outbox_task(
        caller="aida", to_addrs=["a@corp.com"], cc_addrs=[],
        subject="标题", body_text="正文", body_html=None,
        attachments=["D:/r/x.docx"], status="pending_approval",
        verdict_reason="b@out.com 不在白名单",
    )
    task = db.get_outbox_task(task_id)
    assert task["status"] == "pending_approval"
    assert task["to_addrs"] == ["a@corp.com"]
    assert task["attachments"] == ["D:/r/x.docx"]

    db.update_outbox(task_id, status="sent", sent_at=_now(), smtp_message_id="<id@x>")
    assert db.get_outbox_task(task_id)["status"] == "sent"
    assert db.get_outbox_task("不存在") is None


def test_list_pending_and_recent(db):
    a = db.create_outbox_task(caller="aida", to_addrs=["x@o.com"], cc_addrs=[],
                              subject="s1", body_text="b", body_html=None,
                              attachments=[], status="pending_approval", verdict_reason="")
    db.create_outbox_task(caller="aida", to_addrs=["y@corp.com"], cc_addrs=[],
                          subject="s2", body_text="b", body_html=None,
                          attachments=[], status="sent", verdict_reason="")
    pending = db.list_outbox_by_status("pending_approval")
    assert [t["id"] for t in pending] == [a]
    assert len(db.list_outbox_recent(limit=50)) == 2


def test_count_sent_since(db):
    db.create_outbox_task(caller="aida", to_addrs=["x@corp.com"], cc_addrs=[],
                          subject="s", body_text="b", body_html=None,
                          attachments=[], status="sent", verdict_reason="")
    task = db.list_outbox_recent(limit=1)[0]
    db.update_outbox(task["id"], sent_at=_now())
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert db.count_sent_since(one_hour_ago) == 1
    assert db.count_sent_since(tomorrow) == 0


def test_inbox_roundtrip(db):
    mail_id = db.insert_inbox(
        uidl="u1", from_addr="e@corp.com", to_addrs=["bot@corp.com"],
        subject="回复", date="2026-06-10T09:00:00+00:00",
        body_text="正文" * 100, body_html=None, snippet="正文",
        attachments_meta=[{"filename": "表.xlsx", "size": 10, "path": "data/attachments/1/表.xlsx"}],
    )
    assert db.known_uidls() == {"u1"}
    rows = db.list_inbox(limit=10, unread_only=True)
    assert rows[0]["id"] == mail_id and rows[0]["is_read"] == 0

    db.mark_read(mail_id)
    assert db.list_inbox(limit=10, unread_only=True) == []
    full = db.get_inbox(mail_id)
    assert full["attachments_meta"][0]["filename"] == "表.xlsx"


def test_audit(db):
    db.add_audit(actor="aida", action="send_request", detail={"to": ["a@corp.com"]})
    rows = db.list_audit(limit=10)
    assert rows[0]["action"] == "send_request"
    assert rows[0]["detail"]["to"] == ["a@corp.com"]
