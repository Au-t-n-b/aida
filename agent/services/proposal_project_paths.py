"""Unified delivery预案 filesystem paths under BUSINESS_ROOT/projects/{project_id}."""
from __future__ import annotations

from pathlib import Path

from agent.config import BUSINESS_ROOT
from agent.constants.org_assets_paths import (
    is_org_asset_logical,
    org_assets_path,
)
from agent.constants.project_paths import contract_paths, proposal_paths

CHAPTER57_STORE_FILE = "chapter57_store.json"
LEGACY_GLOBAL_STORE = "proposal_store.json"

# Flat output xlsx paths (aligned with shared/datacenter/ipo_paths + chapter_files sync)
CHAPTER_ARTIFACT_RELATIVE: dict[str, str] = {
    "5.1_net_plane": "早期介入/交付预案/输出结果/网络平面配置信息表.xlsx",
    "5.1_common_plane": "早期介入/交付预案/输出结果/共平面类型表.xlsx",
    "5.2_net_mgmt": "早期介入/交付预案/输出结果/网管服务器配置表.xlsx",
    "5.3_cluster_device": "早期介入/交付预案/输出结果/集群设备清单表.xlsx",
    "7.1_room_rack": "孪生世界/算力底座孪生/输出结果/机房机柜信息表.xlsx",
}


def physical_project_root(project_id: str) -> Path:
    return BUSINESS_ROOT / "projects" / project_id


def org_asset_path(relative: str) -> Path:
    """Resolve org-assets logical path → {BUSINESS_ROOT}/org-assets/…"""
    return org_assets_path(relative)


def project_relative(project_id: str, relative: str) -> Path:
    normalized = relative.replace("\\", "/").strip("/")
    return physical_project_root(project_id) / Path(normalized)


def dc_logical_to_project_path(project_id: str, dc_logical: str) -> Path:
    normalized = dc_logical.replace("\\", "/").strip("/")
    if is_org_asset_logical(normalized):
        return org_asset_path(normalized)
    return project_relative(project_id, normalized)


def proposal_draft_dir(project_id: str) -> Path:
    rel = proposal_paths("")["proposal_draft_dir"]
    return physical_project_root(project_id) / Path(rel)


def proposal_output_dir(project_id: str) -> Path:
    rel = proposal_paths("")["out"]
    return physical_project_root(project_id) / Path(rel)


def service_boq_parse_dir(project_id: str) -> Path:
    rel = contract_paths("")["service_boq_parse"]
    return physical_project_root(project_id) / Path(rel)


def boq_device_parse_dir(project_id: str) -> Path:
    rel = contract_paths("")["boq_device_parse"]
    return physical_project_root(project_id) / Path(rel)


def device_table_output_path(project_id: str) -> Path:
    from shared.datacenter import ipo_paths

    return project_relative(project_id, ipo_paths.SUFFIX_PROPOSAL_DEVICE_TABLE_OUT)


def chapter_artifact_path(project_id: str, artifact_key: str) -> Path:
    rel = CHAPTER_ARTIFACT_RELATIVE[artifact_key]
    return project_relative(project_id, rel)


def chapter57_store_path(project_id: str) -> Path:
    return proposal_draft_dir(project_id) / CHAPTER57_STORE_FILE


def legacy_global_store_path() -> Path:
    """Deprecated global store at BUSINESS_ROOT (migrated on load)."""
    return BUSINESS_ROOT / LEGACY_GLOBAL_STORE


def legacy_repo_data_store_path() -> Path:
    """Pre-unification store under repo data/."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / LEGACY_GLOBAL_STORE
