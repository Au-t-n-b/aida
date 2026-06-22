"""Manager 会话存储（进程内；后续可换 Redis）。"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ManagerSession:
    session_id: str
    access_token: str
    user_id: int
    username: str
    role: str
    project_code: str
    expires_at: float
    profile: dict[str, Any] = field(default_factory=dict)
    project_id: str = ""


_STORE: dict[str, ManagerSession] = {}


def create_session(
    *,
    access_token: str,
    user_id: int,
    username: str,
    role: str,
    project_code: str,
    expires_in: int,
    profile: dict[str, Any],
) -> ManagerSession:
    session_id = f"sess-{uuid.uuid4().hex}"
    sess = ManagerSession(
        session_id=session_id,
        access_token=access_token,
        user_id=user_id,
        username=username,
        role=role,
        project_code=project_code,
        expires_at=time.time() + max(expires_in, 60),
        profile=profile,
    )
    _STORE[session_id] = sess
    return sess


def get_session(session_id: str) -> ManagerSession | None:
    sess = _STORE.get(session_id)
    if not sess:
        return None
    if sess.expires_at < time.time():
        _STORE.pop(session_id, None)
        return None
    return sess


def get_by_token(access_token: str) -> ManagerSession | None:
    for sess in list(_STORE.values()):
        if sess.access_token == access_token and sess.expires_at >= time.time():
            return sess
    return None


def delete_session(session_id: str) -> bool:
    return _STORE.pop(session_id, None) is not None


def update_session_project(
    session_id: str,
    *,
    project_id: str,
    project_code: str,
) -> ManagerSession | None:
    sess = _STORE.get(session_id)
    if not sess:
        return None
    sess.project_id = project_id
    sess.project_code = project_code
    return sess


def list_active_sessions() -> list[ManagerSession]:
    """未过期的内存会话（供 Claw 生命周期判定）。"""
    now = time.time()
    return [s for s in _STORE.values() if s.expires_at >= now]


def has_active_user_project_session(
    user_id: int,
    project_id: str,
    *,
    session_id: str | None = None,
) -> bool:
    """是否存在仍有效、且绑定该 user+project 的 Manager 会话。"""
    from manager.registry import sanitize_project_id

    pid = sanitize_project_id(project_id)
    for sess in list_active_sessions():
        if sess.user_id != user_id:
            continue
        if session_id and sess.session_id == session_id:
            return True
        if sess.project_id and sanitize_project_id(sess.project_id) == pid:
            return True
    return False


def rehydrate_session(
    *,
    session_id: str,
    access_token: str,
    user_id: int,
    username: str,
    role: str,
    project_code: str = "",
    profile: dict[str, Any],
    expires_in: int = 3600,
) -> ManagerSession:
    """Manager 进程重启后，用仍有效的 DC token 按客户端 session_id 恢复内存会话。"""
    sess = ManagerSession(
        session_id=session_id,
        access_token=access_token,
        user_id=user_id,
        username=username,
        role=role,
        project_code=project_code,
        expires_at=time.time() + max(expires_in, 60),
        profile=profile,
        project_id="",
    )
    _STORE[session_id] = sess
    return sess
