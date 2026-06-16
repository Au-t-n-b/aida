"""Proposal module HTTP routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from agent.proposal.auth import (
    ProposalSession,
    require_proposal_read,
    require_proposal_release,
    require_proposal_write,
)
from agent.proposal.errors import ProposalApiError
from agent.proposal.models import (
    PatchDeviceInfoBody,
    PatchMaintenanceSlaBody,
    PatchMaintenanceSlaHardwareSupportBody,
    PatchMaintenanceStrategyBody,
    PatchMetadataBody,
    PatchServiceContentBody,
    PatchServiceDeliveryUiBody,
    PostServiceContentBody,
    PutDraftBody,
    ReleaseAndDecideBody,
    ReleaseBody,
)
from agent.proposal.draft_store import load_chapter_84
from agent.proposal.response import proposal_meta, success
from agent.proposal.services import draft as draft_service
from agent.proposal.services import device_info as device_svc
from agent.proposal.services import export as export_service
from agent.proposal.services import release as release_service
from agent.proposal.services import maintenance_sla as sla_svc
from agent.proposal.services import maintenance_strategy as maint_svc
from agent.proposal.services import service_content as content_svc
from agent.proposal.services import service_delivery_ui as svc
from agent.proposal.services import metadata as metadata_service
from agent.proposal.services import versions as versions_service
from agent.proposal.draft_store import assert_draft_editable
from agent.proposal_request_logging import ProposalLoggingRoute

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/proposal",
    tags=["proposal"],
    route_class=ProposalLoggingRoute,
)


@router.get("/draft")
async def get_draft(
    project_id: str,
    request: Request,
    _session: ProposalSession = Depends(require_proposal_read),
):
    from agent.proposal.auth import proposal_operator_display_name

    # region agent log
    try:
        import json, time
        from pathlib import Path

        Path(".cursor/debug-f94a50.log").open("a", encoding="utf-8").write(
            json.dumps(
                {
                    "sessionId": "f94a50",
                    "runId": "pre-fix",
                    "hypothesisId": "H9",
                    "location": "agent/proposal/router.py:get_draft",
                    "message": "get_draft request/session snapshot",
                    "data": {
                        "xUserRoleHeader": request.headers.get("X-User-Role"),
                        "xUserAccountHeader": request.headers.get("X-User-Account"),
                        "sessionRole": getattr(_session, "role", None),
                        "sessionAccount": getattr(_session, "account", None),
                    },
                    "timestamp": int(time.time() * 1000),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    except Exception:
        pass
    # endregion
    data = await run_in_threadpool(
        draft_service.get_draft,
        project_id,
        operator=proposal_operator_display_name(_session),
        session=_session,
    )
    # region agent log
    try:
        import json, time
        from pathlib import Path

        Path(".cursor/debug-f94a50.log").open("a", encoding="utf-8").write(
            json.dumps(
                {
                    "sessionId": "f94a50",
                    "runId": "pre-fix",
                    "hypothesisId": "H9",
                    "location": "agent/proposal/router.py:get_draft",
                    "message": "get_draft response metadata snapshot",
                    "data": {
                        "manifestUpdatedBy": ((data.get("manifest") or {}).get("updatedBy") if isinstance(data, dict) else None),
                        "metadataUpdatedBy": ((data.get("metadata") or {}).get("updatedBy") if isinstance(data, dict) else None),
                    },
                    "timestamp": int(time.time() * 1000),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    except Exception:
        pass
    # endregion
    return success(
        data,
        proposal_meta(project_id, proposal_version="draft", source_layer="draft"),
    )


@router.put("/draft")
def put_draft(
    project_id: str,
    body: PutDraftBody,
    request: Request,
    session: ProposalSession = Depends(require_proposal_write),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    # region agent log
    try:
        import json, time
        from pathlib import Path

        Path(".cursor/debug-f94a50.log").open("a", encoding="utf-8").write(
            json.dumps(
                {
                    "sessionId": "f94a50",
                    "runId": "pre-fix",
                    "hypothesisId": "H6",
                    "location": "agent/proposal/router.py:put_draft",
                    "message": "put_draft request/session snapshot",
                    "data": {
                        "xUserRoleHeader": request.headers.get("X-User-Role"),
                        "xUserAccountHeader": request.headers.get("X-User-Account"),
                        "sessionRole": getattr(session, "role", None),
                        "sessionAccount": getattr(session, "account", None),
                    },
                    "timestamp": int(time.time() * 1000),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    except Exception:
        pass
    # endregion
    data = draft_service.save_draft(project_id, body, session, if_match=if_match)
    if isinstance(data, dict):
        data["_debugSessionAccount"] = getattr(session, "account", None)
        data["_debugSessionRole"] = getattr(session, "role", None)
    return success(
        data,
        proposal_meta(project_id, proposal_version="draft", source_layer="draft"),
    )


@router.get("/metadata")
def get_metadata(
    project_id: str,
    version: str = Query(default="draft"),
    session: ProposalSession = Depends(require_proposal_read),
):
    from agent.proposal.auth import proposal_operator_display_name

    data, deps = metadata_service.get_metadata(
        project_id,
        version,
        operator=proposal_operator_display_name(session),
    )
    layer = "draft" if version == "draft" else "output"
    return success(
        data,
        proposal_meta(
            project_id,
            proposal_version=version,
            source_layer=layer,
            dependencies=deps or None,
        ),
    )


@router.patch("/metadata")
def patch_metadata(
    project_id: str,
    body: PatchMetadataBody,
    version: str = Query(default="draft"),
    session: ProposalSession = Depends(require_proposal_write),
):
    from agent.proposal.auth import proposal_operator_display_name

    assert_draft_editable(project_id, version)
    operator = proposal_operator_display_name(session)
    if body.manual_change_log is not None:
        metadata_service.save_manual_change_log(
            project_id,
            [e.model_dump(by_alias=True) for e in body.manual_change_log],
            operator,
        )
    data = metadata_service.patch_metadata_draft(
        project_id, body.document_summary, session
    )
    return success(
        data,
        proposal_meta(project_id, proposal_version="draft", source_layer="draft"),
    )


@router.get("/metadata/cumulative-change-log")
def get_cumulative_change_log(
    project_id: str,
    _session: ProposalSession = Depends(require_proposal_read),
):
    entries = metadata_service.build_cumulative_change_log(project_id)
    return success(
        {"entries": entries},
        proposal_meta(project_id),
    )


@router.get("/versions")
def get_versions(
    project_id: str,
    _session: ProposalSession = Depends(require_proposal_read),
):
    from agent.proposal.auth import proposal_operator_display_name

    versions = versions_service.list_versions(
        project_id,
        operator=proposal_operator_display_name(_session),
    )
    return success(
        {"versions": versions},
        proposal_meta(project_id),
    )


@router.get("/versions/{proposal_version:path}")
def get_version_snapshot(
    project_id: str,
    proposal_version: str,
    _session: ProposalSession = Depends(require_proposal_read),
):
    data = versions_service.get_version_snapshot(project_id, proposal_version)
    layer = "draft" if proposal_version == "draft" else "output"
    return success(
        data,
        proposal_meta(
            project_id,
            proposal_version=proposal_version,
            source_layer=layer,
        ),
    )


@router.get("/export/document")
def export_document(
    project_id: str,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_read),
):
    content, filename = export_service.export_document_bytes(project_id, version)
    layer = "draft" if version == "draft" else "output"
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Proposal-Version": version,
            "X-Source-Layer": layer,
        },
    )


@router.get("/chapters/2/device-info")
def get_device_info(
    project_id: str,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_read),
):
    rows, dependencies = device_svc.list_rows(project_id, version=version)
    layer = "draft" if version == "draft" else "output"
    return success(
        {
            "rows": [r.model_dump(by_alias=True, mode="json") for r in rows],
            "total": len(rows),
        },
        proposal_meta(
            project_id,
            proposal_version=version,
            source_layer=layer,
            dependencies=dependencies or None,
        ),
    )


@router.patch("/chapters/2/device-info/{row_id}")
def patch_device_info(
    project_id: str,
    row_id: str,
    body: PatchDeviceInfoBody,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    row, activity = device_svc.patch_row(project_id, row_id, body, version=version)
    return success(
        row.model_dump(by_alias=True, mode="json"),
        proposal_meta(
            project_id,
            proposal_version=version,
            manifest_activity=activity,
        ),
    )


@router.post("/chapters/2/device-info/enrich")
def enrich_device_info(
    project_id: str,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    rows, dependencies = device_svc.enrich_draft_rows(project_id, version=version)
    return success(
        {
            "rows": [r.model_dump(by_alias=True, mode="json") for r in rows],
            "total": len(rows),
        },
        proposal_meta(
            project_id,
            proposal_version=version,
            dependencies=dependencies,
        ),
    )


@router.post("/parse/device-boq")
def parse_device_boq(
    project_id: str,
    force: bool = Query(default=False),
    enrich: bool = Query(default=False),
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    rows, dependencies = device_svc.parse_device_boq(
        project_id, force=force, enrich=enrich, version=version
    )
    return success(
        {
            "rows": [r.model_dump(by_alias=True, mode="json") for r in rows],
            "total": len(rows),
        },
        proposal_meta(
            project_id,
            proposal_version=version,
            dependencies=dependencies,
        ),
    )


@router.get("/chapters/8.1/service-delivery-ui")
def get_service_delivery_ui(
    project_id: str,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_read),
):
    rows = svc.list_rows(project_id, version=version)
    layer = "draft" if version == "draft" else "output"
    return success(
        {"rows": [r.model_dump(by_alias=True, mode="json") for r in rows]},
        proposal_meta(project_id, proposal_version=version, source_layer=layer),
    )


@router.post("/chapters/8.1/service-delivery-ui/initialize")
def initialize_service_delivery_ui(
    project_id: str,
    strategy: str = Query(default="skip"),
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    rows, inserted = svc.initialize(project_id, strategy=strategy, version=version)
    return success(
        {
            "rows": [r.model_dump(by_alias=True, mode="json") for r in rows],
            "inserted": inserted,
            "strategy": strategy,
        },
        proposal_meta(project_id, proposal_version=version),
    )


@router.patch("/chapters/8.1/service-delivery-ui/{row_id}")
def patch_service_delivery_ui(
    project_id: str,
    row_id: str,
    body: PatchServiceDeliveryUiBody,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    row, activity = svc.patch_row(project_id, row_id, body, version=version)
    return success(
        row.model_dump(by_alias=True, mode="json"),
        proposal_meta(
            project_id,
            proposal_version=version,
            manifest_activity=activity,
        ),
    )


@router.get("/chapters/8.2/service-content")
def get_service_content(
    project_id: str,
    version: str = Query(default="draft"),
    collapse: bool = Query(default=True),
    expand_offering_id: str | None = Query(default=None, alias="expandOfferingId"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    _session: ProposalSession = Depends(require_proposal_read),
):
    rows, total = content_svc.list_rows(
        project_id,
        version=version,
        collapse=collapse,
        expand_offering_id=expand_offering_id,
        page=page,
        page_size=page_size,
    )
    layer = "draft" if version == "draft" else "output"
    return success(
        {
            "rows": [content_svc._to_api_row(r) for r in rows],
            "total": total,
        },
        proposal_meta(project_id, proposal_version=version, source_layer=layer),
    )


@router.patch("/chapters/8.2/service-content/{row_id}")
def patch_service_content(
    project_id: str,
    row_id: str,
    body: PatchServiceContentBody,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    row, activity = content_svc.patch_row(project_id, row_id, body, version=version)
    return success(
        content_svc._to_api_row(row),
        proposal_meta(
            project_id,
            proposal_version=version,
            manifest_activity=activity,
        ),
    )


@router.post("/chapters/8.2/service-content")
def post_service_content(
    project_id: str,
    body: PostServiceContentBody,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    row, activity = content_svc.create_row(project_id, body, version=version)
    return success(
        content_svc._to_api_row(row),
        proposal_meta(
            project_id,
            proposal_version=version,
            manifest_activity=activity,
        ),
    )


@router.delete("/chapters/8.2/service-content/{row_id}")
def delete_service_content(
    project_id: str,
    row_id: str,
    confirm: bool = Query(default=False),
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    activity = content_svc.delete_row(
        project_id, row_id, confirm=confirm, version=version
    )
    return success(
        {"deleted": True, "rowId": row_id},
        proposal_meta(
            project_id,
            proposal_version=version,
            manifest_activity=activity,
        ),
    )


@router.post("/parse/service-boq")
def parse_service_boq(
    project_id: str,
    force: bool = Query(default=False),
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    rows, _count = content_svc.parse_service_boq(
        project_id, force=force, version=version
    )
    return success(
        {
            "rows": [content_svc._to_api_row(r) for r in rows],
            "total": len(rows),
        },
        proposal_meta(project_id, proposal_version=version),
    )


@router.get("/chapters/8.3/maintenance-strategy")
def get_maintenance_strategy(
    project_id: str,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_read),
):
    rows = maint_svc.list_rows(project_id, version=version)
    layer = "draft" if version == "draft" else "output"
    return success(
        {"rows": [r.model_dump(by_alias=True, mode="json") for r in rows]},
        proposal_meta(project_id, proposal_version=version, source_layer=layer),
    )


@router.patch("/chapters/8.3/maintenance-strategy/{row_id}")
def patch_maintenance_strategy(
    project_id: str,
    row_id: str,
    body: PatchMaintenanceStrategyBody,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    row, activity = maint_svc.patch_row(project_id, row_id, body, version=version)
    return success(
        row.model_dump(by_alias=True, mode="json"),
        proposal_meta(
            project_id,
            proposal_version=version,
            manifest_activity=activity,
        ),
    )


@router.post("/parse/maintenance-boq")
def parse_maintenance_boq(
    project_id: str,
    force: bool = Query(default=False),
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    rows, dependencies, _had_failure = maint_svc.parse_maintenance_boq(
        project_id, force=force, version=version
    )
    return success(
        {"rows": [r.model_dump(by_alias=True, mode="json") for r in rows]},
        proposal_meta(
            project_id,
            proposal_version=version,
            dependencies=dependencies,
        ),
    )


@router.get("/chapters/8.4/maintenance-sla")
def get_maintenance_sla(
    project_id: str,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_read),
):
    raw_payload = load_chapter_84(project_id, version)
    data = sla_svc.get_sla(project_id, version=version)
    layer = "draft" if version == "draft" else "output"
    payload = {
        "hardwareSupport": data["hardwareSupport"],
        "serviceLevel": data["serviceLevel"],
        "rows": sla_svc.serialize_sla_rows(
            raw_payload.get("rows") or [],
            data["rows"],
        ),
    }
    if data.get("meta"):
        payload["meta"] = data["meta"]
    return success(
        payload,
        proposal_meta(project_id, proposal_version=version, source_layer=layer),
    )


@router.patch("/chapters/8.4/maintenance-sla/hardware-support")
def patch_maintenance_sla_hardware_support(
    project_id: str,
    body: PatchMaintenanceSlaHardwareSupportBody,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    data, activity = sla_svc.patch_hardware_support(
        project_id, body, version=version
    )
    return success(
        data,
        proposal_meta(
            project_id,
            proposal_version=version,
            manifest_activity=activity,
        ),
    )


@router.patch("/chapters/8.4/maintenance-sla/{row_id}")
def patch_maintenance_sla(
    project_id: str,
    row_id: str,
    body: PatchMaintenanceSlaBody,
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    row, activity = sla_svc.patch_row(project_id, row_id, body, version=version)
    return success(
        row.model_dump(by_alias=True, mode="json"),
        proposal_meta(
            project_id,
            proposal_version=version,
            manifest_activity=activity,
        ),
    )


@router.post("/parse/maintenance-proposal-doc")
def parse_maintenance_proposal_doc(
    project_id: str,
    force: bool = Query(default=False),
    version: str = Query(default="draft"),
    _session: ProposalSession = Depends(require_proposal_write),
):
    data, dependencies = sla_svc.parse_maintenance_proposal_doc(
        project_id, force=force, version=version
    )
    raw_rows = load_chapter_84(project_id, version).get("rows") or []
    return success(
        {
            "hardwareSupport": data["hardwareSupport"],
            "serviceLevel": data["serviceLevel"],
            "rows": sla_svc.serialize_sla_rows(raw_rows, data["rows"]),
        },
        proposal_meta(
            project_id,
            proposal_version=version,
            dependencies=dependencies,
        ),
    )


@router.post("/release-and-decide")
def release_and_decide(
    project_id: str,
    body: ReleaseAndDecideBody | None = None,
    session: ProposalSession = Depends(require_proposal_release),
):
    try:
        data = release_service.release_and_decide(project_id, body, session)
    except ValueError as exc:
        raise ProposalApiError(422, "BR_PROPOSAL_INCOMPLETE", str(exc)) from exc
    return success(
        data,
        proposal_meta(
            project_id,
            proposal_version=data["proposalVersion"],
            source_layer="output",
        ),
    )


@router.post("/release")
def release_proposal(
    project_id: str,
    body: ReleaseBody | None = None,
    session: ProposalSession = Depends(require_proposal_release),
):
    decide_body = ReleaseAndDecideBody(
        changeDescription=body.change_description if body else None,
    )
    try:
        data = release_service.release_and_decide(project_id, decide_body, session)
    except ValueError as exc:
        raise ProposalApiError(422, "BR_PROPOSAL_INCOMPLETE", str(exc)) from exc
    return success(
        {"chapters": data.get("chapters", {})},
        proposal_meta(
            project_id,
            proposal_version=data["proposalVersion"],
            source_layer="output",
        ),
    )
