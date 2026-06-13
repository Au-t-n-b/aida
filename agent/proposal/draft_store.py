"""File-based draft and versioned output storage for proposal chapters."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DISPLAY_TZ = ZoneInfo("Asia/Shanghai")
from pathlib import Path
from typing import Any

from agent.config import BUSINESS_ROOT
from agent.constants.project_paths import proposal_paths


CHAPTER_02_FILE = "ch-02-device-info.json"
CHAPTER_81_FILE = "ch-08-1-service-delivery-ui.json"
CHAPTER_82_FILE = "ch-08-2-service-content.json"
CHAPTER_83_FILE = "ch-08-3-maintenance-strategy.json"
CHAPTER_84_FILE = "ch-08-4-maintenance-sla.json"
VERSION_MANIFEST_FILE = "version-info.json"


def physical_project_root(project_id: str) -> Path:
    return BUSINESS_ROOT / "projects" / project_id


def logical_project_root(project_id: str) -> str:
    # Proposal payload now lives directly under projects/<project_id>/...
    return ""


def _paths(project_id: str) -> dict[str, str]:
    return proposal_paths(logical_project_root(project_id))


def draft_dir(project_id: str) -> Path:
    return physical_project_root(project_id) / Path(_paths(project_id)["proposal_draft_dir"])


def output_versions_dir(project_id: str) -> Path:
    return physical_project_root(project_id) / Path(_paths(project_id)["proposal_versions_out"])


def output_version_dir(project_id: str, version: str) -> Path:
    safe = version.replace("/", "_")
    return output_versions_dir(project_id) / safe


def chapter_02_draft_path(project_id: str) -> Path:
    return draft_dir(project_id) / CHAPTER_02_FILE


def chapter_02_output_path(project_id: str, version: str) -> Path:
    return output_version_dir(project_id, version) / CHAPTER_02_FILE


def chapter_81_draft_path(project_id: str) -> Path:
    return draft_dir(project_id) / CHAPTER_81_FILE


def chapter_81_output_path(project_id: str, version: str) -> Path:
    return output_version_dir(project_id, version) / CHAPTER_81_FILE


def chapter_82_draft_path(project_id: str) -> Path:
    return draft_dir(project_id) / CHAPTER_82_FILE


def chapter_82_output_path(project_id: str, version: str) -> Path:
    return output_version_dir(project_id, version) / CHAPTER_82_FILE


def chapter_83_draft_path(project_id: str) -> Path:
    return draft_dir(project_id) / CHAPTER_83_FILE


def chapter_83_output_path(project_id: str, version: str) -> Path:
    return output_version_dir(project_id, version) / CHAPTER_83_FILE


def chapter_84_draft_path(project_id: str) -> Path:
    return draft_dir(project_id) / CHAPTER_84_FILE


def chapter_84_output_path(project_id: str, version: str) -> Path:
    return output_version_dir(project_id, version) / CHAPTER_84_FILE


def service_boq_parse_dir(project_id: str) -> Path:
    return physical_project_root(project_id) / Path(_paths(project_id)["service_boq_parse"])


def maint_proposal_parse_dir(project_id: str) -> Path:
    return physical_project_root(project_id) / Path(_paths(project_id)["maint_proposal_parse"])


def manifest_path(project_id: str) -> Path:
    return physical_project_root(project_id) / Path(_paths(project_id)["proposal_draft_manifest"])


def output_xlsx_path(project_id: str, version: str | None = None) -> Path:
    paths = _paths(project_id)
    if version:
        return output_version_dir(project_id, version) / "服务配置.xlsx"
    return physical_project_root(project_id) / Path(paths["service_delivery_ui_out"])


def service_content_xlsx_path(project_id: str, version: str | None = None) -> Path:
    paths = _paths(project_id)
    if version:
        return output_version_dir(project_id, version) / "服务内容.xlsx"
    return physical_project_root(project_id) / Path(paths["service_content_out"])


def maint_strategy_xlsx_path(project_id: str, version: str | None = None) -> Path:
    paths = _paths(project_id)
    if version:
        return output_version_dir(project_id, version) / "维保策略.xlsx"
    return physical_project_root(project_id) / Path(paths["maint_strategy_out"])


def maint_sla_xlsx_path(project_id: str, version: str | None = None) -> Path:
    paths = _paths(project_id)
    if version:
        return output_version_dir(project_id, version) / "维保SLA.xlsx"
    return physical_project_root(project_id) / Path(paths["maint_sla_out"])


def device_boq_parse_dir(project_id: str) -> Path:
    return physical_project_root(project_id) / Path(_paths(project_id)["device_boq_parse"])


def product_basic_info_path(project_id: str) -> Path:
    return physical_project_root(project_id) / Path(_paths(project_id)["product_basic_info"])


def device_table_xlsx_path(project_id: str, version: str | None = None) -> Path:
    paths = _paths(project_id)
    if version:
        return output_version_dir(project_id, version) / "设备信息表.xlsx"
    return physical_project_root(project_id) / Path(paths["device_table_out"]) / "设备信息表.xlsx"


def version_info_path(project_id: str, version: str) -> Path:
    return output_version_dir(project_id, version) / VERSION_MANIFEST_FILE


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_display_datetime(iso: str | None) -> str | None:
    """API 响应用展示时间（东八区），避免把 ISO 原串透给前端。"""
    if not iso:
        return None
    # Already in display format; avoid applying timezone twice.
    if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", iso):
        return iso
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(DISPLAY_TZ)
        return local.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def manifest_activity_fields(manifest: dict[str, Any]) -> dict[str, str | None]:
    """页头元数据时间/人名字段（展示用）。"""
    from agent.proposal.auth import proposal_operator_display_name

    return {
        "createdBy": manifest.get("createdBy") or proposal_operator_display_name(),
        "createdAt": format_display_datetime(manifest.get("createdAt")),
        "updatedBy": manifest.get("updatedBy") or proposal_operator_display_name(),
        "updatedAt": format_display_datetime(manifest.get("updatedAt")),
        "etag": manifest.get("etag"),
    }


def touch_draft_manifest(
    project_id: str,
    *,
    updated_by: str,
    mark_dirty: bool = True,
) -> dict[str, Any]:
    """草稿有编辑活动时更新 manifest 时间戳（真实服务器时间，非 mock）。"""
    manifest = load_manifest(project_id)
    now = _now_iso()
    if not manifest.get("createdAt"):
        manifest["createdAt"] = now
        manifest["createdBy"] = updated_by
    manifest["updatedBy"] = updated_by
    if mark_dirty:
        manifest["dirty"] = True
    saved = save_manifest(project_id, manifest)
    try:
        from agent.proposal.services import metadata as metadata_service

        metadata_service.touch_metadata_on_save(project_id, updated_by)
    except Exception:
        pass
    return saved


def compute_etag(manifest: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "updatedAt": manifest.get("updatedAt"),
            "workingVersionLabel": manifest.get("workingVersionLabel"),
            "changeRecords": manifest.get("changeRecords"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f'W/"{digest}"'


def default_manifest(project_id: str) -> dict[str, Any]:
    return {
        "projectId": project_id,
        "baseProposalVersion": None,
        "workingVersionLabel": "草稿",
        "status": "draft",
        "createdBy": None,
        "createdAt": None,
        "updatedBy": None,
        "updatedAt": None,
        "dirty": False,
        "changeDescription": "",
        "changeRecords": [],
        "latestReleaseVersion": None,
        "publishedVersions": [],
        "etag": 'W/"init"',
    }


def load_manifest(project_id: str) -> dict[str, Any]:
    manifest = load_json(manifest_path(project_id), default_manifest(project_id))
    manifest.setdefault("projectId", project_id)
    manifest.setdefault("publishedVersions", [])
    manifest.setdefault("changeRecords", [])
    manifest.setdefault("status", "draft")
    manifest.setdefault("workingVersionLabel", "草稿")
    if "etag" not in manifest:
        manifest["etag"] = compute_etag(manifest)
    return manifest


def save_manifest(project_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    manifest["updatedAt"] = _now_iso()
    manifest["etag"] = compute_etag(manifest)
    save_json(manifest_path(project_id), manifest)
    return manifest


def load_chapter_02(project_id: str, version: str = "draft") -> dict[str, Any]:
    if version == "draft":
        return load_json(chapter_02_draft_path(project_id), {"rows": []})
    path = chapter_02_output_path(project_id, version)
    if not path.exists():
        return {"rows": []}
    return load_json(path, {"rows": []})


def save_chapter_02_draft(project_id: str, payload: dict[str, Any]) -> None:
    save_json(chapter_02_draft_path(project_id), payload)


def save_chapter_02_output(project_id: str, version: str, payload: dict[str, Any]) -> None:
    save_json(chapter_02_output_path(project_id, version), payload)


def load_chapter_81(project_id: str, version: str = "draft") -> dict[str, Any]:
    if version == "draft":
        return load_json(chapter_81_draft_path(project_id), {"rows": []})
    path = chapter_81_output_path(project_id, version)
    if not path.exists():
        return {"rows": []}
    return load_json(path, {"rows": []})


def save_chapter_81_draft(project_id: str, payload: dict[str, Any]) -> None:
    save_json(chapter_81_draft_path(project_id), payload)


def save_chapter_81_output(project_id: str, version: str, payload: dict[str, Any]) -> None:
    save_json(chapter_81_output_path(project_id, version), payload)


def load_chapter_82(project_id: str, version: str = "draft") -> dict[str, Any]:
    if version == "draft":
        return load_json(chapter_82_draft_path(project_id), {"rows": []})
    path = chapter_82_output_path(project_id, version)
    if not path.exists():
        return {"rows": []}
    return load_json(path, {"rows": []})


def save_chapter_82_draft(project_id: str, payload: dict[str, Any]) -> None:
    save_json(chapter_82_draft_path(project_id), payload)


def save_chapter_82_output(project_id: str, version: str, payload: dict[str, Any]) -> None:
    save_json(chapter_82_output_path(project_id, version), payload)


def load_chapter_83(project_id: str, version: str = "draft") -> dict[str, Any]:
    if version == "draft":
        return load_json(chapter_83_draft_path(project_id), {"rows": []})
    path = chapter_83_output_path(project_id, version)
    if not path.exists():
        return {"rows": []}
    return load_json(path, {"rows": []})


def save_chapter_83_draft(project_id: str, payload: dict[str, Any]) -> None:
    save_json(chapter_83_draft_path(project_id), payload)


def save_chapter_83_output(project_id: str, version: str, payload: dict[str, Any]) -> None:
    save_json(chapter_83_output_path(project_id, version), payload)


def _default_chapter_84() -> dict[str, Any]:
    return {"hardwareSupport": "", "serviceLevel": "", "rows": []}


def load_chapter_84(project_id: str, version: str = "draft") -> dict[str, Any]:
    if version == "draft":
        return load_json(chapter_84_draft_path(project_id), _default_chapter_84())
    path = chapter_84_output_path(project_id, version)
    if not path.exists():
        return _default_chapter_84()
    return load_json(path, _default_chapter_84())


def save_chapter_84_draft(project_id: str, payload: dict[str, Any]) -> None:
    save_json(chapter_84_draft_path(project_id), payload)


def save_chapter_84_output(project_id: str, version: str, payload: dict[str, Any]) -> None:
    save_json(chapter_84_output_path(project_id, version), payload)


def list_published_versions(project_id: str) -> list[str]:
    manifest = load_manifest(project_id)
    versions = list(manifest.get("publishedVersions") or [])
    root = output_versions_dir(project_id)
    if root.exists():
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / VERSION_MANIFEST_FILE).exists():
                name = child.name
                if name not in versions:
                    versions.append(name)

    ts_pattern = re.compile(r"_(\d{14})(?:_|$)")

    def _sort_key(ver: str) -> tuple[str, str]:
        match = ts_pattern.search(ver)
        # Sort by timestamp first; fallback to version string.
        ts = match.group(1) if match else ""
        return ts, ver

    return sorted(versions, key=_sort_key, reverse=True)


def load_version_info(project_id: str, version: str) -> dict[str, Any]:
    info = load_json(
        version_info_path(project_id, version),
        {
            "proposalVersion": version,
            "status": "published",
            "createdBy": None,
            "createdAt": None,
            "updatedBy": None,
            "updatedAt": None,
            "changeDescription": "",
            "changeRecords": [],
        },
    )
    if isinstance(info, dict):
        normalized = dict(info)
        for key in ("createdAt", "updatedAt"):
            val = normalized.get(key)
            if val:
                normalized[key] = format_display_datetime(str(val))
        if normalized != info:
            save_json(version_info_path(project_id, version), normalized)
        return normalized
    return info


def save_version_info(project_id: str, version: str, info: dict[str, Any]) -> None:
    normalized = dict(info)
    for key in ("createdAt", "updatedAt"):
        val = normalized.get(key)
        if val:
            normalized[key] = format_display_datetime(str(val))
    save_json(version_info_path(project_id, version), normalized)


def _rebuild_chapter_draft(
    project_id: str,
    version: str,
    *,
    output_path_fn,
    save_draft_fn,
) -> None:
    src = output_path_fn(project_id, version)
    if src.exists():
        payload = load_json(src, {"rows": []})
        for raw in payload.get("rows") or []:
            raw["proposalVersion"] = None
        save_draft_fn(project_id, payload)


def rebuild_draft_from_version(project_id: str, version: str, *, updated_by: str) -> dict[str, Any]:
    """Copy published output snapshot back into working draft after release."""
    _rebuild_chapter_draft(
        project_id, version, output_path_fn=chapter_02_output_path, save_draft_fn=save_chapter_02_draft
    )
    _rebuild_chapter_draft(
        project_id, version, output_path_fn=chapter_81_output_path, save_draft_fn=save_chapter_81_draft
    )
    _rebuild_chapter_draft(
        project_id, version, output_path_fn=chapter_82_output_path, save_draft_fn=save_chapter_82_draft
    )
    _rebuild_chapter_draft(
        project_id, version, output_path_fn=chapter_83_output_path, save_draft_fn=save_chapter_83_draft
    )
    ch84 = load_json(chapter_84_output_path(project_id, version), _default_chapter_84())
    for raw in ch84.get("rows") or []:
        raw["proposalVersion"] = None
    save_chapter_84_draft(project_id, ch84)

    manifest = load_manifest(project_id)
    now = _now_iso()
    if not manifest.get("createdAt"):
        manifest["createdAt"] = now
        manifest["createdBy"] = updated_by
    manifest.update(
        {
            "baseProposalVersion": version,
            "workingVersionLabel": "草稿",
            "status": "draft",
            "dirty": False,
            "latestReleaseVersion": version,
        }
    )
    return save_manifest(project_id, manifest)


def archive_draft_snapshot(project_id: str, version: str) -> None:
    src = draft_dir(project_id)
    if not src.exists():
        return
    archive_name = f"draft.archive.{version.replace('/', '_')}"
    dest = draft_dir(project_id).parent / archive_name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("draft.archive.*"))


def assert_draft_editable(project_id: str, version: str) -> None:
    if version == "draft":
        return

    from agent.proposal.errors import ProposalApiError

    raise ProposalApiError(
        409,
        "READONLY_VERSION",
        f"版本 {version} 已 Release，不可编辑",
    )


def assert_etag_match(manifest: dict[str, Any], if_match: str | None) -> None:
    if not if_match:
        return
    from agent.proposal.errors import ProposalApiError

    current = manifest.get("etag", "")
    if if_match != current:
        raise ProposalApiError(409, "ETAG_MISMATCH", "草稿已被他人修改，请刷新后重试")
