"""会话流式输出：剥离模型思考链，避免展示给用户。"""
from __future__ import annotations

import re

_THINKING_BLOCK_RE = re.compile(
    r"<(?:redacted_thinking|think|thinking)>.*?</(?:redacted_thinking|think|thinking)>\s*",
    re.DOTALL | re.IGNORECASE,
)
_OPEN_TAG_RE = re.compile(r"<(?:redacted_thinking|think|thinking)>", re.IGNORECASE)
_PARTIAL_OPEN_RE = re.compile(
    r"<(?:/?(?:redacted_thinking|think|thinking)?|redacted_thin(?:king)?|think(?:ing)?)?$",
    re.IGNORECASE,
)


def strip_thinking_content(text: str) -> str:
    """移除完整/未闭合 thinking 标签及其内容。"""
    if not text:
        return ""
    s = _THINKING_BLOCK_RE.sub("", text)
    m = _OPEN_TAG_RE.search(s)
    if m:
        s = s[: m.start()]
    s = _PARTIAL_OPEN_RE.sub("", s)
    return s


class ThinkingStreamFilter:
    """流式 token 增量过滤：只输出可见正文 delta。"""

    def __init__(self) -> None:
        self._raw = ""
        self._last_visible = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._raw += chunk
        visible = strip_thinking_content(self._raw)
        delta = visible[len(self._last_visible) :]
        self._last_visible = visible
        return delta

    def visible_text(self) -> str:
        return self._last_visible
