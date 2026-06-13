"""Run-record overlay persistence for ContingencyOutline (按项目的预案章节裁剪决策).

One overlay row per projectKey holds the tailored chapter set: `include` (which chapters apply),
`order` (their sequence), `notes` (a per-chapter project caption), plus the human pins
(`pinnedInclude` / `pinnedExclude`) that survive re-tailoring. Reuses data_connector's overlay
helpers (same schema/runtime/*.json store as ChapterNarrative). Every data_connector import is lazy
to avoid a circular import. `apply_outline` is a pure function (no langgraph) so deriveContingencyRisks
can apply the cached decision without pulling the LLM stack.

Human-pin-first, non-destructive re-tailoring:
  * the LLM proposes include/order/notes;
  * pinnedInclude forces a chapter in, pinnedExclude forces it out — both win over the LLM and are
    never cleared by a regenerate (mirrors ChapterNarrative.editedText priority).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from contingency_narrative.store import resolve_project_key  # shared 京东 anchor

logger = logging.getLogger(__name__)

OUTLINE_OBJECT = "ContingencyOutline"

# 章节「融合」组：组 id 前缀。include/order 里出现组 id 即代表其成员被折叠成一个「组章」。
GROUP_CHAPTER_PREFIX = "doc-grp-"

# 子决策点 → 中文标签（组章 decisionLabel 由 decisionPoint 映射，与目录章口径一致）。
_DECISION_LABELS = {
    "network": "组网配置可交付性",
    "device": "设备配置可交付性",
    "service": "部件配置可交付性",
    "acceptance": "验收可交付性",
    "global": "全局输入",
}


def is_group_chapter_id(chapter_id: str) -> bool:
    """doc-grp-* → True（融合组章 id）。"""
    return str(chapter_id or "").startswith(GROUP_CHAPTER_PREFIX)


def _dc():  # lazy import to avoid circular dependency with data_connector
    import data_connector as dc

    return dc


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def outline_pk(project_key: str) -> str:
    return f"OUTLINE__{project_key}"


def _ordered_unique(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        s = str(item or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


# --------------------------------------------------------------------------- overlay row I/O

def _read_outline_rows() -> list[dict[str, Any]]:
    return _dc()._read_contingency_runrecord(OUTLINE_OBJECT)


def _write_outline_rows(rows: list[dict[str, Any]]) -> None:
    _dc()._write_contingency_runrecord(OUTLINE_OBJECT, rows)


def read_outline(project_key: str | None) -> dict[str, Any] | None:
    target = outline_pk(resolve_project_key(project_key))
    for row in _read_outline_rows():
        if str(row.get("contingencyOutlineId") or "") == target:
            return row
    return None


def new_outline_row(project_key: str | None, *, plan_id: str | None = None) -> dict[str, Any]:
    pk = resolve_project_key(project_key)
    return {
        "contingencyOutlineId": outline_pk(pk),
        "projectKey": pk,
        "planId": plan_id or "",
        "include": [],
        "order": [],
        "notes": {},
        "groups": {},
        "pinnedInclude": [],
        "pinnedExclude": [],
        "rationale": "",
        "status": "ai_draft",
        "generatedModel": "",
        "generatedAt": "",
        "editedBy": "",
        "editedAt": "",
        "versions": [],
    }


def upsert_outline(row: dict[str, Any]) -> dict[str, Any]:
    pk = str(row.get("contingencyOutlineId") or "")
    rows = [r for r in _read_outline_rows() if str(r.get("contingencyOutlineId") or "") != pk]
    rows.append(row)
    _write_outline_rows(rows)
    return row


def append_version(
    row: dict[str, Any], source: str, *, by: str | None = None, note: str | None = None
) -> dict[str, Any]:
    versions = row.get("versions")
    if not isinstance(versions, list):
        versions = []
    seq = (int(versions[-1].get("seq", 0)) + 1) if versions else 1
    versions.append(
        {
            "seq": seq,
            "source": source,  # ai | human
            "include": list(row.get("include") or []),
            "order": list(row.get("order") or []),
            "groups": dict(row.get("groups") or {}),
            "savedAt": _now_iso(),
            "by": by or "",
            "note": note or "",
        }
    )
    row["versions"] = versions
    return row


def public_view(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "projectKey": row.get("projectKey"),
        "include": list(row.get("include") or []),
        "order": list(row.get("order") or []),
        "notes": dict(row.get("notes") or {}),
        "groups": dict(row.get("groups") or {}),
        "pinnedInclude": list(row.get("pinnedInclude") or []),
        "pinnedExclude": list(row.get("pinnedExclude") or []),
        "rationale": row.get("rationale") or "",
        "status": row.get("status") or "ai_draft",
        "generatedModel": row.get("generatedModel") or "",
        "generatedAt": row.get("generatedAt") or "",
        "editedAt": row.get("editedAt") or "",
        "chapterCount": len(row.get("include") or []),
        "versions": row.get("versions") or [],
    }


# --------------------------------------------------------------------------- pure overlay application

def _build_group_chapter(
    gid: str, group: dict[str, Any], by_id: dict[str, dict[str, Any]], notes: dict[str, Any]
) -> dict[str, Any] | None:
    """Fold a group's member chapters into one composite「组章」dict (复合章：保留成员表 + AI 概述).

    Members are looked up from the full derived directory (`by_id`); ad-hoc members (doc-ot-*) must
    have been materialized upstream so they're present. The composite **nests the full member chapter
    dicts** under `members` (each keeps its rows/columns/detailRows/fields/objectType/title/source so
    the report renders每个成员原始表单) and aggregates member riskIds (union) so the group still
    surfaces bound risks. The group itself carries NO top-level rows/columns — its only prose is the
    fused AI 概述 (ChapterNarrative[gid]) rendered above the member sub-sections. Returns None when no
    member resolves (drop the empty group).
    """
    member_ids = [str(m) for m in (group.get("members") or []) if str(m) in by_id]
    if not member_ids:
        return None
    members = [by_id[m] for m in member_ids]
    risk_ids: list[str] = []
    seen_r: set[str] = set()
    for member in members:
        for rid in member.get("riskIds") or []:
            rid = str(rid)
            if rid and rid not in seen_r:
                seen_r.add(rid)
                risk_ids.append(rid)
    dp = str(group.get("decisionPoint") or "").strip() or str(members[0].get("decisionPoint") or "global")
    title = str(group.get("title") or "").strip() or "／".join(
        str(m.get("title") or "") for m in members
    )
    composite: dict[str, Any] = {
        "id": gid,
        "no": "",  # renumbered by the frontend (mapGenerationToView) by position
        "title": title,
        "isGroup": True,
        "memberIds": member_ids,
        "memberTitles": [str(m.get("title") or "") for m in members],
        "members": members,  # full member chapter dicts → report renders each member's original table
        "decisionPoint": dp,
        "decisionLabel": _DECISION_LABELS.get(dp, str(members[0].get("decisionLabel") or "全局输入")),
        "desc": "",
        "riskIds": risk_ids,
        "state": "gap" if risk_ids else "ok",
    }
    note = notes.get(gid)
    if isinstance(note, str) and note.strip():
        composite["assemblyNote"] = note.strip()
    return composite


def apply_outline(
    chapters: list[dict[str, Any]], outline_row: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Filter+reorder the derived chapter directory by a project's cached outline (pure, no LLM).

    No outline (or an empty `include`) returns the full directory unchanged — graceful default before
    any tailoring has run. Otherwise: keep only included chapters, ordered by `order` (any included id
    missing from `order` is appended in include-order), and attach the per-chapter project caption as
    `assemblyNote` (non-destructive — the skeleton `desc` is preserved).

    Fusion groups: when an included id is a `doc-grp-*` group, its member chapters are folded into one
    composite「组章」(see _build_group_chapter) and the members never render standalone (the group owns
    them — defensive even if a stale include still lists a member id separately).
    """
    if not outline_row:
        return chapters
    include = _ordered_unique([str(x) for x in (outline_row.get("include") or [])])
    if not include:
        return chapters
    groups = outline_row.get("groups")
    if not isinstance(groups, dict):
        groups = {}
    include_set = set(include)
    notes = outline_row.get("notes") or {}
    by_id = {str(c.get("id") or ""): c for c in chapters}

    def _selectable(cid: str) -> bool:
        return cid in by_id or cid in groups

    order = _ordered_unique([str(x) for x in (outline_row.get("order") or [])])
    seq = [cid for cid in order if cid in include_set and _selectable(cid)]
    for cid in include:
        if _selectable(cid) and cid not in seq:
            seq.append(cid)

    # Members consumed by a surviving group must not also render as standalone chapters.
    grouped_members: set[str] = set()
    for gid in seq:
        if gid in groups and isinstance(groups[gid], dict):
            for m in groups[gid].get("members") or []:
                grouped_members.add(str(m))

    out: list[dict[str, Any]] = []
    for cid in seq:
        if cid in groups and isinstance(groups[cid], dict):
            composite = _build_group_chapter(cid, groups[cid], by_id, notes)
            if composite is not None:
                out.append(composite)
            continue
        if cid in grouped_members:
            continue
        chapter = by_id[cid]
        note = notes.get(cid)
        if isinstance(note, str) and note.strip():
            chapter = {**chapter, "assemblyNote": note.strip()}
        out.append(chapter)
    return out


# --------------------------------------------------------------------------- human-driven op (no LLM)

def pin_chapter(
    project_key: str | None,
    chapter_id: str,
    action: str,
    *,
    edited_by: str | None = None,
) -> dict[str, Any]:
    """Human pin a chapter include/exclude (or clear back to auto). Survives re-tailoring.

    `action`: include = force in · exclude = force out · auto = drop the pin (let the LLM decide).
    Recomputes the effective include/order when a selection already exists; when no outline has been
    generated yet, the pin is recorded and takes effect on the next assemble.
    """
    if not chapter_id:
        raise ValueError("chapter_id 必填")
    action = (action or "").strip()
    if action not in ("include", "exclude", "auto"):
        raise ValueError("action 必须为 include | exclude | auto")
    row = read_outline(project_key) or new_outline_row(project_key)
    pin_inc = set(str(x) for x in (row.get("pinnedInclude") or []))
    pin_exc = set(str(x) for x in (row.get("pinnedExclude") or []))
    if action == "include":
        pin_inc.add(chapter_id)
        pin_exc.discard(chapter_id)
    elif action == "exclude":
        pin_exc.add(chapter_id)
        pin_inc.discard(chapter_id)
    else:  # auto
        pin_inc.discard(chapter_id)
        pin_exc.discard(chapter_id)
    row["pinnedInclude"] = sorted(pin_inc)
    row["pinnedExclude"] = sorted(pin_exc)
    base = [str(x) for x in (row.get("include") or [])]
    if base:  # an outline exists -> apply the pin to the effective selection immediately
        include = _ordered_unique([c for c in base + sorted(pin_inc) if c not in pin_exc])
        # Restoring (auto) or force-including a chapter that was previously excluded must bring it
        # back into the visible set: exclude dropped it from the cached include, and pin is LLM-free
        # so it can't be re-derived — without this, 恢复 would clear the exclude pin but never re-show
        # the chapter (it would only reappear on the next full assemble).
        if action in ("include", "auto") and chapter_id not in pin_exc and chapter_id not in include:
            include.append(chapter_id)
        order = _ordered_unique([c for c in (row.get("order") or []) if c in set(include)] + include)
        row["include"] = include
        row["order"] = order
    row["status"] = "human_pinned"
    row["editedBy"] = edited_by or ""
    row["editedAt"] = _now_iso()
    append_version(row, "human", by=edited_by, note=f"{action}:{chapter_id}")
    return public_view(upsert_outline(row))


def set_include(
    project_key: str | None,
    chapter_ids: list[str],
    *,
    groups: dict[str, Any] | None = None,
    edited_by: str | None = None,
) -> dict[str, Any]:
    """Set the chapter selection explicitly, **preserving the given order** (拖拽组装的真相).

    Deterministic, LLM-free: `include` and `order` both become exactly `chapter_ids` (deduped, order
    preserved — the drag order IS the chapter order). `groups` (full overlay-replacing map of
    doc-grp-* → {title, members, decisionPoint}) records the fusion groups referenced by group ids in
    chapter_ids; passing None clears them (an explicit selection carries its own complete group state).
    Human pins are cleared (an explicit selection supersedes prior pins; status='manual'). This is the
    write path behind the drag-to-compose UI; deriveContingencyRisks then filters+orders+folds by this
    selection via apply_outline, so reordering elements reorders the report sections.
    """
    ids = _ordered_unique([str(x) for x in (chapter_ids or [])])
    row = read_outline(project_key) or new_outline_row(project_key)
    row["include"] = list(ids)
    row["order"] = list(ids)
    row["groups"] = dict(groups) if isinstance(groups, dict) else {}
    row["pinnedInclude"] = []
    row["pinnedExclude"] = []
    row["status"] = "manual"
    row["editedBy"] = edited_by or ""
    row["editedAt"] = _now_iso()
    append_version(row, "human", by=edited_by, note="manual set_include")
    return public_view(upsert_outline(row))


def set_group_title(
    project_key: str | None,
    group_id: str,
    title: str,
    *,
    source: str = "ai",
) -> bool:
    """Write back a fusion group's title (LLM-fused 章名)，**人工改名优先永不被覆盖**.

    Updates `groups[group_id].title` only when its `titleBy` is not 'human' (a manual rename in the
    composer pins titleBy='human'). Marks `titleBy=source` ('ai'). Returns True if written, else False
    (no overlay / no such group / human-pinned / empty title). Called by the narrative graph after it
    fuses a title so the composer + next derive reflect it. No-op-safe.
    """
    title = str(title or "").strip()
    if not group_id or not title:
        return False
    row = read_outline(project_key)
    if not row:
        return False
    groups = row.get("groups")
    if not isinstance(groups, dict):
        return False
    group = groups.get(group_id)
    if not isinstance(group, dict):
        return False
    if str(group.get("titleBy") or "") == "human":
        return False  # human rename wins — never clobber
    group["title"] = title
    group["titleBy"] = source
    groups[group_id] = group
    row["groups"] = groups
    row["editedAt"] = _now_iso()
    upsert_outline(row)
    return True


def group_title(project_key: str | None, group_id: str) -> tuple[str, str]:
    """Return a group's (title, titleBy) from the overlay, or ('','') when absent. Read-only helper."""
    row = read_outline(project_key)
    groups = (row or {}).get("groups") if isinstance(row, dict) else None
    group = groups.get(group_id) if isinstance(groups, dict) else None
    if not isinstance(group, dict):
        return "", ""
    return str(group.get("title") or ""), str(group.get("titleBy") or "")


def reset_outline(project_key: str | None) -> dict[str, Any]:
    """Clear a project's tailoring overlay → 还原默认章节目录.

    Removes the ContingencyOutline row entirely, so deriveContingencyRisks (apply_outline) returns the
    full ontology-derived directory again and listContingencyChapters reports every chapter included.
    No-op-safe when no overlay exists.
    """
    pk = resolve_project_key(project_key)
    target = outline_pk(pk)
    rows = [r for r in _read_outline_rows() if str(r.get("contingencyOutlineId") or "") != target]
    _write_outline_rows(rows)
    return {"projectKey": pk, "include": [], "order": [], "status": "default", "chapterCount": 0}
