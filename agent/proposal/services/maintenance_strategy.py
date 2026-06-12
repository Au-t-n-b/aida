"""8.3 维保策略 — business logic."""
from __future__ import annotations

from typing import Any

from agent.proposal.assemblers.maint_date_calculator import (
    compute_over_eos,
    end_date_from_start,
    format_iso_date,
    parse_iso_date,
)
from agent.proposal.assemblers.maint_device_bridge import build_chapter02_device_index
from agent.proposal.assemblers.maintenance_boq_disassembler import disassemble_maintenance_strategy
from agent.proposal.auth import proposal_operator_display_name
from agent.proposal.draft_store import (
    assert_draft_editable,
    load_chapter_83,
    manifest_activity_fields,
    save_chapter_83_draft,
    touch_draft_manifest,
)
from agent.proposal.errors import ProposalApiError
from agent.proposal.models import (
    DataSource,
    MaintenanceStrategyRow,
    OverEos,
    PatchMaintenanceStrategyBody,
)


def _row_from_dict(raw: dict) -> MaintenanceStrategyRow:
    return MaintenanceStrategyRow.model_validate(raw)


def _load_all_rows(project_id: str, version: str) -> list[dict]:
    payload = load_chapter_83(project_id, version)
    return list(payload.get("rows") or [])


def list_rows(
    project_id: str,
    *,
    version: str = "draft",
) -> list[MaintenanceStrategyRow]:
    if version != "draft":
        payload = load_chapter_83(project_id, version)
        if not payload.get("rows"):
            raise ProposalApiError(404, "NOT_FOUND", f"版本 {version} 不存在")
    else:
        payload = load_chapter_83(project_id, "draft")
    return [_row_from_dict(r) for r in payload.get("rows") or []]


def parse_maintenance_boq(
    project_id: str,
    *,
    force: bool = False,
    version: str = "draft",
) -> tuple[list[MaintenanceStrategyRow], list[dict[str, str]], bool]:
    assert_draft_editable(project_id, version)

    existing = _load_all_rows(project_id, "draft")
    manual_rows = [r for r in existing if r.get("dataSource") == DataSource.MANUAL.value]

    allowed_models, device_by_model = build_chapter02_device_index(project_id)
    dependencies: list[dict[str, str]] = []
    had_dep_failure = False
    if not allowed_models:
        had_dep_failure = True
        dependencies.append({
            "code": "SYS_DEPENDENCY",
            "message": "第2章设备配置信息为空，无法校验产品型号与 EOS",
        })

    assembled = disassemble_maintenance_strategy(
        project_id,
        allowed_device_models=allowed_models,
        device_rows_by_model=device_by_model,
    )
    if force:
        merged = assembled
    else:
        merged = assembled + manual_rows

    if not merged:
        raise ProposalApiError(
            422,
            "BR_PROPOSAL_PARSE_EMPTY",
            "未找到维保 BOQ 解析结果",
        )

    save_chapter_83_draft(project_id, {"rows": merged})
    touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return [_row_from_dict(r) for r in merged], dependencies, had_dep_failure


def _recompute_over_eos(target: dict) -> None:
    eos = parse_iso_date(target.get("productEosDate"))
    end = parse_iso_date(target.get("maintEndDate"))
    if end:
        target["overEos"] = compute_over_eos(eos, end).value


def patch_row(
    project_id: str,
    row_id: str,
    body: PatchMaintenanceStrategyBody,
    *,
    version: str = "draft",
) -> tuple[MaintenanceStrategyRow, dict[str, str | None]]:
    assert_draft_editable(project_id, version)

    rows = _load_all_rows(project_id, "draft")
    target: dict | None = None
    for row in rows:
        if row.get("rowId") == row_id:
            target = row
            break
    if target is None:
        raise ProposalApiError(404, "NOT_FOUND", f"行 {row_id} 不存在")

    if body.product_model is not None:
        target["productModel"] = body.product_model
    if body.warranty_policy is not None:
        target["warrantyPolicy"] = body.warranty_policy
    if body.maintenance_policy is not None:
        target["maintenancePolicy"] = body.maintenance_policy
    if body.maint_start_date is not None:
        target["maintStartDate"] = body.maint_start_date
        if body.recalculate_end and target.get("maintYears"):
            start = parse_iso_date(body.maint_start_date)
            if start:
                end = end_date_from_start(start, int(target["maintYears"]))
                target["maintEndDate"] = format_iso_date(end)
    if body.maint_end_date is not None:
        target["maintEndDate"] = body.maint_end_date
    if body.product_eos_date is not None:
        target["productEosDate"] = body.product_eos_date or None
    if body.over_eos_approval is not None:
        target["overEosApproval"] = body.over_eos_approval

    _recompute_over_eos(target)
    target["dataSource"] = DataSource.MANUAL.value

    save_chapter_83_draft(project_id, {"rows": rows})
    manifest = touch_draft_manifest(
        project_id,
        updated_by=proposal_operator_display_name(),
        mark_dirty=True,
    )
    return _row_from_dict(target), manifest_activity_fields(manifest)
