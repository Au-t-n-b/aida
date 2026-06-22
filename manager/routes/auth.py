"""UX 鉴权 API — 代理数据中心 users/login + users/me。"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from manager.datacenter_client import (
    DataCenterError,
    claw_login,
    get_me,
    login as dc_login,
    register_user,
)
from manager.http_errors import dc_http_exception
from manager.config import aida_agent_base, claw_orchestration_enabled
from manager.orchestrator import destroy_all_for_user, destroy_for_session
from manager.session_resolve import resolve_manager_session
from manager.sessions import create_session, delete_session, get_by_token, get_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger("aida.manager.auth")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    project_code: str = Field(default="", max_length=64)


class UserProfile(BaseModel):
    user_id: str
    username: str
    display_name: str
    email: str | None = None
    status: int | None = None
    global_roles: list[dict[str, Any]] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    role: str
    session_id: str
    container_endpoint: str | None = None
    reused: bool = False
    user_id: int | None = None
    username: str | None = None
    expires_in: int | None = None
    user: UserProfile | None = None


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

from manager.profile_roles import primary_role
def _profile_from_claw_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "userId": user.get("userId"),
        "username": user.get("username"),
        "displayName": user.get("displayName") or user.get("username"),
        "email": user.get("email"),
        "status": user.get("status"),
        "globalRoles": user.get("globalRoles") or [],
        "permissions": user.get("permissions") or [],
        "isAdmin": any(
            isinstance(r, dict) and r.get("roleCode") == "ADMIN"
            for r in (user.get("globalRoles") or [])
        ),
    }


def _user_profile_model(profile: dict[str, Any]) -> UserProfile:
    return UserProfile(
        user_id=str(profile.get("userId") or ""),
        username=str(profile.get("username") or ""),
        display_name=str(profile.get("displayName") or profile.get("username") or ""),
        email=profile.get("email"),
        status=profile.get("status"),
        global_roles=list(profile.get("globalRoles") or []),
        permissions=[str(p) for p in (profile.get("permissions") or [])],
    )


async def _authenticate(username: str, password: str) -> tuple[str, dict[str, Any], int, str]:
    """返回 (token, profile, expires_in, token_type)。

    规范 §4.6 创建项目流程使用 POST /api/v1/users/login 的 data.token；
    Manager 优先签发该令牌，仅当 users/login 未上线时回退 CLaw auth/login。
    """
    try:
        dc = await dc_login(username, password)
        token = str(dc["token"])
        expires_in = int(dc.get("expiresIn") or 3600)
        profile = await get_me(token)
        return token, profile, expires_in, "Bearer"
    except DataCenterError as e:
        http_status = (e.debug or {}).get("httpStatus")
        if e.code != 404 and http_status != 404:
            raise

    claw = await claw_login(username, password)
    token = str(claw["accessToken"])
    user = claw.get("user") if isinstance(claw.get("user"), dict) else {}
    profile = _profile_from_claw_user(user)
    return token, profile, 3600, str(claw.get("tokenType") or "Bearer")


@router.post("/login", response_model=LoginResponse)
async def auth_login(body: LoginRequest) -> LoginResponse:
    username = body.username.strip()
    project_code = body.project_code.strip()
    try:
        token, profile, expires_in, token_type = await _authenticate(username, body.password)
    except DataCenterError as e:
        logger.warning(
            "login rejected username=%s code=%s reason=%s",
            username,
            e.code,
            e,
        )
        raise dc_http_exception(e) from e

    user_id = int(profile.get("userId") or 0)
    role = primary_role(profile)
    sess = create_session(
        access_token=token,
        user_id=user_id,
        username=str(profile.get("username") or body.username),
        role=role,
        project_code=project_code,
        expires_in=expires_in,
        profile=profile,
    )
    logger.info(
        "login ok username=%s user_id=%s role=%s session=%s",
        sess.username,
        sess.user_id,
        role,
        sess.session_id,
    )
    return LoginResponse(
        access_token=token,
        token_type=token_type,
        role=role,
        session_id=sess.session_id,
        container_endpoint=None,
        reused=False,
        user_id=sess.user_id,
        username=sess.username,
        expires_in=expires_in,
        user=_user_profile_model(profile),
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
        raise dc_http_exception(e) from e

    user_id = int(data.get("userId") or data.get("user_id") or 0)
    registered_name = str(data.get("username") or username)
    logger.info("register ok username=%s user_id=%s", registered_name, user_id)
    return RegisterResponse(user_id=user_id, username=registered_name)


@router.post("/logout")
async def auth_logout(
    body: LogoutRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = 0
    username = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        try:
            sess = await resolve_manager_session(body.session_id, token)
            user_id = sess.user_id
            username = sess.username
        except HTTPException:
            raise
        except Exception:
            sess = get_session(body.session_id)
            if sess and sess.access_token != token:
                raise HTTPException(status_code=403, detail="session 与 token 不匹配")
            if sess:
                user_id = sess.user_id
                username = sess.username
    else:
        sess = get_session(body.session_id)
        if sess:
            user_id = sess.user_id
            username = sess.username

    containers_destroyed = 0
    if claw_orchestration_enabled() and user_id > 0:
        destroy_for_session(body.session_id)
        containers_destroyed = destroy_all_for_user(user_id, username)
        logger.info(
            "logout user_id=%s session=%s containers_destroyed=%s",
            user_id,
            body.session_id[:16],
            containers_destroyed,
        )

    deleted = delete_session(body.session_id)
    return {
        "session_id": body.session_id,
        "archived": False,
        "destroyed": deleted,
        "container_destroyed": containers_destroyed > 0,
        "containers_destroyed": containers_destroyed,
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
            raise dc_http_exception(e) from e
        project_code = ""
        role = primary_role(profile)
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
