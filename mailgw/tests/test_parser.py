# tests/test_parser.py
from email.header import Header
from email.message import EmailMessage

from mailgw.core.parser import (html_to_text, make_snippet, parse_raw,
                                sanitize_filename)


def _build_mail(subject="测试主题", body="你好，正文。", html=None, attach=False) -> bytes:
    msg = EmailMessage()
    msg["From"] = "张三 <zhang@corp.com>"
    msg["To"] = "bot@corp.com, li@corp.com"
    msg["Subject"] = subject
    msg["Date"] = "Wed, 10 Jun 2026 09:00:00 +0800"
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    if attach:
        msg.add_attachment(b"PK\x03\x04data", maintype="application",
                           subtype="octet-stream", filename="勘测底表.xlsx")
    return msg.as_bytes()


def test_parse_plain_mail():
    mail = parse_raw(_build_mail())
    assert mail.from_addr == "zhang@corp.com"
    assert mail.to_addrs == ["bot@corp.com", "li@corp.com"]
    assert mail.subject == "测试主题"
    assert "你好，正文。" in mail.body_text
    assert mail.attachments == []


def test_parse_html_only_mail_converts_to_text():
    msg = EmailMessage()
    msg["From"] = "a@corp.com"
    msg["To"] = "bot@corp.com"
    msg["Subject"] = "html"
    msg.set_content("<p>第一段</p><script>evil()</script><p>第二段</p>", subtype="html")
    mail = parse_raw(msg.as_bytes())
    assert "第一段" in mail.body_text and "第二段" in mail.body_text
    assert "evil" not in mail.body_text  # script 内容被剔除


def test_parse_attachment():
    mail = parse_raw(_build_mail(attach=True))
    assert len(mail.attachments) == 1
    assert mail.attachments[0].filename == "勘测底表.xlsx"
    assert mail.attachments[0].content.startswith(b"PK")


def test_parse_gbk_mail_with_rfc2047_subject():
    # 手工构造 GBK 编码邮件（公司邮箱常见）
    subject = Header("工勘报告意见", charset="gb2312").encode()
    body = "同意该报告。".encode("gbk")
    raw = (f"From: wang@corp.com\r\nTo: bot@corp.com\r\nSubject: {subject}\r\n"
           f"Content-Type: text/plain; charset=gb2312\r\n"
           f"Content-Transfer-Encoding: 8bit\r\n\r\n").encode("ascii") + body
    mail = parse_raw(raw)
    assert mail.subject == "工勘报告意见"
    assert "同意该报告。" in mail.body_text


def test_parse_broken_charset_does_not_raise():
    raw = (b"From: x@corp.com\r\nTo: bot@corp.com\r\nSubject: bad\r\n"
           b"Content-Type: text/plain; charset=utf-8\r\n\r\n" + b"\xff\xfe\xfa")
    mail = parse_raw(raw)  # 不抛异常即可
    assert mail.subject == "bad"


def test_html_to_text_keeps_line_breaks():
    text = html_to_text("<div>行一</div><br><div>行二</div>")
    assert "行一" in text and "行二" in text


def test_sanitize_filename_blocks_traversal():
    assert "/" not in sanitize_filename("../../etc/passwd")
    assert "\\" not in sanitize_filename("..\\..\\boot.ini")
    assert sanitize_filename("正常 文件.xlsx") == "正常 文件.xlsx"
    assert sanitize_filename("") == "unnamed"


def test_make_snippet_truncates():
    assert make_snippet("长" * 500) == "长" * 200
    assert make_snippet("短文本") == "短文本"
