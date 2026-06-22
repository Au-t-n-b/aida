"""Organization assets (org-assets) path SSOT — physical root under BUSINESS_ROOT."""
from __future__ import annotations

from pathlib import Path

from agent.config import BUSINESS_ROOT

ORG_ASSETS_DIR = "org-assets"
LEGACY_ORG_ASSETS_DIR = "组织资产"
ORG_ASSETS_PREFIXES = (f"{ORG_ASSETS_DIR}/", f"{LEGACY_ORG_ASSETS_DIR}/")


def normalize_org_asset_relative(relative: str) -> str:
    """Strip org-assets/ or legacy 组织资产/ prefix; return path under org-assets root."""
    normalized = relative.replace("\\", "/").strip("/")
    for prefix in ORG_ASSETS_PREFIXES:
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    return normalized


def is_org_asset_logical(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in ORG_ASSETS_PREFIXES)


def org_assets_root() -> Path:
    return BUSINESS_ROOT / ORG_ASSETS_DIR


def org_assets_path(*relative_parts: str) -> Path:
    """Physical path under {BUSINESS_ROOT}/org-assets/."""
    if not relative_parts:
        return org_assets_root()
    joined = "/".join(str(p).replace("\\", "/").strip("/") for p in relative_parts if p)
    rel = normalize_org_asset_relative(joined)
    return org_assets_root() / Path(rel)
