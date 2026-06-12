"""Standard API response envelope — 00-第8章 §8."""
from __future__ import annotations

from typing import Any


def proposal_meta(
    project_id: str,
    *,
    proposal_version: str = "draft",
    source_layer: str = "draft",
    dependencies: list[dict[str, str]] | None = None,
    manifest_activity: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "projectId": project_id,
        "proposalVersion": proposal_version,
        "sourceLayer": source_layer,
        "dependencies": dependencies or [],
    }
    if manifest_activity:
        meta["manifestActivity"] = manifest_activity
    return meta


def success(data: Any, meta: dict[str, Any]) -> dict[str, Any]:
    return {"data": data, "meta": meta}
