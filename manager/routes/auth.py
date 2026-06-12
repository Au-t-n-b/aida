"""UX 鉴权 API — 代理数据中心 users/login + users/me。"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from manager.datacenter_client import DataCenterError, get_me, login as dc_login, register_user
from manager.sessions import create_session, delete_session, get_by_token, get_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger("aida.manager.auth")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    project_code: str = Field(default="K1903", min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    role: str
    session_id: str
    container_endpoint: str | None = None
    reused: bool = False
    user_id: int | None = None
    username: str | None = None
    expires_in: int | None = None


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=6)
    email: str | None = None


class RegisterResponse(BaseModel):
    user_id: int
    username: str
    message: str = "注册成功，请使用新账号登录"


class LogoutRequest(BaseModel):
    session_id: str


class MeResponse(BaseModel):
    user_id: int
    username: str
    role: str
    project_code: str
    is_admin: bool = False
    permissions: list[str] = Field(default_factory=list)
    global_roles: list[dict[str, Any]] = Field(default_factory=list)
    project_roles: list[dict[str, Any]] = Field(default_factory=list)


def _primary_role(profile: dict[str, Any]) -> str:
    if profile.get("isAdmin"):
        return "admin"
    global_roles = profile.get("globalRoles") or []
    if global_roles:
        first = global_roles[0]
        if isinstance(first, dict) and first.get("roleCode"):
            return str(first["roleCode"])
    project_roles = profile.get("projectRoles") or []
    if project_roles:
        first = project_roles[0]
        if isinstance(first, dict) and first.get("roleCode"):
            return str(first["roleCode"])
    return "user"


def _has_project_access(profile: dict[str, Any], project_code: str) -> bool:
    if profile.get("isAdmin"):
        return True
    for item in profile.get("projectRoles") or []:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("projectId") or item.get("projectCode") or "")
        if pid and project_code and pid == project_code:
            return True
    # 数据中心若尚未挂项目角色，登录阶段不阻断（由后续项目列表接口收敛）
    return not (profile.get("projectRoles") or [])


@router.post("/login", response_model=LoginResponse)
async def auth_login(body: LoginRequest) -> LoginResponse:
    username = body.username.strip()
    project_code = body.project_code.strip()
    try:
        dc = await dc_login(username, body.password)
    except DataCenterError as e:
        logger.warning(
            "login rejected username=%s project=%s code=%s reason=%s",
            username,
            project_code,
            e.code,
            e,
        )
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    token = str(dc["token"])
    expires_in = int(dc.get("expiresIn") or 3600)
    user_id = int(dc.get("userId") or 0)

    try:
        profile = await get_me(token)
    except DataCenterError as e:
        logger.warning(
            "login profile failed username=%s user_id=%s code=%s reason=%s",
            username,
            user_id,
            e.code,
            e,
        )
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    if not _has_project_access(profile, project_code):
        logger.warning(
            "login forbidden username=%s user_id=%s project=%s reason=no_project_access",
            username,
            profile.get("userId") or user_id,
            project_code,
        )
        raise HTTPException(status_code=403, detail=f"无权访问项目 {project_code}")

    role = _primary_role(profile)
    sess = create_session(
        access_token=token,
        user_id=int(profile.get("userId") or user_id),
        username=str(profile.get("username") or body.username),
        role=role,
        project_code=body.project_code.strip(),
        expires_in=expires_in,
        profile=profile,
    )
    logger.info(
        "login ok username=%s user_id=%s role=%s project=%s session=%s",
        sess.username,
        sess.user_id,
        role,
        project_code,
        sess.session_id,
    )
    return LoginResponse(
        access_token=token,
        role=role,
        session_id=sess.session_id,
        container_endpoint=None,
        reused=False,
        user_id=sess.user_id,
        username=sess.username,
        expires_in=expires_in,
    )


@router.post("/register", response_model=RegisterResponse)
async def auth_register(body: RegisterRequest) -> RegisterResponse:
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    try:
        data = await register_user(username, body.password, email=body.email)
    except DataCenterError as e:
        logger.warning(
            "register rejected username=%s code=%s reason=%s",
            username,
            e.code,
            e,
        )
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    user_id = int(data.get("userId") or data.get("user_id") or 0)
    registered_name = str(data.get("username") or username)
    logger.info("register ok username=%s user_id=%s", registered_name, user_id)
    return RegisterResponse(user_id=user_id, username=registered_name)


@router.post("/logout")
async def auth_logout(
    body: LogoutRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    sess = get_session(body.session_id)
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if sess and sess.access_token != token:
            raise HTTPException(status_code=403, detail="session 与 token 不匹配")
    deleted = delete_session(body.session_id)
    return {
        "session_id": body.session_id,
        "archived": False,
        "destroyed": deleted,
    }


@router.get("/me", response_model=MeResponse)
async def auth_me(authorization: str | None = Header(default=None)) -> MeResponse:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization")
    token = authorization[7:].strip()
    sess = get_by_token(token)
    profile: dict[str, Any]
    if sess:
        profile = sess.profile
        project_code = sess.project_code
        role = sess.role
        user_id = sess.user_id
        username = sess.username
    else:
        try:
            profile = await get_me(token)
        except DataCenterError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e
        project_code = ""
        role = _primary_role(profile)
        user_id = int(profile.get("userId") or 0)
        username = str(profile.get("username") or "")

    return MeResponse(
        user_id=user_id,
        username=username,
        role=role,
        project_code=project_code,
        is_admin=bool(profile.get("isAdmin")),
        permissions=[str(p) for p in (profile.get("permissions") or [])],
        global_roles=list(profile.get("globalRoles") or []),
        project_roles=list(profile.get("projectRoles") or []),
    )
