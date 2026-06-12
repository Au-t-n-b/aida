"""数据中心 API 客户端（鉴权等）。"""
from __future__ import annotations

from typing import Any

import httpx

from manager.config import datacenter_base, http_proxy, ssl_verify

_DC_ERRORS = {
    1001: "用户名已存在",
    1002: "用户名或密码错误",
    1003: "账号已禁用",
    1004: "用户不存在",
    1005: "不能删除自己的账号",
}


class DataCenterError(Exception):
    def __init__(self, code: int, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _client() -> httpx.AsyncClient:
    proxy = http_proxy()
    return httpx.AsyncClient(
        base_url=datacenter_base(),
        timeout=httpx.Timeout(30.0, connect=10.0),
        proxy=proxy,
        verify=ssl_verify(),
        trust_env=proxy is None,
    )


def _unwrap(payload: dict[str, Any]) -> Any:
    if "code" in payload and "data" in payload:
        code = int(payload.get("code", -1))
        if code != 0:
            msg = str(payload.get("message") or _DC_ERRORS.get(code) or "数据中心错误")
            status = 401 if code in (1002, 1003) else 400
            raise DataCenterError(code, msg, status_code=status)
        return payload.get("data")
    return payload


async def login(username: str, password: str) -> dict[str, Any]:
    async with _client() as client:
        resp = await client.post(
            "/api/v1/users/login",
            json={"username": username, "password": password},
        )
        if resp.status_code >= 400:
            try:
                body = resp.json()
                if isinstance(body, dict) and "code" in body:
                    _unwrap(body)
            except DataCenterError:
                raise
            except Exception:
                pass
            raise DataCenterError(
                resp.status_code,
                f"数据中心登录失败: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = _unwrap(resp.json())
        if not isinstance(data, dict) or not data.get("token"):
            raise DataCenterError(500, "数据中心登录响应缺少 token", status_code=502)
        return data


async def register_user(
    username: str,
    password: str,
    *,
    email: str | None = None,
) -> dict[str, Any]:
    """自助注册：优先 users/register；与 user-mgmt 新建用户入参一致。"""
    body: dict[str, Any] = {"username": username, "password": password}
    if email:
        body["email"] = email
    async with _client() as client:
        resp = await client.post("/api/v1/users/register", json=body)
        if resp.status_code >= 400:
            try:
                payload = resp.json()
                if isinstance(payload, dict) and "code" in payload:
                    _unwrap(payload)
            except DataCenterError:
                raise
            except Exception:
                pass
            raise DataCenterError(
                resp.status_code,
                f"数据中心注册失败: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = _unwrap(resp.json())
        if not isinstance(data, dict):
            raise DataCenterError(500, "数据中心注册响应异常", status_code=502)
        return data


async def get_me(token: str) -> dict[str, Any]:
    async with _client() as client:
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 401:
            raise DataCenterError(1002, "登录已失效，请重新登录", status_code=401)
        if resp.status_code >= 400:
            raise DataCenterError(
                resp.status_code,
                f"获取用户信息失败: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = _unwrap(resp.json())
        if not isinstance(data, dict):
            raise DataCenterError(500, "数据中心 /users/me 响应异常", status_code=502)
        return data
