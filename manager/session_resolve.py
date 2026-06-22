"""Manager 会话解析：内存命中 → token 命中 → DC token 重建。"""
from __future__ import annotations

from fastapi import HTTPException

from manager.datacenter_client import DataCenterError, get_me
from manager.http_errors import dc_http_exception
from manager.profile_roles import primary_role
from manager.sessions import ManagerSession, get_by_token, get_session, rehydrate_session


async def resolve_manager_session(session_id: str, token: str) -> ManagerSession:
    """解析 Manager 会话；Manager 重启后内存丢失时，用 DC Bearer token 自动重建。"""
    sess = get_session(session_id)
    if sess and sess.access_token == token:
        return sess

    by_token = get_by_token(token)
    if by_token:
        return by_token

    try:
        profile = await get_me(token)
    except DataCenterError as e:
        raise dc_http_exception(e) from e

    user_id = int(profile.get("userId") or 0)
    username = str(profile.get("username") or "")
    if not user_id and not username:
        raise HTTPException(status_code=401, detail="会话无效或已过期")

    return rehydrate_session(
        session_id=session_id,
        access_token=token,
        user_id=user_id,
        username=username,
        role=primary_role(profile),
        profile=profile,
    )
