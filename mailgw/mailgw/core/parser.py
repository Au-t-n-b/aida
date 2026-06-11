"""MIME 解析与编码容错（spec §6）。"""
import re
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.header import decode_header
from email.message import Message
from email.utils import getaddresses, parseaddr
from html.parser import HTMLParser


@dataclass
class Attachment:
    filename: str
    content: bytes


@dataclass
class ParsedMail:
    from_addr: str
    to_addrs: list[str]
    subject: str
    date: str | None
    body_text: str
    body_html: str | None
    attachments: list[Attachment] = field(default_factory=list)


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style"}
    _BREAK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BREAK:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self) -> str:
        merged = "".join(self._chunks)
        return re.sub(r"\n{3,}", "\n\n", merged).strip()


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.text()


def decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def sanitize_filename(name: str) -> str:
    name = decode_mime_header(name)
    name = re.sub(r'[\\/:*?"<>|\r\n]', "_", name).strip().strip(".")
    return name or "unnamed"


def make_snippet(text: str, limit: int = 200) -> str:
    return text[:limit]


def _part_text(part: Message) -> str:
    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:  # 未知 charset 名
        return payload.decode("utf-8", errors="replace")


def parse_raw(raw: bytes) -> ParsedMail:
    msg = message_from_bytes(raw, policy=policy.compat32)

    from_addr = parseaddr(decode_mime_header(msg.get("From")))[1].lower()
    to_addrs = [addr.lower() for _, addr in
                getaddresses([decode_mime_header(msg.get("To", ""))]) if addr]
    subject = decode_mime_header(msg.get("Subject"))
    date = msg.get("Date")

    body_text, body_html = "", None
    attachments: list[Attachment] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        disposition = (part.get("Content-Disposition") or "").lower()
        if filename or disposition.startswith("attachment"):
            attachments.append(Attachment(
                filename=sanitize_filename(filename or "unnamed"),
                content=part.get_payload(decode=True) or b"",
            ))
        elif part.get_content_type() == "text/plain" and not body_text:
            body_text = _part_text(part)
        elif part.get_content_type() == "text/html" and body_html is None:
            body_html = _part_text(part)

    if not body_text and body_html:
        body_text = html_to_text(body_html)
    return ParsedMail(from_addr=from_addr, to_addrs=to_addrs, subject=subject,
                      date=date, body_text=body_text, body_html=body_html,
                      attachments=attachments)
