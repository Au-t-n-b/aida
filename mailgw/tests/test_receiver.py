# tests/test_receiver.py
from mailgw.config import Pop3Config
from mailgw.core.receiver import Pop3Receiver, RawMail


class FakePop3:
    """模拟 poplib.POP3：两封邮件，uidl 分别为 u1、u2。"""

    def __init__(self):
        self.calls: list[str] = []
        self.mails = {1: (b"u1", [b"From: a@corp.com", b"", b"hello"]),
                      2: (b"u2", [b"From: b@corp.com", b"", b"world"])}

    def user(self, name):
        self.calls.append(f"user:{name}")

    def pass_(self, password):
        self.calls.append("pass")

    def uidl(self):
        listing = [f"{num} {uid.decode()}".encode() for num, (uid, _) in self.mails.items()]
        return b"+OK", listing, 0

    def retr(self, num):
        return b"+OK", self.mails[num][1], 0

    def quit(self):
        self.calls.append("quit")


def _cfg() -> Pop3Config:
    return Pop3Config(host="pop3.test.com", port=995, ssl=True,
                      username="bot@test.com", password="pass")


def test_fetch_only_new_mails():
    fake = FakePop3()
    receiver = Pop3Receiver(_cfg(), pop3_factory=lambda c: fake)
    result = receiver.fetch_new(known_uidls={"u1"})
    assert [m.uidl for m in result] == ["u2"]
    assert isinstance(result[0], RawMail)
    assert b"world" in result[0].content
    assert "quit" in fake.calls and "pass" in fake.calls


def test_fetch_all_when_no_known():
    receiver = Pop3Receiver(_cfg(), pop3_factory=lambda c: FakePop3())
    result = receiver.fetch_new(known_uidls=set())
    assert [m.uidl for m in result] == ["u1", "u2"]


def test_fetch_nothing_when_all_known():
    receiver = Pop3Receiver(_cfg(), pop3_factory=lambda c: FakePop3())
    assert receiver.fetch_new(known_uidls={"u1", "u2"}) == []
