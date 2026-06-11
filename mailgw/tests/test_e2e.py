# tests/test_e2e.py
import socket
import threading
from email.message import EmailMessage

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult
from fastapi.testclient import TestClient

from mailgw.app import build_app
from mailgw.config import AppConfig, PolicyConfig, Pop3Config, SmtpConfig
from mailgw.store.db import Database


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class SmtpHandler:
    def __init__(self):
        self.messages = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(envelope)
        return "250 Message accepted"


def _authenticator(server, session, envelope, mechanism, auth_data):
    return AuthResult(success=True)


class Pop3Stub(threading.Thread):
    """极简 POP3 服务器：USER/PASS/STAT/UIDL/RETR/QUIT。
    未实现行首句点的字节填充——测试邮件内容避免出现行首句点即可。"""

    def __init__(self, mails: list[tuple[str, bytes]]):
        super().__init__(daemon=True)
        self.mails = mails
        self.sock = socket.create_server(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]

    def run(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                rfile = conn.makefile("rb")

                def send(line: bytes):
                    conn.sendall(line + b"\r\n")

                send(b"+OK mailgw test stub")
                while True:
                    line = rfile.readline()
                    if not line:
                        break
                    parts = line.decode().strip().split(" ")
                    cmd = parts[0].upper()
                    if cmd in ("USER", "PASS"):
                        send(b"+OK")
                    elif cmd == "STAT":
                        send(f"+OK {len(self.mails)} 0".encode())
                    elif cmd == "UIDL":
                        send(b"+OK")
                        for i, (uidl, _) in enumerate(self.mails, 1):
                            send(f"{i} {uidl}".encode())
                        send(b".")
                    elif cmd == "RETR":
                        _, raw = self.mails[int(parts[1]) - 1]
                        send(b"+OK")
                        for raw_line in raw.split(b"\r\n"):
                            send(raw_line)
                        send(b".")
                    elif cmd == "QUIT":
                        send(b"+OK")
                        break
                    else:
                        send(b"-ERR")

    def close(self):
        self.sock.close()


def _expert_mail() -> bytes:
    msg = EmailMessage()
    msg["From"] = "expert@corp.com"
    msg["To"] = "bot@corp.com"
    msg["Subject"] = "回复：工勘报告"
    msg.set_content("同意该报告，可以分发。")
    return msg.as_bytes()


@pytest.fixture
def stack(tmp_path):
    handler = SmtpHandler()
    smtp_port = _free_port()
    controller = Controller(handler, hostname="127.0.0.1", port=smtp_port,
                            authenticator=_authenticator, auth_required=True,
                            auth_require_tls=False)
    controller.start()
    pop3 = Pop3Stub([("e1", _expert_mail())])
    pop3.start()

    config = AppConfig(
        smtp=SmtpConfig(host="127.0.0.1", port=smtp_port, ssl=False,
                        username="bot@corp.com", from_addr="bot@corp.com",
                        password="p", display_name="AIDA"),
        pop3=Pop3Config(host="127.0.0.1", port=pop3.port, ssl=False,
                        username="bot@corp.com", password="p"),
        policy=PolicyConfig(whitelist_domains=["corp.com"],
                            hourly_limit=100, daily_limit=100),
        data_dir=tmp_path / "data",
        tokens={"aida": "tok"},
        admin_password="adm",
    )
    app = build_app(config, db=Database(tmp_path / "e2e.db"))
    client = TestClient(app, headers={"Authorization": "Bearer tok"})
    yield client, handler
    controller.stop()
    pop3.close()


def test_e2e_direct_send(stack):
    client, handler = stack
    resp = client.post("/api/send", json={"to": ["a@corp.com"],
                                          "subject": "测试", "body": "正文"})
    assert resp.json()["status"] == "sent"
    assert len(handler.messages) == 1
    assert handler.messages[0].rcpt_tos == ["a@corp.com"]


def test_e2e_approval_flow(stack):
    client, handler = stack
    task_id = client.post("/api/send", json={"to": ["out@other.com"],
                                             "subject": "需审批", "body": "正文"}
                          ).json()["task_id"]
    assert handler.messages == []
    client.post(f"/admin/approve/{task_id}", auth=("admin", "adm"),
                follow_redirects=False)
    assert len(handler.messages) == 1
    status = client.get(f"/api/send/{task_id}").json()
    assert status["status"] == "sent"


def test_e2e_receive_flow(stack):
    client, _ = stack
    data = client.get("/api/inbox?refresh=true").json()
    assert data["new_count"] == 1
    mail = data["mails"][0]
    assert mail["subject"] == "回复：工勘报告"
    full = client.get(f"/api/inbox/{mail['mail_id']}").json()
    assert full["untrusted"] is True
    assert "同意该报告" in full["body"]
