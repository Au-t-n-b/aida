"""FastAPI dependency: bind proposal request to datacenter ContextVar."""
from __future__ import annotations

from typing import AsyncIterator

from fastapi import Request

from agent.proposal.dc_store import reset_dc_context, set_dc_context
from agent.services.proposal_chapter_files import extract_token


async def bind_proposal_dc(project_id: str, request: Request) -> AsyncIterator[None]:
    token = extract_token(request.headers.get("Authorization"))
    tokens = set_dc_context(project_id, token)
    try:
        yield
    finally:
        reset_dc_context(tokens)
