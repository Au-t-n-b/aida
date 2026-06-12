"""8.1 服务交付界面 — business logic (MVP)."""
from __future__ import annotations

import uuid

from agent.proposal.auth import proposal_operator_display_name
from agent.proposal.draft_store import (
    assert_draft_editable,
    load_chapter_81,
    manifest_activity_fields,
    save_chapter_81_draft,
    touch_draft_manifest,
)
from agent.proposal.enums.service_delivery_ui_template import (
    SERVICE_DELIVERY_UI_TEMPLATE,
    row_key,
)
from agent.proposal.errors import ProposalApiError
from agent.proposal.models import (
    DataSource,
    DeliveryChannel,
    PatchServiceDeliveryUiBody,
    ServiceDeliveryUiRow,
)


def _row_from_dict(raw: dict) -> ServiceDeliveryUiRow:
    return ServiceDeliveryUiRow.model_validate(raw)


def _row_to_dict(row: ServiceDeliveryUiRow) -> dict:
    return row.model_dump(by_alias=True, mode="json")


def list_rows(project_id: str, *, version: str = "draft") -> list[ServiceDeliveryUiRow]:
    if version != "draft":
        payload = load_chapter_81(project_id, version)
        if not payload.get("rows"):
            raise ProposalApiError(404, "NOT_FOUND", f"版本 {version} 不存在")
    else:
        payload = load_chapter_81(project_id, "draft")
    rows = payload.get("rows") or []
    return [_row_from_dict(r) for r in rows]


def initialize(
    project_id: str,
    *,
    strategy: str = "skip",
    version: str = "draft",
) -> tuple[list[ServiceDeliveryUiRow], int]:
    """Return (rows, inserted_count)."""
    assert_draft_editable(project_id, version)

    payload = load_chapter_81(project_id, "draft")
    existing: list[dict] = list(payload.get("rows") or [])
    by_key = {row_key(r["serviceMajor"], r["serviceItem"]): r for r in existing}

    inserted = 0
    for template in SERVICE_DELIVERY_UI_TEMPLATE:
        key = row_key(template.service_major, template.service_item)
        if key in by_key:
            if strategy == "merge":
                by_key[key]["deliveryChannel"] = DeliveryChannel.HUAWEI.value
                by_key[key]["dataSource"] = DataSource.AUTO.value
            continue

        by_key[key] = {
            "rowId": str(uuid.uuid4()),
            "serviceMajor": template.service_major,
            "serviceItem": template.service_item,
            "deliveryChannel": DeliveryChannel.HUAWEI.value,
            "dataSource": DataSource.AUTO.value,
            "proposalVersion": None,
        }
        inserted += 1

    ordered: list[dict] = []
    for template in SERVICE_DELIVERY_UI_TEMPLATE:
        key = row_key(template.service_major, template.service_item)
        if key in by_key:
            ordered.append(by_key[key])

    save_chapter_81_draft(project_id, {"rows": ordered})
    if inserted > 0:
        touch_draft_manifest(
            project_id,
            updated_by=proposal_operator_display_name(),
            mark_dirty=False,
        )
    return [_row_from_dict(r) for r in ordered], inserted


def patch_row(
    project_id: str,
    row_id: str,
    body: PatchServiceDeliveryUiBody,
    *,
    version: str = "draft",
) -> tuple[ServiceDeliveryUiRow, dict[str, str | None]]:
    assert_draft_editable(project_id, version)

    payload = load_chapter_81(project_id, "draft")
    rows: list[dict] = list(payload.get("rows") or [])
    target: dict | None = None
    for row in rows:
        if row.get("rowId") == row_id:
            target = row
            break

    if target is None:
        raise ProposalApiError(404, "NOT_FOUND", f"行 {row_id} 不存在")

    target["deliveryChannel"] = body.delivery_channel.value
    target["dataSource"] = DataSource.MANUAL.value
    save_chapter_81_draft(project_id, {"rows": rows})
    manifest = touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return _row_from_dict(target), manifest_activity_fields(manifest)


def validate_delivery_channel(value: str) -> DeliveryChannel:
    try:
        return DeliveryChannel(value)
    except ValueError as exc:
        raise ProposalApiError(
            400,
            "INVALID_DELIVERY_CHANNEL",
            "deliveryChannel 仅允许 华为 | 客户",
        ) from exc
