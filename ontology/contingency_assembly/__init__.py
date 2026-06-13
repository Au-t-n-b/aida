"""Contingency chapter assembly — per-project, LangGraph + LLM tailoring of the chapter set.

Where contingency_narrative writes prose *into* each chapter, this package decides *which* of the
ontology-derived chapters apply to a project, in what order, plus a one-line note each — and parks
that decision in the ContingencyOutline overlay. deriveContingencyRisks reads the overlay (never the
LLM), so the report stays deterministic + cached; the LLM runs only on an explicit assemble.

Public surface (called by data_connector thin wrappers, which bind the ontology Functions):
  graph.run_assembly(...)      -> assembleContingencyChapters
  store.pin_chapter(...)       -> pinContingencyChapter
  store.apply_outline(...)     -> consumed by data_connector chapter tailoring (pure, no LLM)
  store.read_outline(...)      -> consumed by data_connector chapter tailoring

Kept import-light (no data_connector at import time); data_connector is imported lazily inside
store/graph functions.
"""
from . import graph, llm, prompts, state, store  # noqa: F401
