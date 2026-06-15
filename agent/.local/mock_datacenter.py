"""
本地 Mock 数据中心（仅开发 · 勿提交 git）

启动：
    cd aida
    .\\agent\\.venv\\Scripts\\activate
    python agent/.local/mock_datacenter.py

默认账号：liwen / 123456
Manager 需在 agent/.env 中设置：DATA_CENTER_BASE_URL=http://127.0.0.1:9000
"""
from __future__ import annotations

import secrets
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="AIDA Mock Datacenter", version="local")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 内置账号（可运行时注册扩充）────────────────────────────────────────────

_USERS: dict[str, dict[str, Any]] = {
    "liwen": {
        "password": "123456",
        "userId": 2,
        "displayName": "李伟",
        "email": "liwen@local.dev",
        "status": 1,
        "globalRoles": [{"roleCode": "TD", "roleName": "技术负责人"}],
        "permissions": ["project:list", "project:read", "skill:list", "skill:read"],
        "isAdmin": False,
    },
}

_TOKENS: dict[str, str] = {}

_MOCK_PROJECTS: list[dict[str, Any]] = [
    {
        "id": 1,
        "projectId": "1b9bb4a0d0ce4863925e787bc057ecaf",
        "projectName": "京东三期",
        "projectCode": "K1903",
        "bidCode": "PROP-2026-K1903",
        "customerName": "京东",
        "status": "APPROVED",
        "stage": "install",
        "progress": 45,
        "risk": "medium",
        "description": "本地 Mock 演示项目",
        "updatedAt": "2026-06-12T16:00:00",
        "pdName": "pd_user",
        "tdName": "liwen",
        "pcmName": "pcm_user",
        "myRoles": [{"roleCode": "TD", "roleName": "技术负责人"}],
        "canEnter": True,
        "disabledReason": None,
    },
    {
        "id": 2,
        "projectId": "a1b2c3d4e5f6478990abcdef12345678",
        "projectName": "A1 智算集群一期",
        "projectCode": "A1",
        "bidCode": "PROP-2026-A1-002",
        "customerName": "演示客户",
        "status": "PENDING_APPROVAL",
        "stage": "modeling",
        "progress": 20,
        "risk": "low",
        "updatedAt": "2026-06-11T10:00:00",
        "myRoles": [{"roleCode": "PCM", "roleName": "项目控制经理"}],
        "canEnter": False,
        "disabledReason": "待审批，暂不可进入",
    },
]


def _ok(data: Any) -> dict[str, Any]:
    return {"code": 0, "message": "success", "data": data}


def _fail(code: int, message: str) -> dict[str, Any]:
    return {"code": code, "message": message, "data": None}


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization")
    token = authorization[7:].strip()
    if token not in _TOKENS:
        raise HTTPException(status_code=401, detail="token 无效")
    return token


def _issue_token(username: str) -> str:
    token = f"mock-{username}-{secrets.token_hex(12)}"
    _TOKENS[token] = username
    return token


def _user_public(username: str) -> dict[str, Any]:
    u = _USERS[username]
    return {
        "userId": u["userId"],
        "username": username,
        "displayName": u["displayName"],
        "email": u.get("email"),
        "status": u.get("status", 1),
        "globalRoles": u.get("globalRoles", []),
        "permissions": u.get("permissions", []),
        "isAdmin": u.get("isAdmin", False),
    }


class LoginBody(BaseModel):
    username: str
    password: str


class RegisterBody(BaseModel):
    username: str
    password: str = Field(min_length=6)
    email: str | None = None


@app.get("/health")
@app.get("/healthz")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "mock-datacenter", "users": list(_USERS.keys())}


@app.post("/api/v1/auth/login")
async def claw_login(body: LoginBody) -> dict[str, Any]:
    user = _USERS.get(body.username.strip())
    if not user or user["password"] != body.password:
        return JSONResponse(status_code=400, content=_fail(1002, "invalid username or password"))
    username = body.username.strip()
    token = _issue_token(username)
    pub = _user_public(username)
    return _ok(
        {
            "accessToken": token,
            "tokenType": "Bearer",
            "user": {
                "userId": str(pub["userId"]),
                "username": pub["username"],
                "displayName": pub["displayName"],
                "email": pub["email"],
                "status": pub["status"],
                "globalRoles": pub["globalRoles"],
                "permissions": pub["permissions"],
            },
        }
    )


@app.post("/api/v1/users/login")
async def users_login(body: LoginBody) -> dict[str, Any]:
    user = _USERS.get(body.username.strip())
    if not user or user["password"] != body.password:
        return JSONResponse(status_code=400, content=_fail(1002, "账号或密码错误"))
    username = body.username.strip()
    token = _issue_token(username)
    return _ok(
        {
            "token": token,
            "expiresIn": 3600,
            "userId": user["userId"],
        }
    )


@app.post("/api/v1/users/register")
async def users_register(body: RegisterBody) -> dict[str, Any]:
    name = body.username.strip()
    if name in _USERS:
        return JSONResponse(status_code=400, content=_fail(1001, "用户名已存在"))
    uid = max((u["userId"] for u in _USERS.values()), default=0) + 1
    _USERS[name] = {
        "password": body.password,
        "userId": uid,
        "displayName": name,
        "email": body.email or f"{name}@local.dev",
        "status": 1,
        "globalRoles": [{"roleCode": "TD", "roleName": "技术负责人"}],
        "permissions": ["project:list", "project:read"],
        "isAdmin": False,
    }
    return _ok({"userId": uid, "username": name})


@app.get("/api/v1/users/me")
async def users_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = _bearer(authorization)
    username = _TOKENS[token]
    pub = _user_public(username)
    return _ok(
        {
            "userId": pub["userId"],
            "username": pub["username"],
            "email": pub["email"],
            "isAdmin": pub["isAdmin"],
            "globalRoles": pub["globalRoles"],
            "projectRoles": [],
            "permissions": pub["permissions"],
        }
    )


@app.get("/api/v1/projects/my")
async def projects_my(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _bearer(authorization)
    return _ok({"list": _MOCK_PROJECTS, "total": len(_MOCK_PROJECTS)})


@app.post("/api/v1/projects")
async def projects_create(
    body: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _bearer(authorization)
    project_name = (body.get("projectName") or "").strip()
    contract_type = (body.get("contractType") or "").strip()
    if not project_name:
        raise HTTPException(status_code=400, detail="projectName 必填")
    if contract_type not in ("预销售合同", "标准合同"):
        raise HTTPException(status_code=400, detail="contractType 必填，且须为预销售合同或标准合同")
    pid = uuid.uuid4().hex
    item = {
        "id": len(_MOCK_PROJECTS) + 1,
        "projectId": pid,
        "projectName": project_name,
        "projectCode": body.get("projectCode"),
        "bidCode": body.get("bidCode"),
        "contractType": contract_type,
        "status": "PENDING_APPROVAL",
        "progress": 0,
        "risk": "low",
        "myRoles": [{"roleCode": "TD", "roleName": "技术负责人"}],
        "canEnter": False,
        "disabledReason": "待审批",
    }
    _MOCK_PROJECTS.append(item)
    return _ok(item)


if __name__ == "__main__":
    print("Mock 数据中心 → http://127.0.0.1:9000")
    print("默认账号：liwen / 123456")
    uvicorn.run(app, host="127.0.0.1", port=9000, log_level="info")
