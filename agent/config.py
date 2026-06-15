"""Runtime configuration for proposal APIs in the agent backend."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_AIDA_ROOT = Path(__file__).resolve().parents[1]
if str(_AIDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AIDA_ROOT))


def _load_env_files() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    agent_root = Path(__file__).resolve().parent
    for path in (agent_root / ".env", agent_root.parent / ".env"):
        if path.exists():
            load_dotenv(path, override=False)


_load_env_files()

# Default: feature_new/.data (local dev). Production: set AIDA_BUSINESS_ROOT.
_DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data"
BUSINESS_ROOT = Path(os.environ.get("AIDA_BUSINESS_ROOT", str(_DEFAULT_ROOT))).resolve()

# Allowed proposal roles (TD/PD per 00-第8章 §6).
PROPOSAL_READ_ROLES = frozenset({"td", "pd", "admin"})
PROPOSAL_WRITE_ROLES = frozenset({"td", "pd", "admin"})
