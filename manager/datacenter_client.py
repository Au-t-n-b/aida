"""数据中心 API 客户端（鉴权等）。"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from manager.config import datacenter_base, http_proxy, ssl_verify
from shared.datacenter.errors import DataCenterError
from shared.datacenter.logging_utils import mask_token

LOG = logging.getLogger("aida.manager.dc")

_DC_ERRORS = {
    1001: "用户名已存在",
    1002: "用户名或密码错误",
    1003: "账号已禁用",
    1004: "用户不存在",
    1005: "不能删除自己的账号",
    2001: "项目状态不允许此操作",
    2002: "项目名已存在",
}


def _client() -> httpx.AsyncClient:
    proxy = http_proxy()
    # 勿 trust_env=True：Windows 系统代理会把内网地址也走网关，导致数据中心请求 504
    return httpx.AsyncClient(
        base_url=datacenter_base(),
        timeout=httpx.Timeout(30.0, connect=10.0),
        proxy=proxy,
        verify=ssl_verify(),
        trust_env=False,
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
    base = datacenter_base()
    LOG.info("Manager DC login → POST %s/api/v1/users/login user=%s", base, username)
    async with _client() as client:
        resp = await client.post(
            "/api/v1/users/login",
            json={"username": username, "password": password},
        )
        LOG.info("Manager DC login ← HTTP %s", resp.status_code)
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
        LOG.info("Manager DC login ok user=%s", username)
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
    LOG.info("Manager DC register → POST %s/api/v1/users/register user=%s", datacenter_base(), username)
    async with _client() as client:
        resp = await client.post("/api/v1/users/register", json=body)
        LOG.info("Manager DC register ← HTTP %s", resp.status_code)
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


async def claw_login(username: str, password: str) -> dict[str, Any]:
    """CLaw 专用登录：POST /api/v1/auth/login → accessToken + user 档案。"""
    LOG.info("Manager DC claw_login → POST %s/api/v1/auth/login user=%s", datacenter_base(), username)
    async with _client() as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        LOG.info("Manager DC claw_login ← HTTP %s", resp.status_code)
        if resp.status_code == 404:
            raise DataCenterError(404, "claw auth/login 未实现", status_code=404)
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
                f"数据中心 CLaw 登录失败: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = _unwrap(resp.json())
        if not isinstance(data, dict) or not data.get("accessToken"):
            raise DataCenterError(500, "CLaw 登录响应缺少 accessToken", status_code=502)
        return data


async def create_project(token: str, body: dict[str, Any]) -> dict[str, Any]:
    """新建项目：POST /api/v1/projects，初始状态 PENDING_APPROVAL。"""
    LOG.info(
        "Manager DC create_project → POST %s/api/v1/projects token=%s body=%s",
        datacenter_base(),
        mask_token(token),
        {k: body.get(k) for k in ("name", "code", "status") if k in body},
    )
    async with _client() as client:
        resp = await client.post(
            "/api/v1/projects",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        LOG.info("Manager DC create_project ← HTTP %s", resp.status_code)
        if resp.status_code == 401:
            raise DataCenterError(1002, "登录已失效，请重新登录", status_code=401)
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
                f"新建项目失败: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = _unwrap(resp.json())
        if not isinstance(data, dict):
            raise DataCenterError(500, "数据中心新建项目响应异常", status_code=502)
        LOG.info("Manager DC create_project ok id=%s", data.get("id") or data.get("projectId"))
        return data


async def list_my_projects(
    token: str,
    *,
    page: int = 1,
    page_size: int = 100,
    status: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    """当前用户参与的项目列表：GET /api/v1/projects/my。"""
    params: dict[str, Any] = {"page": page, "pageSize": page_size}
    if status:
        params["status"] = status
    if keyword:
        params["keyword"] = keyword
    LOG.info(
        "Manager DC list_my_projects → GET %s/api/v1/projects/my token=%s params=%s",
        datacenter_base(),
        mask_token(token),
        params,
    )
    async with _client() as client:
        resp = await client.get(
            "/api/v1/projects/my",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        LOG.info(
            "Manager DC list_my_projects ← HTTP %s body=%s",
            resp.status_code,
            (resp.text[:300] + "...") if len(resp.text) > 300 else resp.text,
        )
        if resp.status_code == 401:
            raise DataCenterError(1002, "登录已失效，请重新登录", status_code=401)
        if resp.status_code >= 400:
            raise DataCenterError(
                resp.status_code,
                f"获取项目列表失败: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = _unwrap(resp.json())
        if not isinstance(data, dict):
            raise DataCenterError(500, "数据中心 projects/my 响应异常", status_code=502)
        total = data.get("total")
        items = data.get("list") or data.get("items") or []
        LOG.info("Manager DC list_my_projects ok total=%s count=%s", total, len(items))
        return data


async def get_project(token: str, project_id: str) -> dict[str, Any]:
    """项目详情：GET /api/v1/projects/{uuid}。"""
    pid = (project_id or "").strip()
    if not pid:
        raise DataCenterError(400, "缺少项目 ID", status_code=400)
    LOG.info(
        "Manager DC get_project → GET %s/api/v1/projects/%s token=%s",
        datacenter_base(),
        pid,
        mask_token(token),
    )
    async with _client() as client:
        resp = await client.get(
            f"/api/v1/projects/{pid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        LOG.info("Manager DC get_project ← HTTP %s", resp.status_code)
        if resp.status_code == 401:
            raise DataCenterError(1002, "登录已失效，请重新登录", status_code=401)
        if resp.status_code == 404:
            raise DataCenterError(2001, "项目不存在", status_code=404)
        if resp.status_code >= 400:
            raise DataCenterError(
                resp.status_code,
                f"获取项目详情失败: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = _unwrap(resp.json())
        if not isinstance(data, dict):
            raise DataCenterError(500, "数据中心项目详情响应异常", status_code=502)
        LOG.info("Manager DC get_project ok projectId=%s", data.get("projectId") or pid)
        return data


async def update_project(token: str, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """更新项目：PUT /api/v1/projects/{uuid}。"""
    pid = (project_id or "").strip()
    if not pid:
        raise DataCenterError(400, "缺少项目 ID", status_code=400)
    LOG.info(
        "Manager DC update_project → PUT %s/api/v1/projects/%s token=%s body_keys=%s",
        datacenter_base(),
        pid,
        mask_token(token),
        sorted(body.keys()),
    )
    async with _client() as client:
        resp = await client.put(
            f"/api/v1/projects/{pid}",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        LOG.info("Manager DC update_project ← HTTP %s", resp.status_code)
        if resp.status_code == 401:
            raise DataCenterError(1002, "登录已失效，请重新登录", status_code=401)
        if resp.status_code == 404:
            raise DataCenterError(2001, "项目不存在", status_code=404)
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
                f"更新项目失败: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = _unwrap(resp.json())
        if not isinstance(data, dict):
            raise DataCenterError(500, "数据中心更新项目响应异常", status_code=502)
        LOG.info("Manager DC update_project ok projectId=%s", data.get("projectId") or pid)
        return data


async def get_me(token: str) -> dict[str, Any]:
    LOG.info("Manager DC get_me → GET %s/api/v1/users/me token=%s", datacenter_base(), mask_token(token))
    async with _client() as client:
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        LOG.info("Manager DC get_me ← HTTP %s", resp.status_code)
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
        LOG.info("Manager DC get_me ok user=%s", data.get("username"))
        return data
