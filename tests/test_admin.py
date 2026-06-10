# tests/test_admin.py

AUTH = ("admin", "admin-pass")  # 同 conftest 中 app_config.admin_password


def _queue_task(client) -> str:
    """经 API 投一封白名单外邮件，进入待审批队列。"""
    resp = client.post("/api/send", json={"to": ["out@other.com"],
                                          "subject": "待审主题", "body": "正文"})
    return resp.json()["task_id"]


def test_admin_requires_basic_auth(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=("admin", "wrong")).status_code == 401


def test_admin_lists_pending(client):
    _queue_task(client)
    resp = client.get("/admin", auth=AUTH)
    assert resp.status_code == 200
    assert "待审主题" in resp.text
    assert "out@other.com" in resp.text


def test_approve_sends_mail(client, db, fake_sender):
    task_id = _queue_task(client)
    resp = client.post(f"/admin/approve/{task_id}", auth=AUTH, follow_redirects=False)
    assert resp.status_code == 303
    task = db.get_outbox_task(task_id)
    assert task["status"] == "sent"
    assert task["approved_by"] == "admin"
    assert len(fake_sender.sent) == 1
    # 重复审批被拒
    assert client.post(f"/admin/approve/{task_id}", auth=AUTH,
                       follow_redirects=False).status_code == 409


def test_reject_with_reason(client, db, fake_sender):
    task_id = _queue_task(client)
    resp = client.post(f"/admin/reject/{task_id}", auth=AUTH,
                       data={"reason": "收件人不明"}, follow_redirects=False)
    assert resp.status_code == 303
    task = db.get_outbox_task(task_id)
    assert task["status"] == "rejected"
    assert task["reject_reason"] == "收件人不明"
    assert fake_sender.sent == []
    # agent 侧能查到驳回原因
    status = client.get(f"/api/send/{task_id}").json()
    assert status["status"] == "rejected"
    assert status["reject_reason"] == "收件人不明"
