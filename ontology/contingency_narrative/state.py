"""LangGraph state schema for the chapter-narrative generation pipeline."""
from __future__ import annotations

from typing import Any, TypedDict


class NarrativeState(TypedDict, total=False):
    # inputs
    plan_id: str
    project_key: str
    scope: str  # all | chapter
    chapter_id: str
    mode: str  # only_empty | regenerate | smart_merge
    apply: bool
    reference_date: str
    # working set (populated by gather)
    targets: list[dict[str, Any]]  # per-chapter fact bundles
    existing: dict[str, dict[str, Any]]  # chapterId -> current narrative row (or None)
    # outputs
    degraded: bool
    narratives: list[dict[str, Any]]  # public_view rows (set by persist)
