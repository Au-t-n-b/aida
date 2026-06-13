"""LLM helpers for chapter narrative generation — reuse the project's unified LLM entry.

get_chat_llm() (ontology/langgraph_agent/llm.py) delegates to aida/agent's agent/llm.py — the only
approved ChatOpenAI holder (ZHIPU/百炼 + Langfuse). Returns None when langchain/key is unavailable;
callers degrade gracefully (no narrative written). This mirrors plan_compression.py's pattern, so it
passes lint_no_naked_llm (no new naked LLM client here).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .prompts import (
    GENERATE_SYSTEM,
    GROUP_FUSION_SYSTEM,
    GROUP_TITLE_SYSTEM,
    MERGE_SYSTEM,
    PROJECT_OVERVIEW_CHAPTER_ID,
    PROJECT_OVERVIEW_SYSTEM,
)

logger = logging.getLogger(__name__)


def get_model() -> Any | None:
    """Return the configured chat model, or None when unavailable (graceful degrade)."""
    try:
        from langgraph_agent.llm import get_chat_llm
    except Exception as exc:  # pragma: no cover - import guard
        logger.warning("[narrative_llm] get_chat_llm import failed: %s", exc)
        return None
    try:
        return get_chat_llm()
    except Exception as exc:  # pragma: no cover - construction guard
        logger.warning("[narrative_llm] get_chat_llm() failed: %s", exc)
        return None


def model_name(model: Any) -> str:
    try:
        return str(getattr(model, "model_name", "") or getattr(model, "model", "") or "")
    except Exception:
        return ""


def _message_content(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p)
    return str(content or "")


def _invoke(model: Any, system: str, user_payload: dict[str, Any]) -> str:
    response = model.invoke(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
    )
    return _message_content(response).strip()


def generate_chapter_text(model: Any, fact: dict[str, Any]) -> str:
    """Write one (non-group) chapter's prose from its fact bundle.

    The 项目背景 overview gets the one-sentence overview prompt; everything else uses the per-chapter
    prompt. Fusion groups go through generate_group_title_and_intro instead (title + 导语, not full text).
    """
    system = (
        PROJECT_OVERVIEW_SYSTEM
        if str(fact.get("chapterId") or "") == PROJECT_OVERVIEW_CHAPTER_ID
        else GENERATE_SYSTEM
    )
    return _invoke(model, system, fact)


def _parse_title_intro(raw: str) -> tuple[str, str]:
    """Parse the group-fusion LLM output {"title","intro"}; tolerate code fences / surrounding prose.

    Falls back to ('', whole-text-as-intro) when no JSON object is found, so a non-conforming model
    still yields a usable 概述 (the title then keeps its 拼接 default upstream).
    """
    s = (raw or "").strip()
    if not s:
        return "", ""
    if s.startswith("```"):
        s = s.strip("`")
        nl = s.find("\n")
        if nl != -1 and s[:nl].strip().lower() in ("json", ""):
            s = s[nl + 1:]
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(s[start:end + 1])
            if isinstance(obj, dict):
                return str(obj.get("title") or "").strip(), str(obj.get("intro") or "").strip()
        except (json.JSONDecodeError, ValueError):
            pass
    return "", s


def _clean_title(raw: str) -> str:
    """First non-empty line, stripped of quotes/编号/标点装饰，capped — for the title-only fallback."""
    for line in (raw or "").splitlines():
        t = line.strip().strip("「」\"'《》#*·-—:：。、 ").strip()
        if t:
            return t[:40]
    return ""


def generate_group_title(model: Any, fact: dict[str, Any]) -> str:
    """Dedicated, tightly-constrained title-only call — reliable even when models won't emit JSON."""
    return _clean_title(_invoke(model, GROUP_TITLE_SYSTEM, fact))


def generate_group_title_and_intro(model: Any, fact: dict[str, Any]) -> tuple[str, str]:
    """Fuse a group's members into (fused_title, intro 导语). Robust: one JSON call, title fallback.

    Member data tables are rendered separately in the report, so the intro is an overview/导语 (ties the
    members together, points out key risks), not a restatement of every row. Live models don't always
    honor「只输出 JSON」—— when the parse yields no title, a dedicated title-only call (trivially
    compliant) guarantees the 章名 still gets LLM-fused; the prose then serves as the intro.
    """
    title, intro = _parse_title_intro(_invoke(model, GROUP_FUSION_SYSTEM, fact))
    if not title:
        try:
            title = generate_group_title(model, fact)
        except Exception:  # pragma: no cover - title fallback is best-effort
            title = ""
    return title, intro


def merge_chapter_text(model: Any, prior_ai: str, human_edited: str, facts: dict[str, Any]) -> str:
    """Fuse the latest facts into a human edit without losing the human's changes (3-way merge)."""
    payload = {"priorAi": prior_ai or "", "humanEdited": human_edited or "", "facts": facts}
    return _invoke(model, MERGE_SYSTEM, payload)
