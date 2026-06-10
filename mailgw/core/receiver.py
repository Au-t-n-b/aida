"""收件通道（spec §6）：MailReceiver 接口 + POP3 实现，UIDL 去重，不删服务器邮件。"""
import poplib
from dataclasses import dataclass
from typing import Callable, Protocol

from mailgw.config import Pop3Config


@dataclass
class RawMail:
    uidl: str
    content: bytes


class MailReceiver(Protocol):
    def fetch_new(self, known_uidls: set[str]) -> list[RawMail]:
        """拉取本地未见过的邮件原文。实现方负责连接的建立与关闭。"""
        ...


def _default_factory(cfg: Pop3Config):
    if cfg.ssl:
        return poplib.POP3_SSL(cfg.host, cfg.port, timeout=30)
    return poplib.POP3(cfg.host, cfg.port, timeout=30)


class Pop3Receiver:
    def __init__(self, cfg: Pop3Config, pop3_factory: Callable | None = None):
        self.cfg = cfg
        self.pop3_factory = pop3_factory or _default_factory

    def fetch_new(self, known_uidls: set[str]) -> list[RawMail]:
        client = self.pop3_factory(self.cfg)
        try:
            client.user(self.cfg.username)
            client.pass_(self.cfg.password)
            _, listing, _ = client.uidl()
            new: list[RawMail] = []
            for line in listing:
                num_str, uidl = line.decode().split(" ", 1)
                if uidl in known_uidls:
                    continue
                _, lines, _ = client.retr(int(num_str))
                new.append(RawMail(uidl=uidl, content=b"\r\n".join(lines)))
            return new
        finally:
            try:
                client.quit()
            except Exception:
                pass
