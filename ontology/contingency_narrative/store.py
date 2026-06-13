"""Run-record overlay persistence for ChapterNarrative + PlanVersionLog (预案章节正文 + 整案版本里程碑).

Reuses data_connector's overlay helpers (``_read/_write_contingency_runrecord``) so narratives live
in the same ``schema/runtime/*.json`` store as other writable run-records. Every data_connector
import is **lazy** (inside functions) to avoid a circular import: data_connector exposes thin
wrappers that delegate back here.

Design — human-edit-first, non-destructive regeneration:
  * ``generatedText``  = the latest AI draft.
  * ``editedText``     = the human edit (kept separate; once set, regeneration never clobbers it).
  * ``displayText``    = editedText if non-empty else generatedText.
  * ``pendingGenerated`` = a re-generation of a human-edited chapter parks its new draft here
    (status -> regen_pending) so the UI can offer "有新版本待合并" without losing the human edit.
  * ``mergeCandidate`` = a smart-merge (priorAI + humanEdit + latest facts) parks its fused draft
    here for review; accepted via accept_chapter_merge.
  * ``versions``       = append-only JSON history (per-chapter), tagged with versionLabel on milestone save.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

NARRATIVE_OBJECT = "ChapterNarrative"
VERSION_OBJECT = "PlanVersionLog"

# Display anchor — mirrors the frontend CONTINGENCY_ANCHOR (projectKey=京东) so a
# deriveContingencyRisks call that carries no project_key still resolves narratives generated under
# the anchor. Narratives are keyed by (projectKey, chapterId), stable regardless of planId.
DEFAULT_PROJECT_KEY = "京东"
DEFAULT_PLAN_ID = "JD_A3_CONTINGENCY"


def resolve_project_key(project_key: str | None) -> str:
    return (project_key or "").strip() or DEFAULT_PROJECT_KEY


def _dc():  # lazy import to avoid circular dependency with data_connector
    import data_connector as dc

    return dc


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def narrative_pk(project_key: str, chapter_id: str) -> str:
    return f"{project_key}__{chapter_id}"


# --------------------------------------------------------------------------- overlay row I/O

def _read_narrative_rows() -> list[dict[str, Any]]:
    return _dc()._read_contingency_runrecord(NARRATIVE_OBJECT)


def _write_narrative_rows(rows: list[dict[str, Any]]) -> None:
    _dc()._write_contingency_runrecord(NARRATIVE_OBJECT, rows)


def read_all_narratives(project_key: str | None) -> list[dict[str, Any]]:
    pk = resolve_project_key(project_key)
    return [r for r in _read_narrative_rows() if str(r.get("projectKey") or "") == pk]


def read_narrative(project_key: str | None, chapter_id: str) -> dict[str, Any] | None:
    target = narrative_pk(resolve_project_key(project_key), chapter_id)
    for row in _read_narrative_rows():
        if str(row.get("chapterNarrativeId") or "") == target:
            return row
    return None


def new_narrative_row(
    project_key: str | None,
    chapter_id: str,
    *,
    plan_id: str | None = None,
    chapter_no: str | None = None,
    chapter_title: str | None = None,
) -> dict[str, Any]:
    pk = resolve_project_key(project_key)
    return {
        "chapterNarrativeId": narrative_pk(pk, chapter_id),
        "projectKey": pk,
        "planId": plan_id or "",
        "chapterId": chapter_id,
        "chapterNo": chapter_no or "",
        "chapterTitle": chapter_title or "",
        "generatedText": "",
        "editedText": "",
        "status": "ai_draft",
        "pendingGenerated": "",
        "mergeCandidate": "",
        "versions": [],
        "generatedModel": "",
        "generatedAt": "",
        "editedBy": "",
        "editedAt": "",
    }


def display_text(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    edited = str(row.get("editedText") or "").strip()
    return edited if edited else str(row.get("generatedText") or "")


def upsert_narrative(row: dict[str, Any]) -> dict[str, Any]:
    pk = str(row.get("chapterNarrativeId") or "")
    rows = [r for r in _read_narrative_rows() if str(r.get("chapterNarrativeId") or "") != pk]
    rows.append(row)
    _write_narrative_rows(rows)
    return row


def append_version(
    row: dict[str, Any],
    source: str,
    text: str,
    *,
    by: str | None = None,
    note: str | None = None,
    version_label: str | None = None,
) -> dict[str, Any]:
    versions = row.get("versions")
    if not isinstance(versions, list):
        versions = []
    seq = (int(versions[-1].get("seq", 0)) + 1) if versions else 1
    versions.append(
        {
            "seq": seq,
            "source": source,  # ai | human | merge | restore | milestone
            "text": text or "",
            "savedAt": _now_iso(),
            "by": by or "",
            "note": note or "",
            "versionLabel": version_label,
        }
    )
    row["versions"] = versions
    return row


def public_view(row: dict[str, Any]) -> dict[str, Any]:
    """Trim a stored narrative row to the fields the frontend consumes."""
    return {
        "chapterId": row.get("chapterId"),
        "chapterNo": row.get("chapterNo"),
        "chapterTitle": row.get("chapterTitle"),
        "status": row.get("status") or "ai_draft",
        "displayText": display_text(row),
        "generatedText": row.get("generatedText") or "",
        "editedText": row.get("editedText") or "",
        "pendingGenerated": row.get("pendingGenerated") or "",
        "mergeCandidate": row.get("mergeCandidate") or "",
        "generatedModel": row.get("generatedModel") or "",
        "generatedAt": row.get("generatedAt") or "",
        "editedAt": row.get("editedAt") or "",
        "versions": row.get("versions") or [],
    }


# --------------------------------------------------------------------------- human-driven ops (no LLM)

def edit_chapter_narrative(
    project_key: str | None,
    chapter_id: str,
    text: str,
    *,
    edited_by: str | None = None,
    chapter_no: str | None = None,
    chapter_title: str | None = None,
) -> dict[str, Any]:
    if not chapter_id:
        raise ValueError("chapter_id 必填")
    row = read_narrative(project_key, chapter_id) or new_narrative_row(
        project_key, chapter_id, chapter_no=chapter_no, chapter_title=chapter_title
    )
    row["editedText"] = text or ""
    row["status"] = "human_edited"
    row["editedBy"] = edited_by or ""
    row["editedAt"] = _now_iso()
    # Editing manually = the human chose their own text over any AI candidate -> clear candidates.
    row["pendingGenerated"] = ""
    row["mergeCandidate"] = ""
    append_version(row, "human", text or "", by=edited_by)
    return public_view(upsert_narrative(row))


def accept_chapter_merge(
    project_key: str | None,
    chapter_id: str,
    choice: str,
    *,
    edited_by: str | None = None,
) -> dict[str, Any]:
    row = read_narrative(project_key, chapter_id)
    if not row:
        raise ValueError(f"章节正文不存在：{chapter_id}")
    choice = (choice or "").strip()
    if choice == "mine":
        row["status"] = "human_edited"
    elif choice == "new":
        new_text = str(row.get("pendingGenerated") or row.get("generatedText") or "")
        row["editedText"] = new_text
        row["status"] = "merged"
        append_version(row, "ai", new_text, by=edited_by, note="采纳新生成稿")
    elif choice == "candidate":
        candidate = str(row.get("mergeCandidate") or "")
        if not candidate.strip():
            raise ValueError("无智能融合候选稿可采纳")
        row["editedText"] = candidate
        row["status"] = "merged"
        append_version(row, "merge", candidate, by=edited_by, note="采纳智能融合稿")
    else:
        raise ValueError("choice 必须为 mine | new | candidate")
    row["pendingGenerated"] = ""
    row["mergeCandidate"] = ""
    row["editedBy"] = edited_by or row.get("editedBy") or ""
    row["editedAt"] = _now_iso()
    return public_view(upsert_narrative(row))


def restore_chapter_narrative_version(
    project_key: str | None,
    chapter_id: str,
    *,
    seq: str | int | None = None,
    version_label: str | None = None,
    edited_by: str | None = None,
) -> dict[str, Any]:
    row = read_narrative(project_key, chapter_id)
    if not row:
        raise ValueError(f"章节正文不存在：{chapter_id}")
    versions = row.get("versions") or []
    target = None
    if seq is not None and str(seq).strip():
        target = next((v for v in versions if str(v.get("seq")) == str(seq).strip()), None)
    elif version_label:
        matches = [v for v in versions if v.get("versionLabel") == version_label]
        target = matches[-1] if matches else None
    if not target:
        raise ValueError("未找到指定的历史版本（按 seq 或 version_label 定位）")
    text = str(target.get("text") or "")
    row["editedText"] = text
    row["status"] = "human_edited"
    row["editedBy"] = edited_by or ""
    row["editedAt"] = _now_iso()
    append_version(row, "restore", text, by=edited_by, note=f"回滚到 seq={target.get('seq')}")
    return public_view(upsert_narrative(row))


# --------------------------------------------------------------------------- whole-plan milestones

def _read_version_rows() -> list[dict[str, Any]]:
    return _dc()._read_contingency_runrecord(VERSION_OBJECT)


def _write_version_rows(rows: list[dict[str, Any]]) -> None:
    _dc()._write_contingency_runrecord(VERSION_OBJECT, rows)


def _text_at_label(row: dict[str, Any], label: str | None) -> str | None:
    if not label:
        return None
    matches = [v for v in (row.get("versions") or []) if v.get("versionLabel") == label]
    return str(matches[-1].get("text") or "") if matches else None


def list_contingency_plan_versions(project_key: str | None = None) -> dict[str, Any]:
    pk = resolve_project_key(project_key)
    overlay = [r for r in _read_version_rows() if str(r.get("projectKey") or "") == pk]
    seed: list[dict[str, Any]] = []
    try:  # best-effort Dolt seed merge; offline -> overlay only
        dc = _dc()
        seed = [
            r
            for r in dc.read_dolt_object_rows(VERSION_OBJECT)
            if str(r.get("projectKey") or "") == pk
        ]
    except Exception:
        seed = []
    merged = {str(r.get("planVersionLogId")): r for r in seed}
    for row in overlay:
        merged[str(row.get("planVersionLogId"))] = row
    versions = sorted(merged.values(), key=lambda r: str(r.get("createdAt") or ""), reverse=True)
    return {"versions": versions}


def _last_milestone_label(project_key: str) -> str | None:
    versions = list_contingency_plan_versions(project_key)["versions"]
    return str(versions[0].get("planVersion")) if versions else None


_NARRATIVE_SNAPSHOT_COLUMNS = [
    "chapterNarrativeId",
    "projectKey",
    "planId",
    "chapterId",
    "chapterNo",
    "chapterTitle",
    "text",
    "status",
    "versionLabel",
    "updatedBy",
    "updatedAt",
]


def _snapshot_narratives_to_dolt(
    project_key: str,
    version_label: str,
    narratives: list[dict[str, Any]],
    *,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Best-effort: freeze each chapter's displayText into the Dolt ChapterNarrative table at a milestone.

    One row per (projectKey, chapterId, versionLabel) — the published version history, directly
    queryable for cross-version comparison (diff_chapter_narrative_versions). Each milestone is also a
    dolt_commit, so Dolt-native dolt_diff across milestones works too. Live per-edit working state stays
    in the run-record overlay; only the milestone-frozen text lands in Dolt (writeback separation).
    Degrades silently when Dolt is offline (mirrors the Dolt-seed read in list_contingency_plan_versions)
    — the overlay milestone + PlanVersionLog have already persisted. Returns {written, ...}.
    """
    try:
        from dolt_schema_sync import (
            _fetch_column_names,
            _get_dolt_engine,
            _sql_text,
            build_add_column_statements,
            build_create_table_sql,
            object_type_table_name,
            quote_ident,
        )
        engine = _get_dolt_engine()
    except Exception:  # pragma: no cover - dolt offline / deps missing
        return {"written": 0, "skipped": "dolt-unavailable"}
    if engine is None:
        return {"written": 0, "skipped": "dolt-offline"}
    schema = _dc()._contingency_object_schema(NARRATIVE_OBJECT)
    if not schema:
        return {"written": 0, "skipped": "no-schema"}
    table = object_type_table_name(NARRATIVE_OBJECT, schema)
    cols = _NARRATIVE_SNAPSHOT_COLUMNS
    now = _now_iso()
    written = 0
    try:
        with engine.connect() as conn:
            conn.execute(_sql_text(build_create_table_sql(NARRATIVE_OBJECT, schema)))
            existing = _fetch_column_names(conn, table)
            add_stmts, _ = build_add_column_statements(table, schema, existing)
            for stmt in add_stmts:
                conn.execute(_sql_text(stmt))
            conn.commit()
            collist = ", ".join(quote_ident(c) for c in cols)
            vallist = ", ".join(f":{c}" for c in cols)
            for row in narratives:
                cid = str(row.get("chapterId") or "").strip()
                if not cid:
                    continue
                snapshot_pk = f"{project_key}__{cid}__{version_label}"
                values = {
                    "chapterNarrativeId": snapshot_pk,
                    "projectKey": project_key,
                    "planId": str(row.get("planId") or ""),
                    "chapterId": cid,
                    "chapterNo": str(row.get("chapterNo") or ""),
                    "chapterTitle": str(row.get("chapterTitle") or ""),
                    "text": display_text(row),
                    "status": str(row.get("status") or ""),
                    "versionLabel": version_label,
                    "updatedBy": created_by or "",
                    "updatedAt": now,
                }
                conn.execute(
                    _sql_text(f"DELETE FROM {quote_ident(table)} WHERE {quote_ident('chapterNarrativeId')} = :pk"),
                    {"pk": snapshot_pk},
                )
                conn.execute(
                    _sql_text(f"INSERT INTO {quote_ident(table)} ({collist}) VALUES ({vallist})"),
                    values,
                )
                written += 1
            if written:
                try:
                    conn.execute(
                        _sql_text("CALL dolt_commit('-A', '-m', :m)"),
                        {"m": f"预案章节正文里程碑 {version_label}（{written} 章 · {project_key}）"[:500]},
                    )
                except Exception as exc:  # nothing-to-commit is fine
                    if "nothing to commit" not in str(exc).lower():
                        raise
            conn.commit()
    except Exception:  # pragma: no cover - best-effort, overlay already persisted
        logger.exception("[narrative] milestone snapshot to Dolt failed (best-effort, skipped)")
        return {"written": 0, "skipped": "error"}
    return {"written": written, "committed": bool(written), "table": table}


def diff_chapter_narrative_versions(
    project_key: str | None,
    from_version: str,
    to_version: str,
) -> dict[str, Any]:
    """Compare two published milestone versions of the chapter narratives (cross-version 比对).

    Reads the Dolt ChapterNarrative published snapshots (reader: dolt_rows) and pairs rows by chapterId
    across the two versionLabels — per chapter: added / removed / modified / unchanged + from/to text.
    Dolt offline -> empty diff. (The same milestones are dolt_commits, so a field-level dolt_diff via
    scenario_lifecycle_manager is also available when commit refs are known.)
    """
    pk = resolve_project_key(project_key)
    try:
        rows = [r for r in _dc().get_object_data(NARRATIVE_OBJECT) if str(r.get("projectKey") or "") == pk]
    except Exception:  # pragma: no cover - dolt offline
        rows = []
    a = {str(r.get("chapterId")): r for r in rows if str(r.get("versionLabel") or "") == str(from_version)}
    b = {str(r.get("chapterId")): r for r in rows if str(r.get("versionLabel") or "") == str(to_version)}
    diffs: list[dict[str, Any]] = []
    for cid in sorted(set(a) | set(b)):
        ra, rb = a.get(cid), b.get(cid)
        ta = str((ra or {}).get("text") or "")
        tb = str((rb or {}).get("text") or "")
        if ra and rb:
            change = "modified" if ta != tb else "unchanged"
        elif rb:
            change = "added"
        else:
            change = "removed"
        diffs.append(
            {
                "chapterId": cid,
                "chapterTitle": str((rb or ra or {}).get("chapterTitle") or ""),
                "change": change,
                "fromText": ta,
                "toText": tb,
            }
        )
    return {
        "projectKey": pk,
        "fromVersion": from_version,
        "toVersion": to_version,
        "diffs": diffs,
        "changedCount": sum(1 for d in diffs if d["change"] != "unchanged"),
    }


def save_contingency_plan_version(
    project_key: str | None,
    version_label: str,
    *,
    plan_id: str | None = None,
    created_by: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    pk = resolve_project_key(project_key)
    label = (version_label or "").strip()
    if not label:
        raise ValueError("version_label 必填")
    prev_label = _last_milestone_label(pk)
    changed: list[str] = []
    for row in read_all_narratives(pk):
        text = display_text(row)
        prev_text = _text_at_label(row, prev_label)
        if prev_text is None or prev_text != text:
            changed.append(str(row.get("chapterTitle") or row.get("chapterId")))
        append_version(row, "milestone", text, by=created_by, note=note, version_label=label)
        upsert_narrative(row)
    # Freeze this milestone's chapter text into the Dolt published version layer (best-effort; the
    # overlay above is the live edit layer, Dolt is the versioned/diff-able published layer).
    dolt_snapshot = _snapshot_narratives_to_dolt(pk, label, read_all_narratives(pk), created_by=created_by)
    if changed:
        change_summary = f"{label}：更新 {len(changed)} 章（{('、'.join(changed))[:200]}）"
    else:
        change_summary = f"{label}：本次无章节正文变更"
    if note:
        change_summary = f"{change_summary}；备注：{note}"
    now = _now_iso()
    pvl_id = f"PVL-{pk}-{label}"
    pvl_row = {
        "planVersionLogId": pvl_id,
        "projectKey": pk,
        "planId": plan_id or "",
        "planVersion": label,
        "status": "ACTIVE",
        "createdBy": created_by or "",
        "createdAt": now,
        "lastModifiedBy": created_by or "",
        "modifiedAt": now,
        "changeDescription": change_summary,
        "cumulativeChangeLog": _build_cumulative_log(pk, label, change_summary, now),
    }
    rows = [r for r in _read_version_rows() if str(r.get("planVersionLogId") or "") != pvl_id]
    rows.append(pvl_row)
    _write_version_rows(rows)
    return {
        "version": pvl_row,
        "changeSummary": change_summary,
        "versions": list_contingency_plan_versions(pk)["versions"],
        "doltSnapshot": dolt_snapshot,
    }


def _build_cumulative_log(project_key: str, label: str, summary: str, now: str) -> str:
    prior = [r for r in _read_version_rows() if str(r.get("projectKey") or "") == project_key]
    lines = [
        f"{r.get('createdAt')} {r.get('planVersion')} {r.get('changeDescription')}" for r in prior
    ]
    lines.append(f"{now} {label} {summary}")
    return "\n".join(lines[-50:])
