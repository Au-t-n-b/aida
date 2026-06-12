"""Bridge chapter 2 device info into 8.3 maintenance strategy assembly."""
from __future__ import annotations

from typing import Any

from agent.proposal.draft_store import load_chapter_02


def build_chapter02_device_index(
    project_id: str,
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    """Return device models and model → chapter-2 row (with EOS fields)."""
    payload = load_chapter_02(project_id, "draft")
    allowed: set[str] = set()
    by_model: dict[str, dict[str, Any]] = {}

    for row in payload.get("rows") or []:
        model = (row.get("deviceModel") or "").strip()
        if not model:
            continue
        allowed.add(model)
        existing = by_model.get(model)
        if existing is None or _row_has_eos(row) and not _row_has_eos(existing):
            by_model[model] = row

    return allowed, by_model


def match_product_model_to_device(candidate: str, allowed: set[str]) -> str | None:
    """Map a BOQ-derived product model to a chapter-2 deviceModel, if any."""
    text = (candidate or "").strip()
    if not text or not allowed:
        return None
    if text in allowed:
        return text
    for model in sorted(allowed, key=len, reverse=True):
        if text.startswith(model) or model in text:
            return model
    return None


def eos_date_from_device_row(row: dict[str, Any]) -> str | None:
    """Prefer actual EOS, fall back to planned EOS (aligned with chapter 2 / PBI §17)."""
    actu = (row.get("eosActualDate") or "").strip()
    if actu:
        return actu[:10]
    plan = (row.get("eosPlanDate") or "").strip()
    if plan:
        return plan[:10]
    return None


def _row_has_eos(row: dict[str, Any]) -> bool:
    return bool((row.get("eosActualDate") or row.get("eosPlanDate") or "").strip())
