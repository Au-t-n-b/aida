"""Small LangGraph for per-project chapter tailoring (assembly).

Pipeline: gather -> select -> persist.

  gather   Read the *un-tailored* ontology-derived chapter directory for this project (full set, via
           deriveContingencyRisks with apply_outline=False) + each chapter's fact-row / bound-risk
           counts, and load the current ContingencyOutline overlay.
  select   Ask the LLM which chapters apply to this project, their order, and a one-line note each.
           The LLM output is schema-validated (ids must exist in the directory — hallucinations
           dropped), mandatory chapters are force-kept (global/structural, or any with facts/risks),
           and human pins win (pinnedInclude forced in, pinnedExclude forced out). Result parked in
           the overlay (never regenerated under mode=only_empty once present).
  persist  Read back the overlay row and return its public view.

Nodes write to the run-record overlay directly (store.upsert_outline); graph state stays
JSON-serializable. If langgraph is unavailable the same nodes run sequentially.
"""
from __future__ import annotations

import logging
from typing import Any

from . import llm, store
from .state import AssemblyState

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import START, END, StateGraph

    _HAS_LANGGRAPH = True
except Exception:  # pragma: no cover - langgraph is a declared dependency, belt-and-suspenders
    _HAS_LANGGRAPH = False


def _row_count(chapter: dict[str, Any]) -> int:
    rows = chapter.get("rows")
    if isinstance(rows, list) and rows:
        return len(rows)
    detail = chapter.get("detailRows")
    if isinstance(detail, list) and detail:
        return len(detail)
    return 0


def _chapter_summary(chapter: dict[str, Any]) -> dict[str, Any]:
    object_type = str(chapter.get("objectType") or "").strip()
    row_count = _row_count(chapter)
    risk_count = len(chapter.get("riskIds") or [])
    consolidates = bool(chapter.get("consolidatesRisks"))
    # mandatory = always keep: structural/global chapters (no fact table) or anything with facts/risks.
    # Only a fact-backed chapter that is empty for THIS project (no rows, no risks) is droppable.
    mandatory = consolidates or risk_count > 0 or row_count > 0 or not object_type
    return {
        "id": str(chapter.get("id") or ""),
        "no": str(chapter.get("no") or ""),
        "title": str(chapter.get("title") or ""),
        "objectType": object_type,
        "decisionLabel": str(chapter.get("decisionLabel") or ""),
        "rowCount": row_count,
        "riskCount": risk_count,
        "consolidatesRisks": consolidates,
        "mandatory": mandatory,
    }


# --------------------------------------------------------------------------- nodes


def gather(state: AssemblyState) -> dict[str, Any]:
    pk = store.resolve_project_key(state.get("project_key"))
    plan_id = (state.get("plan_id") or "").strip()
    ref = (state.get("reference_date") or "").strip()
    import data_connector as dc  # lazy

    # apply_outline=False -> the FULL directory, so a regenerate can re-expand previously dropped chapters.
    derived = dc.derive_contingency_risks_for_plan(
        plan_id=plan_id or None,
        project_key=pk,
        reference_date=ref or None,
        apply_outline=False,
    )
    available = [
        _chapter_summary(c)
        for c in (derived.get("chapters") or [])
        if isinstance(c, dict) and c.get("id")
    ]
    return {"project_key": pk, "available": available, "existing": store.read_outline(pk)}


def select(state: AssemblyState) -> dict[str, Any]:
    available = state.get("available") or []
    existing = state.get("existing")
    mode = (state.get("mode") or "only_empty").strip()
    if mode == "only_empty" and existing and (existing.get("include") or []):
        return {}  # already tailored; only_empty does not regenerate
    available_ids = {s["id"] for s in available}
    mandatory_ids = [s["id"] for s in available if s.get("mandatory")]

    model = llm.get_model()
    llm_include: list[str] = []
    llm_order: list[str] = []
    llm_notes: dict[str, str] = {}
    rationale = ""
    degraded = False
    if model is None:
        degraded = True
    else:
        try:
            out = llm.select_chapters(model, {"projectKey": state.get("project_key"), "availableChapters": available})
        except Exception as exc:
            logger.exception("[assembly] select failed: %s", exc)
            out = {}
            degraded = True
        # schema-validate: keep only ids that really exist (drop any hallucinated id)
        llm_include = [i for i in (out.get("include") or []) if str(i) in available_ids]
        llm_order = [i for i in (out.get("order") or []) if str(i) in available_ids]
        llm_notes = {
            str(k): str(v)
            for k, v in (out.get("notes") or {}).items()
            if str(k) in available_ids and isinstance(v, str) and v.strip()
        }
        rationale = str(out.get("rationale") or "")

    pk = state["project_key"]
    row = existing or store.new_outline_row(pk, plan_id=(state.get("plan_id") or "").strip() or None)
    pin_inc = [str(x) for x in (row.get("pinnedInclude") or [])]
    pin_exc = {str(x) for x in (row.get("pinnedExclude") or [])}
    # 手动拖入的临时章（doc-ot-*，见 data_connector._ADHOC_CHAPTER_PREFIX）与人工 pin 同档强保：
    # AI 重排不得静默丢弃；available_ids 校验保证只保留仍可 materialize 的 id。人工 exclude 仍然最大。
    manual_adhoc = [
        str(cid)
        for cid in ((existing or {}).get("include") or [])
        if str(cid).startswith("doc-ot-") and str(cid) in available_ids
    ]

    # include = mandatory ∪ LLM-picked ∪ human-pinned-in ∪ manual-adhoc, minus human-pinned-out (human wins).
    include = store._ordered_unique(mandatory_ids + llm_include + pin_inc + manual_adhoc)
    include = [c for c in include if c not in pin_exc]
    include_set = set(include)
    # order = LLM order first (validated to include), then any remaining included chapter by directory order.
    order = store._ordered_unique([c for c in llm_order if c in include_set] + include)

    if degraded and not (existing and existing.get("include")):
        # No model and no prior outline -> leave include empty so derive falls back to the full
        # directory (graceful), but still persist any pins for next time.
        include, order = [], []

    row["include"] = include
    row["order"] = order
    row["notes"] = {k: v for k, v in llm_notes.items() if k in include_set}
    row["rationale"] = rationale
    row["generatedModel"] = llm.model_name(model) if model is not None else ""
    row["generatedAt"] = store._now_iso()
    row["status"] = "human_pinned" if (pin_inc or pin_exc) else "ai_draft"
    store.append_version(row, "ai", note=("degraded" if degraded else None))
    view = store.public_view(row)
    # persist=False (AI 建议布局): compute the suggested outline but do NOT write the overlay — the
    # user reviews it (pre-loaded into the drag composer) and only a manual setContingencyChapters commits.
    if state.get("persist", True):
        store.upsert_outline(row)
    return {"degraded": degraded, "outline": view}


def persist(state: AssemblyState) -> dict[str, Any]:
    # select stashes its computed view in state, so a suggest-only run (which skipped the overlay write)
    # still returns its proposal; fall back to the stored row otherwise (e.g. only_empty short-circuit).
    if state.get("outline") is not None:
        return {"outline": state["outline"]}
    row = store.read_outline(state["project_key"])
    return {"outline": store.public_view(row)}


# --------------------------------------------------------------------------- assembly + entry


def build_assembly_graph(checkpointer: Any | None = None):
    graph = StateGraph(AssemblyState)
    graph.add_node("gather", gather)
    graph.add_node("select", select)
    graph.add_node("persist", persist)
    graph.add_edge(START, "gather")
    graph.add_edge("gather", "select")
    graph.add_edge("select", "persist")
    graph.add_edge("persist", END)
    return graph.compile(checkpointer=checkpointer)


def _run_sequential(state: dict[str, Any]) -> dict[str, Any]:
    for node in (gather, select, persist):
        state = {**state, **(node(state) or {})}  # type: ignore[arg-type]
    return state


def run_assembly(
    *,
    plan_id: str | None = None,
    project_key: str | None = None,
    mode: str = "only_empty",
    reference_date: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Public entry for the assembleContingencyChapters Function.

    persist=False → suggest-only (AI 建议布局): return the proposed outline without writing the overlay.
    """
    init: dict[str, Any] = {
        "plan_id": (plan_id or "").strip(),
        "project_key": store.resolve_project_key(project_key),
        "mode": (mode or "only_empty").strip(),
        "reference_date": (reference_date or "").strip(),
        "persist": bool(persist),
        "degraded": False,
    }
    if _HAS_LANGGRAPH:
        final = build_assembly_graph().invoke(init)
    else:  # pragma: no cover - langgraph is installed in this environment
        final = _run_sequential(init)
    return {
        "projectKey": init["project_key"],
        "planId": init["plan_id"],
        "degraded": bool(final.get("degraded")),
        "outline": final.get("outline") or {},
    }
