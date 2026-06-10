"""SMTP 发送（spec §10）：每次新建连接，指数退避重试。"""
import mimetypes
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Callable

from mailgw.config import SmtpConfig

RETRY_DELAYS = (1, 4, 16)


class SendError(Exception):
    """重试耗尽后抛出，message 为最后一次错误。"""


def _default_factory(cfg: SmtpConfig):
    if cfg.ssl:
        return smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=30)
    client = smtplib.SMTP(cfg.host, cfg.port, timeout=30)
    client.ehlo()
    if client.has_extn("starttls"):
        client.starttls()
        client.ehlo()
    return client


class SmtpSender:
    def __init__(self, cfg: SmtpConfig,
                 smtp_factory: Callable | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.cfg = cfg
        self.smtp_factory = smtp_factory or _default_factory
        self.sleep = sleep

    def send(self, *, to: list[str], cc: list[str], subject: str, body_text: str,
             body_html: str | None = None, attachments: list[str] | None = None) -> str:
        msg = self._build(to=to, cc=cc, subject=subject, body_text=body_text,
                          body_html=body_html, attachments=attachments or [])
        last_error: Exception | None = None
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                client = self.smtp_factory(self.cfg)
                try:
                    client.login(self.cfg.username, self.cfg.password)
                    client.send_message(msg)
                finally:
                    try:
                        client.quit()
                    except Exception:
                        pass
                return msg["Message-ID"]
            except Exception as exc:  # noqa: BLE001 —— 网络/协议错误统一重试
                last_error = exc
                if attempt < len(RETRY_DELAYS):
                    self.sleep(RETRY_DELAYS[attempt])
        raise SendError(str(last_error))

    def _build(self, *, to, cc, subject, body_text, body_html, attachments) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = formataddr((self.cfg.display_name or None, self.cfg.from_addr))
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        msg["Message-ID"] = make_msgid()
        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")
        for path_str in attachments:
            path = Path(path_str)
            ctype, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
            msg.add_attachment(path.read_bytes(), maintype=maintype,
                               subtype=subtype, filename=path.name)
        return msg
