"""LangGraph state schema for the per-project chapter-assembly (tailoring) pipeline.

The narrative pipeline writes prose *into* the chapter skeleton; this pipeline decides, per project,
*which* of the ontology-derived chapters apply, in what order, plus a one-line note per chapter — and
parks that decision in the ContingencyOutline overlay so deriveContingencyRisks stays deterministic
(it reads the overlay, never the LLM).
"""
from __future__ import annotations

from typing import Any, TypedDict


class AssemblyState(TypedDict, total=False):
    # inputs
    plan_id: str
    project_key: str
    mode: str  # only_empty | regenerate
    reference_date: str
    persist: bool  # False = suggest-only (AI 建议布局): compute the outline but do not write the overlay
    # working set (populated by gather)
    available: list[dict[str, Any]]  # per-chapter summaries the LLM selects over
    existing: dict[str, Any] | None  # current ContingencyOutline overlay row (or None)
    # outputs
    degraded: bool
    outline: dict[str, Any]  # public_view of the persisted outline (set by persist)
