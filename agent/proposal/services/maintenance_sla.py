"""8.4 维保 SLA — business logic."""
from __future__ import annotations

from typing import Any

from agent.proposal.assemblers.maintenance_sla_mapper import map_sla_parse_to_draft
from agent.proposal.assemblers.maintenance_sla_reader import load_maintenance_sla_parse_json
from agent.proposal.auth import proposal_operator_display_name
from agent.proposal.draft_store import (
    assert_draft_editable,
    load_chapter_84,
    manifest_activity_fields,
    save_chapter_84_draft,
    touch_draft_manifest,
)
from agent.proposal.errors import ProposalApiError
from agent.proposal.models import (
    DataSource,
    MaintenanceSlaRow,
    PatchMaintenanceSlaBody,
    PatchMaintenanceSlaHardwareSupportBody,
)


def _load_payload(project_id: str, version: str = "draft") -> dict[str, Any]:
    payload = load_chapter_84(project_id, version)
    return {
        "hardwareSupport": payload.get("hardwareSupport") or "",
        "serviceLevel": payload.get("serviceLevel") or "",
        "rows": list(payload.get("rows") or []),
    }


def _row_from_dict(raw: dict) -> MaintenanceSlaRow:
    return MaintenanceSlaRow.model_validate(raw)


def _to_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "hardwareSupport": payload.get("hardwareSupport") or "",
        "serviceLevel": payload.get("serviceLevel") or "",
        "rows": [_row_from_dict(r) for r in payload.get("rows") or []],
    }


def serialize_sla_rows(
    raw_rows: list[dict[str, Any]],
    rows: list[MaintenanceSlaRow],
) -> list[dict[str, Any]]:
    """API JSON rows — always include seq from draft/mapper raw payload."""
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        item = row.model_dump(by_alias=True, mode="json")
        raw_seq = raw_rows[i].get("seq") if i < len(raw_rows) else None
        item["seq"] = str(
            raw_seq if raw_seq is not None else item.get("seq") or row.seq or "1"
        )
        out.append(item)
    return out


def get_sla(
    project_id: str,
    *,
    version: str = "draft",
) -> dict[str, Any]:
    if version != "draft":
        payload = load_chapter_84(project_id, version)
        if not payload.get("rows") and not payload.get("hardwareSupport"):
            raise ProposalApiError(404, "NOT_FOUND", f"版本 {version} 不存在")
    else:
        payload = load_chapter_84(project_id, "draft")

    result = _to_response(payload)
    if version == "draft" and not result["rows"]:
        result["meta"] = {
            "hint": "请确认维保建议书解析结果已落盘并触发 parse，或手工录入 SLA 行",
        }
    return result


def parse_maintenance_proposal_doc(
    project_id: str,
    *,
    force: bool = False,
    version: str = "draft",
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    assert_draft_editable(project_id, version)

    existing = _load_payload(project_id, "draft")
    manual_rows = [
        r for r in existing["rows"] if r.get("dataSource") == DataSource.MANUAL.value
    ]

    parse_json = load_maintenance_sla_parse_json(project_id)
    dependencies: list[dict[str, str]] = []
    if not parse_json or not parse_json.get("tables"):
        dependencies.append({
            "code": "SYS_DEPENDENCY",
            "message": "未找到维保建议书解析结果",
        })
        return _to_response(existing), dependencies

    mapped = map_sla_parse_to_draft(
        parse_json,
        service_level=existing.get("serviceLevel") or None,
    )
    auto_rows = mapped["rows"]
    merged_rows = auto_rows + manual_rows

    payload = {
        "hardwareSupport": mapped["hardwareSupport"] or existing["hardwareSupport"],
        "serviceLevel": mapped["serviceLevel"] or existing["serviceLevel"],
        "rows": merged_rows,
    }
    save_chapter_84_draft(project_id, payload)
    touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return _to_response(payload), dependencies


def patch_row(
    project_id: str,
    row_id: str,
    body: PatchMaintenanceSlaBody,
    *,
    version: str = "draft",
) -> tuple[MaintenanceSlaRow, dict[str, str | None]]:
    assert_draft_editable(project_id, version)

    payload = _load_payload(project_id, "draft")
    target: dict | None = None
    for row in payload["rows"]:
        if row.get("rowId") == row_id:
            target = row
            break
    if target is None:
        raise ProposalApiError(404, "NOT_FOUND", f"行 {row_id} 不存在")

    if body.severity_level is not None:
        target["severityLevel"] = body.severity_level
    if body.coverage_period is not None:
        target["coveragePeriod"] = body.coverage_period
    if body.response_time is not None:
        target["responseTime"] = body.response_time
    if body.restore_time is not None:
        target["restoreTime"] = body.restore_time
    if body.resolve_time is not None:
        target["resolveTime"] = body.resolve_time

    target["dataSource"] = DataSource.MANUAL.value
    save_chapter_84_draft(project_id, payload)
    manifest = touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return _row_from_dict(target), manifest_activity_fields(manifest)


def patch_hardware_support(
    project_id: str,
    body: PatchMaintenanceSlaHardwareSupportBody,
    *,
    version: str = "draft",
) -> tuple[dict[str, Any], dict[str, str | None]]:
    assert_draft_editable(project_id, version)

    payload = _load_payload(project_id, "draft")
    payload["hardwareSupport"] = body.hardware_support
    save_chapter_84_draft(project_id, payload)
    manifest = touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return {
        "hardwareSupport": payload["hardwareSupport"],
        "serviceLevel": payload["serviceLevel"],
    }, manifest_activity_fields(manifest)
