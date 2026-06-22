"""Deprecated: proposal runtime no longer uses local mock / project mirror.

Kept as empty compatibility shim; do not import in new code.
"""
from __future__ import annotations

import warnings

warnings.warn(
    "agent.services.local_mock_fallback is deprecated; use DataCenterClient via proposal dc_store",
    DeprecationWarning,
    stacklevel=2,
)

OPTIONAL_OUTPUT_SLOTS = frozenset({"raci_out", "acceptance_out", "testcases_out"})


def mock_fallback_enabled() -> bool:
    return False
