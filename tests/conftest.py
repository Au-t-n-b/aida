# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from mailgw.app import build_app
from mailgw.config import AppConfig, PolicyConfig, Pop3Config, SmtpConfig
from mailgw.core.sender import SendError
from mailgw.store.db import Database


class FakeSender:
    def __init__(self):
        self.sent = []
        self.fail = False

    def send(self, **kw):
        if self.fail:
            raise SendError("connection refused")
        self.sent.append(kw)
        return "<mid@test>"


class FakeReceiver:
    def __init__(self):
        self.mails = []

    def fetch_new(self, known_uidls):
        return [m for m in self.mails if m.uidl not in known_uidls]


@pytest.fixture
def app_config(tmp_path) -> AppConfig:
    return AppConfig(
        smtp=SmtpConfig(host="h", port=465, ssl=True, username="bot@corp.com",
                        from_addr="bot@corp.com", password="p"),
        pop3=Pop3Config(host="h", port=995, ssl=True, username="bot@corp.com", password="p"),
        policy=PolicyConfig(whitelist_domains=["corp.com"], hourly_limit=100,
                            daily_limit=100, max_attachment_mb=25, max_recipients=20),
        data_dir=tmp_path / "data",
        tokens={"aida": "tok-aida"},
        admin_password="admin-pass",
    )


@pytest.fixture
def fake_sender() -> FakeSender:
    return FakeSender()


@pytest.fixture
def fake_receiver() -> FakeReceiver:
    return FakeReceiver()


@pytest.fixture
def db(tmp_path) -> Database:
    return Database(tmp_path / "t.db")


@pytest.fixture
def client(app_config, db, fake_sender, fake_receiver) -> TestClient:
    app = build_app(app_config, db=db, sender=fake_sender, receiver=fake_receiver)
    return TestClient(app, headers={"Authorization": "Bearer tok-aida"})
