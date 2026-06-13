"""数据中心 HTTP 客户端（files/list · download · upload）。"""
from __future__ import annotations

from typing import Any

import httpx

from shared.datacenter.config import datacenter_base, http_proxy, ssl_verify
from shared.datacenter.errors import DataCenterError
from shared.datacenter.logging_utils import LOG, mask_token
from shared.datacenter.types import SemanticFileRef

_DC_ERRORS = {
    1001: "用户名已存在",
    1002: "用户名或密码错误",
    1003: "账号已禁用",
    1004: "用户不存在",
    1005: "不能删除自己的账号",
    2001: "项目状态不允许此操作",
    2002: "项目名已存在",
    3001: "文件不存在",
    3002: "文件上传失败",
}


class DataCenterClient:
    def __init__(self, token: str | None = None) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=datacenter_base(),
            timeout=httpx.Timeout(60.0, connect=15.0),
            proxy=http_proxy(),
            verify=ssl_verify(),
            trust_env=False,
        )

    @staticmethod
    def unwrap(payload: dict[str, Any]) -> Any:
        if "code" in payload and "data" in payload:
            code = int(payload.get("code", -1))
            if code != 0:
                msg = str(payload.get("message") or _DC_ERRORS.get(code) or "数据中心错误")
                status = 401 if code in (1002, 1003) else (404 if code == 3001 else 400)
                raise DataCenterError(code, msg, status_code=status)
            return payload.get("data")
        return payload

    async def list_files(self, ref: SemanticFileRef, *, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        body = ref.to_list_body(page=page, page_size=page_size)
        base = datacenter_base()
        LOG.info(
            "DC list_files → POST %s/api/v1/files/list token=%s body=%s",
            base,
            mask_token(self._token),
            body,
        )
        async with self._client() as client:
            resp = await client.post(
                "/api/v1/files/list",
                headers=self._headers(),
                json=body,
            )
            LOG.info(
                "DC list_files ← HTTP %s body=%s",
                resp.status_code,
                (resp.text[:500] + "...") if len(resp.text) > 500 else resp.text,
            )
            if resp.status_code == 401:
                raise DataCenterError(1002, "登录已失效，请重新登录", status_code=401)
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                    if isinstance(body, dict) and "code" in body:
                        self.unwrap(body)
                except DataCenterError:
                    raise
                except Exception:
                    pass
                raise DataCenterError(
                    resp.status_code,
                    f"files/list 失败: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )
            data = self.unwrap(resp.json())
            if not isinstance(data, dict):
                raise DataCenterError(500, "files/list 响应异常", status_code=502)
            return data

    async def download_file(self, ref: SemanticFileRef) -> bytes:
        params = ref.to_download_params()
        base = datacenter_base()
        LOG.info(
            "DC download_file → GET %s/api/v1/files/download token=%s params=%s",
            base,
            mask_token(self._token),
            params,
        )
        async with self._client() as client:
            resp = await client.get(
                "/api/v1/files/download",
                headers=self._headers(),
                params=params,
            )
            LOG.info(
                "DC download_file ← HTTP %s size=%s bytes",
                resp.status_code,
                len(resp.content) if resp.status_code == 200 else 0,
            )
            if resp.status_code == 401:
                raise DataCenterError(1002, "登录已失效，请重新登录", status_code=401)
            if resp.status_code == 404:
                raise DataCenterError(3001, "文件不存在", status_code=404)
            if resp.status_code >= 400:
                raise DataCenterError(
                    resp.status_code,
                    f"files/download 失败: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )
            return resp.content

    async def upload_file(
        self,
        ref: SemanticFileRef,
        content: bytes,
        filename: str,
        *,
        file_display_name: str | None = None,
    ) -> dict[str, Any]:
        form = ref.to_upload_form()
        files = {"file": (filename, content)}
        if file_display_name:
            form["fileDisplayName"] = file_display_name
        base = datacenter_base()
        LOG.info(
            "DC upload_file → POST %s/api/v1/files/upload token=%s form=%s filename=%s size=%s",
            base,
            mask_token(self._token),
            form,
            filename,
            len(content),
        )
        async with self._client() as client:
            resp = await client.post(
                "/api/v1/files/upload",
                headers=self._headers(),
                data=form,
                files=files,
            )
            if resp.status_code == 401:
                raise DataCenterError(1002, "登录已失效，请重新登录", status_code=401)
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                    if isinstance(body, dict) and "code" in body:
                        self.unwrap(body)
                except DataCenterError:
                    raise
                except Exception:
                    pass
                raise DataCenterError(
                    resp.status_code,
                    f"files/upload 失败: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )
            data = self.unwrap(resp.json())
            if not isinstance(data, dict):
                raise DataCenterError(500, "files/upload 响应异常", status_code=502)
            LOG.info("DC upload_file ← ok logicalPath=%s", data.get("logicalPath"))
            return data

    async def resolve_first_file(
        self,
        ref: SemanticFileRef,
        *,
        extensions: tuple[str, ...] = (".xlsx", ".xlsm", ".docx", ".md", ".pdf"),
    ) -> tuple[SemanticFileRef, dict[str, Any]]:
        """列目录并返回第一个匹配文件的 ref + list 元数据。"""
        data = await self.list_files(ref)
        items = data.get("list") or []
        total = data.get("total", len(items))
        LOG.info("DC resolve_first_file total=%s items=%s", total, [i.get("fileName") for i in items[:5]])
        for item in items:
            name = str(item.get("fileName") or "")
            if ref.file_name and name != ref.file_name:
                continue
            if not ref.file_name and extensions and not any(name.lower().endswith(ext) for ext in extensions):
                continue
            resolved = SemanticFileRef(
                module_code=ref.module_code,
                file_stage=ref.file_stage,
                folder_sub_path=ref.folder_sub_path,
                file_name=name,
                project_id=ref.project_id,
            )
            return resolved, item
        raise DataCenterError(3001, "目录下无可用文件", status_code=404)
