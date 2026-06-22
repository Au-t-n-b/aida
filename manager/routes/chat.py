"""聊天访问票据 — 登录后 ClawRail 自由聊天用。"""
from __future__ import annotations

import time

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from manager.config import aida_agent_base
from manager.orchestrator import endpoint_for_session
from manager.session_resolve import resolve_manager_session

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatAccessRequest(BaseModel):
    session_id: str = Field(min_length=1)


class ChatAccessResponse(BaseModel):
    session_id: str
    endpoint: str
    token: str
    expires_at: int
    protocol: str = "aida"
    paths: dict[str, str] = Field(default_factory=lambda: {"send": "agent/chat/stream"})


@router.post("/access", response_model=ChatAccessResponse)
async def chat_access(
    body: ChatAccessRequest,
    authorization: str | None = Header(default=None),
) -> ChatAccessResponse:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization")
    token = authorization[7:].strip()
    sess = await resolve_manager_session(body.session_id, token)

    endpoint = endpoint_for_session(sess.session_id) or aida_agent_base()

    return ChatAccessResponse(
        session_id=sess.session_id,
        endpoint=endpoint,
        token=token,
        expires_at=int(sess.expires_at),
        protocol="aida",
        paths={"send": "agent/chat/stream"},
    )
