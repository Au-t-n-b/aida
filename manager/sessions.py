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
