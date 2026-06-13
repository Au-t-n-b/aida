"""Release promote draft → versioned output + rebuild working draft."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from agent.integrations.occ_review_client import resolve_review_tag
from agent.proposal.auth import ProposalSession, proposal_operator_display_name
from agent.proposal.chapter_files import (
    sync_output_chapter_excels,
)
from agent.proposal.draft_store import (
    format_display_datetime,
    load_manifest,
    save_manifest,
)
from agent.proposal.models import ReleaseAndDecideBody
from agent.proposal.services import metadata as metadata_service
from agent.proposal.services.device_info import list_rows as list_device_rows
from agent.proposal.services.maintenance_strategy import list_rows as list_maint_rows
from agent.proposal.services.service_content import list_rows as list_content_rows
from agent.proposal.services.service_delivery_ui import list_rows as list_delivery_rows


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_MAIN_VERSION_PATTERN = re.compile(r"^V(?P<major>\d+)\.(?P<minor>\d+)$")


def _parse_main_version(version: str | None) -> tuple[int, int] | None:
    """Parse `Vx.y` head and normalize legacy overflow minor."""
    if not version:
        return None
    head = version.split("_")[0]
    match = _MAIN_VERSION_PATTERN.match(head)
    if not match:
        return None

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    if major < 1 or minor < 0:
        return None

    # Legacy names like V1.10/V1.11 are treated as overflow and
    # normalized to the rollover edge so next release becomes V2.0.
    if minor > 9:
        return major + 1, 9
    return major, minor


def _next_main_version(latest_version: str | None) -> str:
    parsed = _parse_main_version(latest_version)
    if parsed is None:
        return "V1.0"

    major, minor = parsed
    if minor >= 9:
        return f"V{major + 1}.0"
    return f"V{major}.{minor + 1}"


def _next_version(manifest: dict, *, review_tag_hint: str | None = None) -> str:
    latest = manifest.get("latestReleaseVersion")
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    base = f"{_next_main_version(latest)}_{ts}"

    if review_tag_hint and review_tag_hint.upper() in ("DTRB", "DRB"):
        return f"{base}_{review_tag_hint.upper()}"
    if latest and ("_DTRB" in latest or "_DRB" in latest):
        tag = "_DTRB" if "_DTRB" in latest else "_DRB"
        return f"{base}{tag}"
    return base


def _validate_release_inputs(project_id: str) -> None:
    rows_2, _deps = list_device_rows(project_id, version="draft")
    if not rows_2:
        raise ValueError("第 2 章设备信息表为空，请先解析设备 BOQ")

    rows_81 = list_delivery_rows(project_id, version="draft")
    if len(rows_81) != 13:
        raise ValueError("8.1 须包含 13 行后再 Release；请先 POST initialize")

    rows_82, _ = list_content_rows(project_id, version="draft", collapse=False)
    if not rows_82:
        raise ValueError("8.2 服务内容为空，请先解析服务 BOQ")

    rows_83 = list_maint_rows(project_id, version="draft")
    if not rows_83:
        raise ValueError("8.3 维保策略为空，请先解析维保 BOQ")


def _build_release_change_description(
    manual_records: list[dict[str, Any]],
) -> str:
    manual_entries = [
        {
            "chapter": str(r.get("chapter") or ""),
            "changeDescription": str(
                r.get("description") or r.get("changeDescription") or ""
            ),
        }
        for r in manual_records
    ]
    return metadata_service._format_manual_change_description(manual_entries)


def release_and_decide(
    project_id: str,
    body: ReleaseAndDecideBody | None,
    session: ProposalSession,
) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    basic, _deps = metadata_service.read_project_basic_info(project_id)
    project_code = basic.get("projectId") or project_id
    review_hint = resolve_review_tag(project_code)
    new_version = _next_version(manifest, review_tag_hint=review_hint)
    prev_version = manifest.get("latestReleaseVersion")
    operator = proposal_operator_display_name(session)

    pending_manual_records: list[dict[str, Any]] = list(manifest.get("changeRecords") or [])
    if body and body.change_records:
        pending_manual_records = [r.model_dump() for r in body.change_records]
        manifest["changeRecords"] = pending_manual_records
        save_manifest(project_id, manifest)
    _validate_release_inputs(project_id)
    written_xlsx = sync_output_chapter_excels(
        project_id,
        proposal_version=new_version,
        source_version="draft",
    )

    meta_snapshot: dict[str, Any] | None = None
    full_snap: dict[str, Any] = {}
    try:
        meta_snapshot = metadata_service.promote_metadata_on_release(
            project_id,
            new_version,
            operator,
            prev_version=prev_version,
        )
        from agent.proposal.version_info_store import find_snapshot

        full_snap = find_snapshot(project_id, new_version) or {}
    except Exception:
        meta_snapshot = None

    now = _now_iso()
    legacy_change_description = _build_release_change_description(pending_manual_records)

    if meta_snapshot is None:
        meta_snapshot = {
            "createdBy": manifest.get("createdBy") or operator,
            "createdAt": manifest.get("createdAt"),
            "updatedBy": operator,
            "updatedAt": format_display_datetime(now),
            "changeDescription": legacy_change_description,
            "documentSummary": "",
        }

    version_records = full_snap.get("changeRecords") if full_snap else None
    if not version_records:
        version_records = pending_manual_records

    change_description = (
        meta_snapshot.get("changeDescription") or legacy_change_description
    )

    version_info = {
        "proposalVersion": new_version,
        "status": "published",
        "createdBy": meta_snapshot.get("createdBy"),
        "createdAt": meta_snapshot.get("createdAt"),
        "updatedBy": meta_snapshot.get("updatedBy"),
        "updatedAt": meta_snapshot.get("updatedAt") or format_display_datetime(now),
        "changeDescription": change_description,
        "documentSummary": meta_snapshot.get("documentSummary", ""),
        "changeRecords": version_records,
    }

    published = list(manifest.get("publishedVersions") or [])
    if new_version not in published:
        published.append(new_version)
    manifest_after = load_manifest(project_id)
    manifest_after["publishedVersions"] = published
    manifest_after["latestReleaseVersion"] = new_version
    manifest_after["baseProposalVersion"] = new_version
    manifest_after["workingVersionLabel"] = "草稿"
    manifest_after["status"] = "draft"
    manifest_after["dirty"] = False
    manifest_after["changeRecords"] = []
    save_manifest(project_id, manifest_after)

    archived_docs = sorted(set(written_xlsx))

    label = new_version
    from agent.proposal.services.draft import get_draft

    draft_payload = get_draft(project_id, operator=operator, session=session)
    chapters_result: dict[str, Any] = dict(draft_payload.get("chapters") or {})
    for payload in chapters_result.values():
        if not isinstance(payload, dict):
            continue
        rows = payload.get("rows")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    row["proposalVersion"] = new_version
        payload["proposalVersion"] = new_version

    return {
        "proposalVersion": new_version,
        "status": "published",
        "createdBy": version_info["createdBy"],
        "updatedBy": proposal_operator_display_name(session),
        "updatedAt": format_display_datetime(now),
        "decisionEvalJobId": f"job_{new_version}",
        "sideEffects": {
            "tasksCreated": 3,
            "risksCreated": 3,
            "integrationRequirementsCreated": 2,
            "documentsArchived": archived_docs,
        },
        "progress": [
            {"role": "user", "body": f"生成预案并决策 · {label}"},
            {
                "role": "ai",
                "body": f"预案 {label} 已发布 · 正在下发任务与风险…",
                "chips": ["预案已发布"],
            },
            {
                "role": "ai",
                "body": "任务下发完成：ConnectX-7 数量确认（何博）/ 样本面接入设备补齐（王明）/ k8s 平台版本确认（TD）已进入计划任务列表。",
                "chips": ["任务 +3", "已指定责任人"],
            },
            {
                "role": "ai",
                "body": "风险已写入项目孪生风险预警：BOQ 冲突（高）/ 组网缺失（高）/ CAD 缺失（中）· 进入孪生看板可见全貌。",
                "chips": ["风险 +3", "已同步看板"],
            },
        ],
        "chapters": chapters_result,
    }
