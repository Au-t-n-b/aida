import json

import mailgw.agent_notify as agent_notify


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_notify_agent_inbound_parses_timestamp_task_id(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode())
        captured["timeout"] = timeout
        return _Resp({"ok": True, "triggered_step_retry": True})

    monkeypatch.setattr(agent_notify.urllib.request, "urlopen", fake_urlopen)

    result = agent_notify.notify_agent_inbound(
        mail_id=5,
        subject="[gkclaw] task.result task-20260614191328096-K1903",
        base_url="http://127.0.0.1:7401",
        token="tok",
        sleep_fn=lambda _sec: None,
    )

    assert result["ok"] is True
    assert captured["body"]["task_id"] == "task-20260614191328096-K1903"


def test_notify_agent_inbound_retries_deferred(monkeypatch):
    calls = []
    payloads = [
        {"ok": True, "deferred": True, "retry_after_sec": 0},
        {"ok": True, "deferred": False, "triggered_step_retry": True},
    ]

    def fake_urlopen(req, timeout):
        calls.append(json.loads(req.data.decode()))
        return _Resp(payloads.pop(0))

    monkeypatch.setattr(agent_notify.urllib.request, "urlopen", fake_urlopen)

    result = agent_notify.notify_agent_inbound(
        mail_id=5,
        subject="[gkclaw] task.result task-20260614191328096-K1903",
        base_url="http://127.0.0.1:7401",
        token="tok",
        sleep_fn=lambda _sec: None,
    )

    assert result["triggered_step_retry"] is True
    assert len(calls) == 2
