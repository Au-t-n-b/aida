"""交付预案 · 数据中心表格读写与解析（第 9–12 章）。"""
from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

_AIDA_ROOT = Path(__file__).resolve().parents[2]
if str(_AIDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AIDA_ROOT))

from ..services.proposal_dc_files import (
    load_testcases_template_bytes,
    read_table_slot,
    sync_proposal_slots,
    write_table_slot,
)
from ..services.proposal_parse import parse_acceptance_from_docx
from ..proposal_request_logging import ProposalLoggingRoute

router = APIRouter(prefix="/api/v1/proposal", tags=["proposal-files"], route_class=ProposalLoggingRoute)
LOG = logging.getLogger("aida.proposal.files")

READ_SLOTS = frozenset({
    "raci_template", "raci_out", "plan", "acceptance_out",
    "acceptance_input", "testcases_template", "testcases_out", "card_scale",
})
WRITE_SLOTS = frozenset({"raci_out", "acceptance_out", "testcases_out"})


def _ok(data: Any, *, source: str, warnings: list[str], logical_path: str = "") -> dict:
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "meta": {
            "source": source,
            "logicalPath": logical_path or data.get("path", ""),
            "warnings": warnings,
        },
    }


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return authorization.strip() or None


class ReadTableBody(BaseModel):
    slot: str
    projectId: str
    projectName: str = ""
    projectCode: str | None = None


class SyncBody(BaseModel):
    projectId: str
    projectName: str = ""
    projectCode: str | None = None
    slots: list[str] | None = None


@router.post("/sync")
async def sync_local_files(body: SyncBody, authorization: str | None = Header(default=None)):
    """进入交付预案时：检查本地 mock 目录，缺失则从数据中心下载到固定路径。"""
    token = _extract_token(authorization)
    slots = body.slots or sorted(READ_SLOTS)
    unknown = [s for s in slots if s not in READ_SLOTS]
    if unknown:
        raise HTTPException(400, f"unsupported slot: {unknown[0]}")
    LOG.info(
        "POST /sync projectId=%s projectName=%s slots=%s hasToken=%s",
        body.projectId,
        body.projectName,
        len(slots),
        bool(token),
    )
    results, warnings = await sync_proposal_slots(
        token, body.projectId, body.projectName, body.projectCode, slots,
    )
    ready = sum(1 for r in results.values() if r.get("status") in ("local", "downloaded"))
    LOG.info("POST /sync ok ready=%s/%s warnings=%s", ready, len(slots), len(warnings))
    return _ok(
        {"slots": results, "ready": ready, "total": len(slots)},
        source="sync",
        warnings=warnings,
    )


@router.post("/tables/read")
async def read_table(body: ReadTableBody, authorization: str | None = Header(default=None)):
    if body.slot not in READ_SLOTS:
        raise HTTPException(400, f"unsupported slot: {body.slot}")
    token = _extract_token(authorization)
    LOG.info(
        "POST /tables/read slot=%s projectId=%s projectName=%s hasToken=%s",
        body.slot,
        body.projectId,
        body.projectName,
        bool(token),
    )
    try:
        data, source, warnings = await read_table_slot(
            token, body.slot, body.projectId, body.projectName, body.projectCode,
        )
        row_count = len(data.get("rows") or [])
        LOG.info(
            "POST /tables/read ok slot=%s source=%s rows=%s path=%s warnings=%s",
            body.slot,
            source,
            row_count,
            data.get("path"),
            warnings,
        )
        return _ok(data, source=source, warnings=warnings, logical_path=data.get("path", ""))
    except FileNotFoundError as e:
        LOG.warning("POST /tables/read 404 slot=%s: %s", body.slot, e)
        raise HTTPException(404, str(e)) from e


class WriteTableBody(BaseModel):
    slot: str
    projectId: str
    projectName: str
    projectCode: str | None = None
    kind: str = Field(..., description="raci | acceptance | testcases")
    version: int = 1
    rows: list[dict[str, Any]]


@router.post("/tables/write")
async def write_table(body: WriteTableBody, authorization: str | None = Header(default=None)):
    if body.slot not in WRITE_SLOTS:
        raise HTTPException(400, f"unsupported slot: {body.slot}")
    token = _extract_token(authorization)
    LOG.info(
        "POST /tables/write slot=%s projectId=%s kind=%s version=%s rows=%s hasToken=%s",
        body.slot,
        body.projectId,
        body.kind,
        body.version,
        len(body.rows),
        bool(token),
    )
    try:
        data, source, warnings = await write_table_slot(
            token,
            body.slot,
            body.projectId,
            body.projectName,
            body.projectCode,
            body.kind,
            body.rows,
            body.version,
        )
        LOG.info(
            "POST /tables/write ok slot=%s source=%s path=%s warnings=%s",
            body.slot,
            source,
            data.get("path"),
            warnings,
        )
        return _ok(data, source=source, warnings=warnings, logical_path=data.get("path", ""))
    except ValueError as e:
        LOG.warning("POST /tables/write 400 slot=%s: %s", body.slot, e)
        raise HTTPException(400, str(e)) from e


@router.post("/parse/tech-proposal")
async def parse_tech_proposal(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".docx", ".pdf"):
        raise HTTPException(400, "仅支持 .docx / .pdf")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        if suffix == ".docx":
            try:
                from ..services.officecli_parse import parse_acceptance_via_officecli
                rows = parse_acceptance_via_officecli(tmp_path)
            except Exception:
                rows = parse_acceptance_from_docx(tmp_path)
        else:
            rows = []
        return {"code": 0, "message": "success", "data": {"rows": rows, "source": file.filename, "engine": "officecli"}}
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/parse/testcases")
async def parse_testcases_upload(
    file: UploadFile = File(...),
    projectId: str = Form(...),
    projectName: str = Form(""),
    projectCode: str | None = Form(None),
    authorization: str | None = Header(default=None),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".docx", ".pdf", ".xlsx", ".xlsm"):
        raise HTTPException(400, "仅支持 .docx / .pdf / .xlsx")
    if not projectId:
        raise HTTPException(400, "projectId 必填")

    token = _extract_token(authorization)
    xlsx_path, tpl_source, tpl_warnings = await load_testcases_template_bytes(
        token, projectId, projectName, projectCode,
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        upload_path = Path(tmp.name)

    try:
        from ..services.officecli_parse import merge_testcases_with_upload

        rows, source = merge_testcases_with_upload(xlsx_path, upload_path)
        source["upload"] = file.filename
        source["templateSource"] = tpl_source
        return {
            "code": 0,
            "message": "success",
            "data": {"rows": rows, "source": source, "engine": source.get("engine", "officecli")},
            "meta": {"source": tpl_source, "warnings": tpl_warnings},
        }
    finally:
        upload_path.unlink(missing_ok=True)
