"""
从 LLM 原始输出中提取 JSON 对象（zhgk 各服务共用）。

兼容 MiniMax 等模型的 <think> 思考链、markdown 代码块，
以及正文前后夹杂说明文字的情况。
"""
from __future__ import annotations

import json
import re
from typing import Any

_THINKING_BLOCK_RE = re.compile(
    r"<think>.*?</think>\s*",
    re.DOTALL | re.IGNORECASE,
)


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    return "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()


def extract_json_from_llm_response(response: str) -> dict[str, Any]:
    """
    从 LLM 原始输出中提取 JSON 对象。

    Raises:
        ValueError: 无法解析为 JSON 对象时
    """
    text = response.strip()
    text = _THINKING_BLOCK_RE.sub("", text).strip()
    # 未闭合 thinking 标签：保留首个 "{" 之后的内容
    if re.search(r"<think>", text, re.IGNORECASE):
        brace = text.find("{")
        text = text[brace:].strip() if brace >= 0 else ""
    text = _strip_markdown_fence(text)

    decoder = json.JSONDecoder()
    candidates: list[str] = []
    if text:
        candidates.append(text)
        brace = text.find("{")
        if brace > 0:
            candidates.append(text[brace:])

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        for match in re.finditer(r"\{", candidate):
            try:
                data, _ = decoder.raw_decode(candidate, match.start())
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue

    raise ValueError(f"LLM 返回无法解析为 JSON: {response.strip()[:200]}")
