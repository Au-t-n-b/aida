"""建模仿真 HTTP API 客户端（新 wapi 网关）。

新网关（9091）使用 **Bearer Token** 鉴权：
  - 请求头 ``Authorization: Bearer <token>``；
  - token 由 ``createProject`` 接口签发，已创建项目可直接复用。
端点为完整路径 ``/wapi/v1/ai/...``，请求体不再携带 username/password。
"""

from __future__ import annotations

import os
from typing import Any, Mapping

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]


def resolve_token(auth_spec: Mapping[str, Any] | None) -> str:
    """从 config.auth 解析 Bearer Token：优先 ``token``，否则读 ``token_env`` 环境变量。"""
    if not auth_spec:
        return ""
    token = str(auth_spec.get("token") or "").strip()
    if not token:
        token_env = str(auth_spec.get("token_env") or "").strip()
        if token_env:
            token = os.environ.get(token_env, "").strip()
    return token


def build_headers(token: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def normalize_base_url(base_url: str) -> str:
    """归一化基址：默认 9091 新网关，去掉尾部 ``/``。"""
    prefix = (base_url or "").strip()
    if not prefix:
        prefix = "http://100.102.191.17:9091"
    return prefix.rstrip("/")


def is_ok(status: int, body: Any, *, extra_ok_codes: set[int] | None = None) -> bool:
    """成功判定：HTTP 2xx 且 body.code 缺省或为 200（或在 extra_ok_codes 内）。"""
    if not (200 <= status < 300):
        return False
    if isinstance(body, dict):
        code = body.get("code")
        if code in (None, 200, "200"):
            return True
        if extra_ok_codes and code in extra_ok_codes:
            return True
        return False
    return True


def extract_data(body: Any) -> Any:
    """从响应体提取 ``data`` 字段；非标准结构时原样返回。"""
    if isinstance(body, dict) and "data" in body:
        return body.get("data")
    return body


def post_sim_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    token: str = "",
    timeout: int = 60,
) -> tuple[int, Any]:
    """POST JSON（Bearer 鉴权），返回 (http_status, body)。网络异常返回 (0, {"error": ...})。"""
    if requests is None:
        return 0, {"error": "requests not installed; run pip install -r requirements.txt"}
    try:
        resp = requests.post(
            url,
            json=dict(payload),
            headers=build_headers(token),
            timeout=timeout,
        )
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, {"raw_text": resp.text}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def get_sim_json(
    url: str,
    *,
    token: str = "",
    timeout: int = 60,
) -> tuple[int, Any]:
    """GET（Bearer 鉴权），返回 (http_status, body)。网络异常返回 (0, {"error": ...})。"""
    if requests is None:
        return 0, {"error": "requests not installed; run pip install -r requirements.txt"}
    try:
        resp = requests.get(
            url,
            headers=build_headers(token),
            timeout=timeout,
        )
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, {"raw_text": resp.text}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}
