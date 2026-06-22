"""数据中心 · 通用文件代理（透传 Bearer token）。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

# 确保 aida 根在 sys.path，以便 import shared.*
_AIDA_ROOT = Path(__file__).resolve().parents[2]
if str(_AIDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AIDA_ROOT))

from shared.datacenter import DataCenterClient, DataCenterError, SemanticFileRef

router = APIRouter(prefix="/api/v1/datacenter", tags=["datacenter"])


def _ok(data: Any, *, source: str = "datacenter", warnings: list[str] | None = None) -> dict:
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "meta": {"source": source, "warnings": warnings or []},
    }


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return authorization.strip() or None


class FileRefBody(BaseModel):
    projectId: str | None = None
    moduleCode: str
    fileStage: str | None = None
    folderSubPath: str | None = None
    fileName: str | None = None
    fileKeyword: str | None = None


def _to_ref(body: FileRefBody) -> SemanticFileRef:
    return SemanticFileRef(
        module_code=body.moduleCode,
        file_stage=body.fileStage,
        folder_sub_path=body.folderSubPath,
        file_name=body.fileName,
        project_id=body.projectId,
        file_keyword=body.fileKeyword,
    )


@router.post("/files/list")
async def list_files(body: FileRefBody, authorization: str | None = Header(default=None)):
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(401, "需要 Authorization: Bearer <token>")
    try:
        client = DataCenterClient(token)
        data = await client.list_files(_to_ref(body))
        return _ok(data)
    except DataCenterError as e:
        raise HTTPException(e.status_code, e.args[0]) from e


class DownloadBody(BaseModel):
    ref: FileRefBody
    projectName: str = ""
    projectCode: str | None = None


@router.post("/files/download")
async def download_file_meta(body: DownloadBody, authorization: str | None = Header(default=None)):
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(401, "需要 Authorization: Bearer <token>")
    ref = _to_ref(body.ref)
    if not ref.file_name:
        raise HTTPException(400, "download 需要 fileName")
    try:
        client = DataCenterClient(token)
        content = await client.download_file(ref)
        import base64

        payload: dict[str, Any] = {
            "fileName": ref.file_name,
            "sizeBytes": len(content),
            "contentBase64": base64.b64encode(content).decode("ascii"),
        }
        return _ok(payload)
    except DataCenterError as e:
        raise HTTPException(e.status_code, e.args[0]) from e
