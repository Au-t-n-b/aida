# tests/test_sender.py
import pytest

from mailgw.config import SmtpConfig
from mailgw.core.sender import SendError, SmtpSender


class FakeSmtp:
    """记录调用的假 SMTP 客户端；fail_times 控制前 N 次 send_message 抛错。"""
    instances: list["FakeSmtp"] = []
    fail_times = 0

    def __init__(self):
        self.logged_in = None
        self.sent = []
        FakeSmtp.instances.append(self)

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        if FakeSmtp.fail_times > 0:
            FakeSmtp.fail_times -= 1
            raise ConnectionResetError("boom")
        self.sent.append(msg)

    def quit(self):
        pass


@pytest.fixture
def cfg() -> SmtpConfig:
    return SmtpConfig(host="smtp.test.com", port=465, ssl=True, username="bot@test.com",
                      from_addr="bot@test.com", password="pass", display_name="测试机器人")


@pytest.fixture
def sender(cfg):
    FakeSmtp.instances = []
    FakeSmtp.fail_times = 0
    sleeps: list[float] = []
    s = SmtpSender(cfg, smtp_factory=lambda c: FakeSmtp(), sleep=sleeps.append)
    s._test_sleeps = sleeps  # 仅测试用
    return s


def test_send_builds_message(sender, tmp_path):
    f = tmp_path / "报告.docx"
    f.write_bytes(b"PK\x03\x04")
    message_id = sender.send(to=["a@corp.com"], cc=["b@corp.com"], subject="主题",
                             body_text="正文", attachments=[str(f)])
    msg = FakeSmtp.instances[-1].sent[0]
    assert msg["To"] == "a@corp.com"
    assert msg["Cc"] == "b@corp.com"
    assert msg["Subject"] == "主题"
    assert "测试机器人" in msg["From"]
    assert message_id == msg["Message-ID"]
    assert FakeSmtp.instances[-1].logged_in == ("bot@test.com", "pass")
    filenames = [p.get_filename() for p in msg.iter_attachments()]
    assert filenames == ["报告.docx"]


def test_retry_then_success(sender):
    FakeSmtp.fail_times = 2
    sender.send(to=["a@corp.com"], cc=[], subject="s", body_text="b")
    assert sender._test_sleeps == [1, 4]          # 失败两次 → 退避两次
    assert len(FakeSmtp.instances) == 3           # 每次尝试新建连接


def test_all_retries_fail_raises(sender):
    FakeSmtp.fail_times = 99
    with pytest.raises(SendError):
        sender.send(to=["a@corp.com"], cc=[], subject="s", body_text="b")
    assert sender._test_sleeps == [1, 4, 16]      # 共尝试 4 次
