# tests/test_api_send.py


def test_requires_token(client):
    resp = client.post("/api/send", json={"to": ["a@corp.com"], "subject": "s", "body": "b"},
                       headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401
    resp = client.post("/api/send", json={"to": ["a@corp.com"], "subject": "s", "body": "b"},
                       headers={"Authorization": ""})
    assert resp.status_code == 401


def test_send_whitelisted(client, fake_sender):
    resp = client.post("/api/send", json={"to": ["a@corp.com"], "subject": "主题", "body": "正文"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert len(fake_sender.sent) == 1


def test_send_outside_whitelist_queues(client, fake_sender):
    resp = client.post("/api/send", json={"to": ["x@other.com"], "subject": "s", "body": "b"})
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert fake_sender.sent == []


def test_check_send_status(client):
    task_id = client.post("/api/send", json={"to": ["a@corp.com"], "subject": "s",
                                             "body": "b"}).json()["task_id"]
    resp = client.get(f"/api/send/{task_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sent"
    assert body["task_id"] == task_id
    assert client.get("/api/send/不存在的id").status_code == 404
