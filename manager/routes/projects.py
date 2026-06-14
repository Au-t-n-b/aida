"""项目 API — 代理数据中心 CLaw 接口。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from manager.datacenter_client import (
    DataCenterError,
    create_project,
    get_project,
    list_my_projects,
    update_project,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="缺少 access token")
    return token


class CreateProjectBody(BaseModel):
    projectName: str = Field(min_length=1)
    projectCode: str | None = None
    bidCode: str | None = None
    customerName: str | None = None
    tdUserId: int | None = None
    pdUserId: int | None = None
    pcmUserId: int | None = None


class UpdateProjectBody(BaseModel):
    projectName: str | None = None
    tdUsername: str | None = None
    pdUsername: str | None = None
    pcmUsername: str | None = None
    stage: str | None = None
    progress: int | None = None
    risk: str | None = None
    description: str | None = None
    deliveryTraits: list[Any] | None = None


@router.post("")
async def create_project_endpoint(
    body: CreateProjectBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """代理数据中心新建项目 POST /api/v1/projects。"""
    token = _bearer_token(authorization)
    payload = body.model_dump(exclude_none=True)
    try:
        data = await create_project(token, payload)
    except DataCenterError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    return {"code": 0, "message": "success", "data": data}


@router.get("/my")
async def my_projects(
    authorization: str | None = Header(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200, alias="pageSize"),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> dict[str, Any]:
    """代理数据中心「当前用户参与的项目列表」。"""
    token = _bearer_token(authorization)
    try:
        data = await list_my_projects(
            token,
            page=page,
            page_size=page_size,
            status=status,
            keyword=keyword,
        )
    except DataCenterError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    return {"code": 0, "message": "success", "data": data}


@router.get("/{project_id}")
async def project_detail(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """代理数据中心「项目详情」GET /api/v1/projects/{uuid}。"""
    token = _bearer_token(authorization)
    try:
        data = await get_project(token, project_id)
    except DataCenterError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    return {"code": 0, "message": "success", "data": data}


@router.put("/{project_id}")
async def update_project_endpoint(
    project_id: str,
    body: UpdateProjectBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """代理数据中心更新项目 PUT /api/v1/projects/{uuid}。"""
    token = _bearer_token(authorization)
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="请至少提供一个待更新字段")
    try:
        data = await update_project(token, project_id, payload)
    except DataCenterError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    return {"code": 0, "message": "success", "data": data}
