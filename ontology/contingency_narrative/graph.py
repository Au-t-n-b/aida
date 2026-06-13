"""Small LangGraph for predefined-plan chapter narrative generation.

Pipeline: gather -> generate -> merge -> persist.

  gather    Read the chapter facts (via deriveContingencyRisks) + each chapter's current narrative
            overlay row, and select the target chapters per scope.
  generate  For chapters that need a draft (mode-dependent), call the LLM to write prose. A
            human-edited chapter is NEVER overwritten: under `regenerate` its new draft is parked in
            pendingGenerated (status -> regen_pending).
  merge     `smart_merge` only: for human-edited chapters, 3-way fuse (priorAI + humanEdit + facts)
            into mergeCandidate (or editedText when apply=true).
  persist   Read back the targets' narrative rows and return their public views.

Nodes write to the run-record overlay directly (store.upsert_narrative); the graph state carries
only JSON-serializable working data, so an optional checkpointer can be plugged in without holding a
ChatOpenAI in state. If langgraph is ever unavailable the same nodes run sequentially.
"""
from __future__ import annotations

import logging
from typing import Any

from . import llm, store
from .state import NarrativeState

logger = logging.getLogger(__name__)

# 真实生成中只有 项目背景 一章保留 AI 文字总结；其余普通章不生成正文（风险&假设章已从目录删除）。
# 例外：融合组章（isGroup，doc-grp-*）必生成——把多个成员要素融合成单段正文，是「融合成单段描述」的载体。
# 与前端 ontology-report.tsx 的 NARRATIVE_CHAPTER_IDS / c.isGroup 门控保持一致。
NARRATIVE_CHAPTERS = {"doc-ch-1"}

try:
    from langgraph.graph import START, END, StateGraph

    _HAS_LANGGRAPH = True
except Exception:  # pragma: no cover - langgraph is a declared dependency, this is belt-and-suspenders
    _HAS_LANGGRAPH = False


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _risk_brief(risk: dict[str, Any]) -> dict[str, Any]:
    return {
        "riskName": risk.get("riskName"),
        "riskPoint": risk.get("riskPoint"),
        "severity": risk.get("severity"),
        "owner": risk.get("owner"),
        "mitigationPlan": risk.get("mitigationPlan"),
        "impact": risk.get("impact"),
    }


def _project_rows(chapter: dict[str, Any], *, limit: int = 5, maxlen: int = 60) -> list[dict[str, Any]]:
    """Project a chapter's fact rows to their curated Chinese-labeled columns, truncated + capped.

    Keeps the LLM payload lean and readable (label→value, not raw apiName rows): big fact substrates
    like EquipmentConfig (many devices × many columns) otherwise bloat the prompt to thousands of
    chars and push generation past the LLM timeout. Falls back to the row's own keys when a chapter
    declares no columns.
    """
    cols = [c for c in (chapter.get("columns") or []) if isinstance(c, dict)]
    out: list[dict[str, Any]] = []
    for row in (chapter.get("rows") or [])[:limit]:
        if not isinstance(row, dict):
            continue
        rec: dict[str, Any] = {}
        pairs = (
            [(c.get("label") or c.get("key"), row.get(c.get("key"))) for c in cols if c.get("key")]
            if cols
            else list(row.items())[:10]
        )
        for label, val in pairs:
            if label is None or val in (None, ""):
                continue
            rec[str(label)] = str(val)[:maxlen]
        if rec:
            out.append(rec)
    return out


def _project_detail(chapter: dict[str, Any], *, maxlen: int = 240) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for detail in chapter.get("detailRows") or []:
        if isinstance(detail, dict) and detail.get("value") not in (None, ""):
            out.append({"label": detail.get("label"), "value": str(detail.get("value"))[:maxlen]})
    return out


def _chapter_fact(chapter: dict[str, Any], risks_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    bound = [
        _risk_brief(risks_by_id[rid])
        for rid in (chapter.get("riskIds") or [])
        if rid in risks_by_id
    ]
    return {
        "chapterId": str(chapter.get("id") or ""),
        "chapterNo": str(chapter.get("no") or ""),
        "title": str(chapter.get("title") or ""),
        "skeleton": str(chapter.get("desc") or ""),
        "decisionLabel": str(chapter.get("decisionLabel") or ""),
        "fields": [
            f.get("name") for f in (chapter.get("fields") or []) if isinstance(f, dict) and f.get("name")
        ],
        "factRows": _project_rows(chapter),
        "detailRows": _project_detail(chapter),
        "boundRisks": bound,
        "state": str(chapter.get("state") or ""),
        "source": str(chapter.get("source") or ""),
    }


def _member_fact(chapter: dict[str, Any], risks_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """A fusion-group member's projected facts (one entry in the group fact's `members` list)."""
    return {
        "title": str(chapter.get("title") or ""),
        "skeleton": str(chapter.get("desc") or ""),
        "fields": [
            f.get("name") for f in (chapter.get("fields") or []) if isinstance(f, dict) and f.get("name")
        ],
        "factRows": _project_rows(chapter),
        "detailRows": _project_detail(chapter),
        "boundRisks": [
            _risk_brief(risks_by_id[rid])
            for rid in (chapter.get("riskIds") or [])
            if rid in risks_by_id
        ],
    }


def _group_fact(
    group_chapter: dict[str, Any],
    full_by_id: dict[str, dict[str, Any]],
    risks_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a fusion-group fact bundle: each member's facts projected from the FULL directory.

    The tailored derive folds members into the composite (no member rows), so members are resolved
    from `full_by_id` (the apply_outline=False directory). Drives GROUP_FUSION_SYSTEM to fuse the
    members into one coherent section.
    """
    members: list[dict[str, Any]] = []
    for mid in group_chapter.get("memberIds") or []:
        member = full_by_id.get(str(mid))
        if isinstance(member, dict):
            members.append(_member_fact(member, risks_by_id))
    bound = [
        _risk_brief(risks_by_id[rid])
        for rid in (group_chapter.get("riskIds") or [])
        if rid in risks_by_id
    ]
    return {
        "chapterId": str(group_chapter.get("id") or ""),
        "chapterNo": str(group_chapter.get("no") or ""),
        "title": str(group_chapter.get("title") or ""),
        "isGroup": True,
        "decisionLabel": str(group_chapter.get("decisionLabel") or ""),
        "members": members,
        "boundRisks": bound,
        "state": str(group_chapter.get("state") or ""),
    }


# --------------------------------------------------------------------------- nodes


def gather(state: NarrativeState) -> dict[str, Any]:
    pk = store.resolve_project_key(state.get("project_key"))
    plan_id = (state.get("plan_id") or "").strip()
    ref = (state.get("reference_date") or "").strip()
    import data_connector as dc  # lazy

    derived = dc.derive_contingency_risks_for_plan(
        plan_id=plan_id or None,
        project_key=pk,
        reference_date=ref or None,
    )
    chapters = derived.get("chapters") or []
    risks_by_id = {
        str(r.get("riskId")): r for r in (derived.get("risks") or []) if isinstance(r, dict)
    }
    # Fusion-group members are folded out of the tailored chapters; resolve their facts from the FULL
    # (un-tailored) directory. Only derived when the report actually contains a group (saves a derive).
    full_by_id: dict[str, dict[str, Any]] = {}
    if any(c.get("isGroup") for c in chapters if isinstance(c, dict)):
        full = dc.derive_contingency_risks_for_plan(
            plan_id=plan_id or None,
            project_key=pk,
            reference_date=ref or None,
            apply_outline=False,
        )
        full_by_id = {
            str(c.get("id") or ""): c for c in (full.get("chapters") or []) if isinstance(c, dict)
        }
    scope = (state.get("scope") or "all").strip()
    target_cid = (state.get("chapter_id") or "").strip()
    facts: list[dict[str, Any]] = []
    for chapter in chapters:
        cid = str(chapter.get("id") or "")
        if not cid:
            continue
        # Narrative targets: 项目背景 (NARRATIVE_CHAPTERS) + every fusion group (single fused prose).
        if not (chapter.get("isGroup") or cid in NARRATIVE_CHAPTERS):
            continue
        if scope == "chapter" and cid != target_cid:
            continue
        facts.append(
            _group_fact(chapter, full_by_id, risks_by_id)
            if chapter.get("isGroup")
            else _chapter_fact(chapter, risks_by_id)
        )
    existing = {fact["chapterId"]: store.read_narrative(pk, fact["chapterId"]) for fact in facts}
    return {"project_key": pk, "targets": facts, "existing": existing, "degraded": False}


def generate(state: NarrativeState) -> dict[str, Any]:
    mode = (state.get("mode") or "only_empty").strip()
    if mode == "smart_merge":
        return {}  # handled by the merge node
    model = llm.get_model()
    if model is None:
        return {"degraded": True}
    pk = state["project_key"]
    plan_id = (state.get("plan_id") or "").strip()
    existing = state.get("existing") or {}
    for fact in state.get("targets") or []:
        cid = fact["chapterId"]
        row = existing.get(cid)
        has_edit = bool(row and str(row.get("editedText") or "").strip())
        has_any = bool(
            row
            and (str(row.get("editedText") or "").strip() or str(row.get("generatedText") or "").strip())
        )
        if mode == "only_empty" and has_any:
            continue
        group_title = ""
        try:
            if fact.get("isGroup"):
                # 融合组：一次产出融合标题 + 概述导语（成员表另行展示，不在 intro 复述）。
                group_title, text = llm.generate_group_title_and_intro(model, fact)
            else:
                text = llm.generate_chapter_text(model, fact)
        except Exception as exc:
            logger.exception("[narrative] generate chapter %s failed: %s", cid, exc)
            continue
        if not text.strip():
            continue
        row = row or store.new_narrative_row(
            pk, cid, plan_id=plan_id, chapter_no=fact["chapterNo"], chapter_title=fact["title"]
        )
        row["chapterNo"] = fact["chapterNo"] or row.get("chapterNo")
        row["chapterTitle"] = fact["title"] or row.get("chapterTitle")
        if plan_id:
            row["planId"] = plan_id
        row["generatedModel"] = llm.model_name(model)
        row["generatedAt"] = store._now_iso()
        if has_edit and mode == "regenerate":
            # Human-edited chapter: park the new draft, never clobber editedText.
            row["pendingGenerated"] = text
            row["status"] = "regen_pending"
            store.append_version(row, "ai", text, note="重生成（待合并）")
        else:
            row["generatedText"] = text
            if not has_edit:
                row["status"] = "ai_draft"
            store.append_version(row, "ai", text)
        if fact.get("isGroup"):
            # 融合标题写回 outline 组（set_group_title 内部守卫：人工改名 titleBy='human' 永不被覆盖），
            # 并把有效标题（人工 else AI）反映进 narrative 行，让响应/前端即时拿到正确章名。
            from contingency_assembly import store as _outline_store

            if group_title:
                _outline_store.set_group_title(pk, cid, group_title, source="ai")
            eff_title, _by = _outline_store.group_title(pk, cid)
            if eff_title:
                row["chapterTitle"] = eff_title
        store.upsert_narrative(row)
    return {}


def merge(state: NarrativeState) -> dict[str, Any]:
    if (state.get("mode") or "").strip() != "smart_merge":
        return {}
    model = llm.get_model()
    if model is None:
        return {"degraded": True}
    apply_now = _as_bool(state.get("apply"))
    pk = state["project_key"]
    for fact in state.get("targets") or []:
        cid = fact["chapterId"]
        row = store.read_narrative(pk, cid)
        if not row:
            continue
        human = str(row.get("editedText") or "").strip()
        if not human:
            continue  # smart-merge only applies where there is a human edit to preserve
        prior_ai = str(row.get("generatedText") or "")
        try:
            merged = llm.merge_chapter_text(model, prior_ai, human, fact)
        except Exception as exc:
            logger.exception("[narrative] merge chapter %s failed: %s", cid, exc)
            continue
        if not merged.strip():
            continue
        if apply_now:
            row["editedText"] = merged
            row["status"] = "merged"
            row["mergeCandidate"] = ""
            store.append_version(row, "merge", merged, note="智能融合（直接采纳）")
        else:
            row["mergeCandidate"] = merged
            # status stays human_edited; the UI surfaces the candidate for review.
            store.append_version(row, "merge", merged, note="智能融合候选")
        row["generatedModel"] = llm.model_name(model)
        store.upsert_narrative(row)
    return {}


def persist(state: NarrativeState) -> dict[str, Any]:
    pk = state["project_key"]
    out: list[dict[str, Any]] = []
    for fact in state.get("targets") or []:
        row = store.read_narrative(pk, fact["chapterId"])
        if row:
            out.append(store.public_view(row))
    return {"narratives": out}


# --------------------------------------------------------------------------- assembly + entry


def build_narrative_graph(checkpointer: Any | None = None):
    """Compile the gather->generate->merge->persist StateGraph (requires langgraph)."""
    graph = StateGraph(NarrativeState)
    graph.add_node("gather", gather)
    graph.add_node("generate", generate)
    graph.add_node("merge", merge)
    graph.add_node("persist", persist)
    graph.add_edge(START, "gather")
    graph.add_edge("gather", "generate")
    graph.add_edge("generate", "merge")
    graph.add_edge("merge", "persist")
    graph.add_edge("persist", END)
    return graph.compile(checkpointer=checkpointer)


def _run_sequential(state: dict[str, Any]) -> dict[str, Any]:
    """Fallback runner if langgraph is unavailable — same nodes, plain sequence."""
    for node in (gather, generate, merge, persist):
        state = {**state, **(node(state) or {})}  # type: ignore[arg-type]
    return state


def run_generation(
    *,
    plan_id: str | None = None,
    project_key: str | None = None,
    scope: str = "all",
    chapter_id: str | None = None,
    mode: str = "only_empty",
    apply: Any = False,
    reference_date: str | None = None,
) -> dict[str, Any]:
    """Public entry for the generateContingencyNarratives Function."""
    init: dict[str, Any] = {
        "plan_id": (plan_id or "").strip(),
        "project_key": store.resolve_project_key(project_key),
        "scope": (scope or "all").strip(),
        "chapter_id": (chapter_id or "").strip(),
        "mode": (mode or "only_empty").strip(),
        "apply": _as_bool(apply),
        "reference_date": (reference_date or "").strip(),
        "degraded": False,
    }
    if _HAS_LANGGRAPH:
        final = build_narrative_graph().invoke(init)
    else:  # pragma: no cover - langgraph is installed in this environment
        final = _run_sequential(init)
    return {
        "projectKey": init["project_key"],
        "planId": init["plan_id"],
        "degraded": bool(final.get("degraded")),
        "narratives": final.get("narratives") or [],
    }
