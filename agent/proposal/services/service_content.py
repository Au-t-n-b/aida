"""8.2 服务配置 — business logic."""
from __future__ import annotations

import uuid
from typing import Any

from agent.proposal.assemblers.service_boq_assembler import assemble_service_content
from agent.proposal.auth import proposal_operator_display_name
from agent.proposal.draft_store import (
    assert_draft_editable,
    load_chapter_82,
    manifest_activity_fields,
    save_chapter_82_draft,
    touch_draft_manifest,
)
from agent.proposal.errors import ProposalApiError
from agent.proposal.models import (
    DataSource,
    PatchServiceContentBody,
    PostServiceContentBody,
    RowLevel,
    ServiceContentRow,
)


def _row_from_dict(raw: dict) -> ServiceContentRow:
    return ServiceContentRow.model_validate(raw)


def _to_api_row(row: ServiceContentRow) -> dict[str, Any]:
    data = row.model_dump(by_alias=True, mode="json")
    data.pop("saleCode", None)
    data.pop("internalSeq", None)
    return data


def _load_all_rows(project_id: str, version: str) -> list[dict]:
    payload = load_chapter_82(project_id, version)
    return list(payload.get("rows") or [])


def list_rows(
    project_id: str,
    *,
    version: str = "draft",
    collapse: bool = True,
    expand_offering_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ServiceContentRow], int]:
    if version != "draft":
        payload = load_chapter_82(project_id, version)
        if not payload.get("rows"):
            raise ProposalApiError(404, "NOT_FOUND", f"版本 {version} 不存在")
    else:
        payload = load_chapter_82(project_id, "draft")

    rows = [_row_from_dict(r) for r in payload.get("rows") or []]

    if expand_offering_id:
        filtered = [r for r in rows if r.row_id == expand_offering_id or r.parent_row_id == expand_offering_id]
        return filtered, len(filtered)

    if collapse:
        rows = [r for r in rows if r.row_level == RowLevel.L1]

    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return rows[start:end], total


def parse_service_boq(
    project_id: str,
    *,
    force: bool = False,
    version: str = "draft",
) -> tuple[list[ServiceContentRow], int]:
    assert_draft_editable(project_id, version)

    existing = _load_all_rows(project_id, "draft")
    manual_rows = [r for r in existing if r.get("dataSource") == DataSource.MANUAL.value]
    assembled = assemble_service_content(project_id)
    if force:
        merged = assembled
    else:
        merged = assembled + manual_rows

    if not merged:
        raise ProposalApiError(
            422,
            "BR_PROPOSAL_PARSE_EMPTY",
            "未找到服务 BOQ 解析结果，请先上传并解析",
        )

    save_chapter_82_draft(project_id, {"rows": merged})
    touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return [_row_from_dict(r) for r in merged], len(merged)


def patch_row(
    project_id: str,
    row_id: str,
    body: PatchServiceContentBody,
    *,
    version: str = "draft",
) -> tuple[ServiceContentRow, dict[str, str | None]]:
    assert_draft_editable(project_id, version)

    rows = _load_all_rows(project_id, "draft")
    target: dict | None = None
    for row in rows:
        if row.get("rowId") == row_id:
            target = row
            break
    if target is None:
        raise ProposalApiError(404, "NOT_FOUND", f"行 {row_id} 不存在")

    if body.service_name is not None:
        target["serviceName"] = body.service_name
    if body.service_content is not None:
        target["serviceContent"] = body.service_content
    if body.quantity is not None:
        target["quantity"] = body.quantity
    if body.unit is not None:
        target["unit"] = body.unit
    target["dataSource"] = DataSource.MANUAL.value

    save_chapter_82_draft(project_id, {"rows": rows})
    manifest = touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return _row_from_dict(target), manifest_activity_fields(manifest)


def create_row(
    project_id: str,
    body: PostServiceContentBody,
    *,
    version: str = "draft",
) -> tuple[ServiceContentRow, dict[str, str | None]]:
    assert_draft_editable(project_id, version)

    rows = _load_all_rows(project_id, "draft")
    new_row = {
        "rowId": str(uuid.uuid4()),
        "serviceName": body.service_name,
        "serviceContent": body.service_content,
        "quantity": body.quantity,
        "unit": body.unit,
        "rowLevel": RowLevel.L2.value,
        "parentRowId": body.parent_row_id,
        "saleCode": None,
        "internalSeq": None,
        "dataSource": DataSource.MANUAL.value,
        "proposalVersion": None,
    }
    rows.append(new_row)
    save_chapter_82_draft(project_id, {"rows": rows})
    manifest = touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return _row_from_dict(new_row), manifest_activity_fields(manifest)


def delete_row(
    project_id: str,
    row_id: str,
    *,
    confirm: bool = False,
    version: str = "draft",
) -> dict[str, str | None]:
    assert_draft_editable(project_id, version)

    rows = _load_all_rows(project_id, "draft")
    target: dict | None = None
    for row in rows:
        if row.get("rowId") == row_id:
            target = row
            break
    if target is None:
        raise ProposalApiError(404, "NOT_FOUND", f"行 {row_id} 不存在")

    if target.get("dataSource") == DataSource.AUTO.value and not confirm:
        raise ProposalApiError(
            409,
            "CONFIRM_REQUIRED",
            "自动解析行删除需 confirm=true",
        )

    remaining = [r for r in rows if r.get("rowId") != row_id and r.get("parentRowId") != row_id]
    save_chapter_82_draft(project_id, {"rows": remaining})
    manifest = touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return manifest_activity_fields(manifest)
