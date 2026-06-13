"""Contingency chapter narrative — LangGraph + LLM generation, human-edit-first merge, versioning.

Public surface (called by data_connector thin wrappers, which bind the ontology Functions):
  graph.run_generation(...)                    -> generateContingencyNarratives
  store.edit_chapter_narrative(...)            -> editChapterNarrative
  store.accept_chapter_merge(...)              -> acceptChapterMerge
  store.save_contingency_plan_version(...)     -> saveContingencyPlanVersion
  store.list_contingency_plan_versions(...)    -> listContingencyPlanVersions
  store.restore_chapter_narrative_version(...) -> restoreChapterNarrativeVersion
  store.read_all_narratives(...)               -> consumed by data_connector chapter injection

Kept import-light (no data_connector at import time) so importing the package does not pull the
heavy ontology backend; data_connector is imported lazily inside store/graph functions.
"""
from . import graph, llm, prompts, state, store  # noqa: F401
