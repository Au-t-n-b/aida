"""LLM helpers for chapter tailoring — reuse the project's unified LLM entry.

Delegates model construction to contingency_narrative.llm.get_model() (which goes through
langgraph_agent.llm.get_chat_llm — the only approved ChatOpenAI holder), so there is no new naked
LLM client here and lint_no_naked_llm stays green. Returns None when unavailable; callers degrade.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from contingency_narrative.llm import get_model, model_name  # noqa: F401 (re-exported)

from .prompts import SELECT_SYSTEM

logger = logging.getLogger(__name__)


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


def _strip_json(text: str) -> str:
    """Best-effort: peel a ```json fence / surrounding prose to the outermost JSON object."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
        s = s.strip()
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s


def select_chapters(model: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Ask the LLM to tailor the chapter set; return a parsed dict (empty on parse failure).

    Shape: {"include":[ids], "order":[ids], "notes":{id:str}, "rationale":str}. The graph's select
    node schema-validates the ids against the available chapters, so a malformed/partial parse simply
    yields fewer (or no) selections — never a crash.
    """
    response = model.invoke(
        [
            {"role": "system", "content": SELECT_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
    )
    raw = _message_content(response)
    try:
        parsed = json.loads(_strip_json(raw))
    except (ValueError, TypeError) as exc:
        logger.warning("[assembly_llm] select JSON parse failed: %s", exc)
        return {}
    return parsed if isinstance(parsed, dict) else {}
