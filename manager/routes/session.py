"""Claw 会话：进入项目 / 心跳。"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from manager.config import aida_agent_base, claw_orchestration_enabled, container_endpoint_url
from manager.orchestrator import (
    endpoint_for_session,
    ensure_claw,
    is_claw_ready,
    touch_session_heartbeat,
)
from manager.session_resolve import resolve_manager_session
from manager.sessions import update_session_project

router = APIRouter(prefix="/api/v1/session", tags=["session"])
logger = logging.getLogger("aida.manager.session")


class EnterProjectRequest(BaseModel):
    session_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1, max_length=128)
    project_code: str = Field(default="", max_length=64)


class EnterProjectResponse(BaseModel):
    container_endpoint: str
    routing_key: str
    reused: bool
    host_port: int | None = None
    container_ready: bool = False


class HeartbeatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    project_id: str = Field(default="", max_length=128)
    project_code: str = Field(default="", max_length=64)


class HeartbeatResponse(BaseModel):
    ok: bool
    container_endpoint: str | None = None
    container_ready: bool = False


@router.post("/enter-project", response_model=EnterProjectResponse)
async def enter_project(
    body: EnterProjectRequest,
    authorization: str | None = Header(default=None),
) -> EnterProjectResponse:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization")
    token = authorization[7:].strip()
    sess = await resolve_manager_session(body.session_id, token)

    project_id = body.project_id.strip()
    project_code = (body.project_code or project_id).strip()
    update_session_project(sess.session_id, project_id=project_id, project_code=project_code)

    if not claw_orchestration_enabled():
        fallback = aida_agent_base()
        return EnterProjectResponse(
            container_endpoint=fallback,
            routing_key="",
            reused=False,
            host_port=None,
        )

    try:
        alloc, reused = await asyncio.to_thread(
            ensure_claw,
            session_id=sess.session_id,
            user_id=sess.user_id,
            project_id=project_id,
            project_code=project_code,
            username=sess.username,
            wait_ready=False,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.exception("enter-project ensure_claw failed user=%s project=%s", sess.user_id, project_id)
        raise HTTPException(status_code=503, detail=f"Claw 容器启动失败: {e}") from e

    endpoint = container_endpoint_url(alloc.routing_key, alloc.host_port)
    ready = is_claw_ready(alloc.host_port) if alloc.host_port else False
    logger.info(
        "enter-project user=%s project=%s endpoint=%s reused=%s ready=%s",
        sess.user_id,
        project_id,
        endpoint,
        reused,
        ready,
    )
    return EnterProjectResponse(
        container_endpoint=endpoint,
        routing_key=alloc.routing_key,
        reused=reused,
        host_port=alloc.host_port,
        container_ready=ready,
    )


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def session_heartbeat(
    body: HeartbeatRequest,
    authorization: str | None = Header(default=None),
) -> HeartbeatResponse:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization")
    token = authorization[7:].strip()
    sess = await resolve_manager_session(body.session_id, token)

    project_id = body.project_id.strip()
    project_code = (body.project_code or project_id or sess.project_code).strip()
    if project_id:
        update_session_project(sess.session_id, project_id=project_id, project_code=project_code)

    ok = True
    endpoint = aida_agent_base()
    ready = False
    if claw_orchestration_enabled():
        ok = touch_session_heartbeat(
            body.session_id,
            user_id=sess.user_id,
            project_id=project_id or sess.project_id,
            project_code=project_code or sess.project_code,
            username=sess.username,
        )
        endpoint = endpoint_for_session(body.session_id) or aida_agent_base()
        from manager.orchestrator import registry

        alloc = registry().get_by_session(body.session_id)
        if alloc and alloc.host_port:
            ready = is_claw_ready(alloc.host_port)
    return HeartbeatResponse(ok=ok, container_endpoint=endpoint, container_ready=ready)
