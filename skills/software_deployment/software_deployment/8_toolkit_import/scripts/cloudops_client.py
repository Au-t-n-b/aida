from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

import requests

try:
    from requests_toolbelt.multipart.encoder import MultipartEncoder  # type: ignore
except Exception:  # pragma: no cover
    MultipartEncoder = None

try:
    from .cloudops_sign import build_canonical_headers, convert_ipv4_to_ak, generate_signature_hmac_sha256
except ImportError:
    from cloudops_sign import build_canonical_headers, convert_ipv4_to_ak, generate_signature_hmac_sha256  # type: ignore


class CloudOpsClientError(RuntimeError):
    pass


def default_upload_timeout_s() -> int:
    """与 workbench 默认 300s 对齐；大文件经 APIGW 上传可再加大（环境变量）。"""
    for key in ("CLOUDOPS_UPLOAD_TIMEOUT_S", "CLOUDOPS_TIMEOUT_S"):
        raw = str(os.environ.get(key) or "").strip()
        if raw.isdigit():
            return max(60, min(int(raw), 1800))
    return 600


@dataclass(frozen=True)
class GatewayEnv:
    apigw_url: str
    gateway_key: str
    hw_app_id: str


class CloudOpsClient:
    """APIGW → GroundRoute gateway client（UploadFile，签名与 workbench 对齐）。"""

    def __init__(
        self,
        *,
        gateway: GatewayEnv,
        base_url_ip: str,
        base_url_port: str,
        secret_key: str,
        timeout_s: int | None = None,
    ) -> None:
        self.gateway = gateway
        self.apigw_url = str(gateway.apigw_url or "").rstrip("/")
        self.base_url_ip = str(base_url_ip or "").strip()
        self.base_url_port = str(base_url_port or "28880").strip() or "28880"
        self.secret_key = str(secret_key or "").strip()
        self.timeout_s = int(timeout_s) if timeout_s is not None else default_upload_timeout_s()
        self.unified_path = "/groundroute/gateway"
        self.host = f"{self.base_url_ip}:{self.base_url_port}"
        self.access_key = convert_ipv4_to_ak(self.base_url_ip)
        if not self.apigw_url:
            raise CloudOpsClientError("missing apigw_url")
        if not self.base_url_ip:
            raise CloudOpsClientError("missing base_url_ip")
        if not self.secret_key:
            raise CloudOpsClientError("missing secret_key")

    def _base_headers(self, *, content_type: str) -> dict[str, str]:
        return {
            "route_ip": self.base_url_ip,
            "Host": self.host,
            "X-HW-ID": str(self.gateway.hw_app_id),
            "X-HW-APPKEY": str(self.gateway.gateway_key),
            "Content-Type": content_type,
        }

    def init_unified_headers(self, *, operation: str, work_stage: str, content_type: str) -> dict[str, str]:
        headers = self._base_headers(content_type=content_type)
        headers["X-WORKSTAGE"] = work_stage
        headers["X-OPERATION"] = operation
        return headers

    def sign_request(
        self,
        headers: dict[str, str],
        method: str,
        url: str,
        *,
        body: Any = "",
    ) -> None:
        headers_to_be_signed = "Host;X-Timestamp"
        headers["X-Timestamp"] = str(int(time.time()))
        canonical_headers = build_canonical_headers(headers=headers, key_list=headers_to_be_signed)
        signature = generate_signature_hmac_sha256(
            secret_key=self.secret_key,
            method=method,
            url=url,
            canonical_query_string="",
            canonical_headers=canonical_headers,
            headers_to_be_signed=headers_to_be_signed,
            body=body,
        )
        headers.update(
            {
                "X-Access-Key": self.access_key,
                "X-Signature": signature,
                "X-Signed-Headers": headers_to_be_signed,
            }
        )

    @staticmethod
    def _is_multipart_encoder(body: Any) -> bool:
        return MultipartEncoder is not None and isinstance(body, MultipartEncoder)

    def rest_call(self, *, headers: dict[str, str], multipart_body: MultipartEncoder) -> requests.Response:
        request_headers = dict(headers)
        self.sign_request(request_headers, "POST", self.unified_path, body=multipart_body)
        full_url = f"{self.apigw_url}{self.unified_path}"
        return requests.post(
            full_url,
            data=multipart_body,
            headers=request_headers,
            timeout=self.timeout_s,
        )

    def _format_http_error(self, resp: requests.Response, op: str, payload: Any) -> str:
        code = int(resp.status_code)
        if code == 504:
            return (
                f"{op}：APIGW 网关超时（504 nginx）。"
                f"完整配置经网关转发到地端 Toolkit 时，处理超过网关等待上限（常见 60s）。"
                f"当前客户端超时 {self.timeout_s}s；可设置 `CLOUDOPS_UPLOAD_TIMEOUT_S=900` 后重试，"
                "若仍 504 需网关/运维调大 `proxy_read_timeout` 或换网络环境。"
            )
        if code in {502, 503}:
            return f"{op}：网关/地端暂不可用（HTTP {code}），请稍后重试。详情：{payload}"
        return f"{op} failed: status={code} payload={payload}"

    def _ensure_success(self, resp: requests.Response, op: str) -> dict[str, Any]:
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": (resp.text or "")[:500]}
        if resp.status_code != 200:
            raise CloudOpsClientError(self._format_http_error(resp, op, payload))
        if isinstance(payload, dict):
            code = payload.get("code")
            # 网关成功码在不同环境为 "200" / 0 / "0"；与 workbench 对齐（其判定 str(code)=="200"），
            # 同时兼容 0/"0"/None，避免把成功响应误判为失败。
            if code is not None and str(code) not in {"0", "200"}:
                raise CloudOpsClientError(f"{op} failed: code={code} payload={payload}")
            return payload
        return {"payload": payload}

    def upload_config_file(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        network: str = "outOfBand",
        work_stage: str = "lldImport",
    ) -> dict[str, Any]:
        if MultipartEncoder is None:
            raise CloudOpsClientError("缺少依赖 requests-toolbelt（用于 multipart 上传）")
        safe_name = unquote(filename) or filename
        last_err: Exception | None = None
        for attempt in range(3):
            multipart_body = MultipartEncoder(
                fields={
                    "file": (safe_name, file_bytes, "application/octet-stream"),
                    "network": network,
                }
            )
            headers = self.init_unified_headers(
                operation="UploadFile",
                work_stage=work_stage,
                content_type=multipart_body.content_type,
            )
            try:
                resp = self.rest_call(headers=headers, multipart_body=multipart_body)
                return self._ensure_success(resp, "upload_config_file")
            except CloudOpsClientError as e:
                last_err = e
                msg = str(e)
                if attempt < 2 and ("504" in msg or "502" in msg or "503" in msg):
                    time.sleep(2**attempt)
                    continue
                raise
            except requests.RequestException as e:
                last_err = e
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise CloudOpsClientError(f"upload_config_file 网络异常：{e}") from e
        if last_err:
            raise last_err
        raise CloudOpsClientError("upload_config_file failed")

    @staticmethod
    def _compact_json_bytes(body: dict[str, Any]) -> bytes:
        return json.dumps(body, ensure_ascii=False).replace(" ", "").encode("utf-8")

    def rest_call_json(
        self,
        *,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> requests.Response:
        request_headers = dict(headers)
        self.sign_request(request_headers, "POST", self.unified_path, body=body)
        full_url = f"{self.apigw_url}{self.unified_path}"
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                return requests.post(
                    full_url,
                    headers=request_headers,
                    data=self._compact_json_bytes(body),
                    timeout=self.timeout_s,
                )
            except requests.RequestException as e:
                last_err = e
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise CloudOpsClientError(f"rest_call_json 网络异常：{e}") from e
        if last_err:
            raise last_err
        raise CloudOpsClientError("rest_call_json failed")

    def create_task_multipart_ztp(
        self,
        *,
        work_stage: str,
        config_check_req: dict[str, Any],
        ztp_bytes: bytes,
        ztp_filename: str,
    ) -> str:
        """灵衢配置检查等：CreateTask multipart（ZTP zip + configCheckReq JSON）。"""
        if MultipartEncoder is None:
            raise CloudOpsClientError("缺少依赖 requests-toolbelt（用于 multipart 下发）")
        safe_name = unquote(ztp_filename) or ztp_filename or "ZTP.zip"
        config_json = json.dumps(config_check_req, ensure_ascii=False)
        multipart_body = MultipartEncoder(
            fields={
                "file": (safe_name, ztp_bytes, "application/octet-stream"),
                "configCheckReq": ("", config_json, "application/json"),
            }
        )
        headers = self.init_unified_headers(
            operation="CreateTask",
            work_stage=work_stage,
            content_type=multipart_body.content_type,
        )
        resp = self.rest_call(headers=headers, multipart_body=multipart_body)
        payload = self._ensure_success(resp, "create_task_multipart_ztp")
        task_id = str(payload.get("data") or "").strip()
        if not task_id:
            raise CloudOpsClientError(f"create_task_multipart_ztp: missing taskId in response: {payload}")
        return task_id

    def create_task(self, *, work_stage: str, body: dict[str, Any]) -> str:
        headers = self.init_unified_headers(
            operation="CreateTask",
            work_stage=work_stage,
            content_type="application/json",
        )
        resp = self.rest_call_json(headers=headers, body=body)
        payload = self._ensure_success(resp, "create_task")
        task_id = str(payload.get("data") or "").strip()
        if not task_id:
            raise CloudOpsClientError(f"create_task: missing taskId in response: {payload}")
        return task_id

    def query_task(self, *, work_stage: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = self.init_unified_headers(
            operation="TaskStatusQuery",
            work_stage=work_stage,
            content_type="application/json",
        )
        resp = self.rest_call_json(headers=headers, body=body)
        return self._ensure_success(resp, "query_task")

    def query_report_history(
        self,
        *,
        work_stage: str,
        task_id: str,
        check_type: str = "server",
    ) -> str:
        """ReportQuery：取最新报告 createTime（集群健康检查等）。"""
        headers = self.init_unified_headers(
            operation="ReportQuery",
            work_stage=work_stage,
            content_type="application/json",
        )
        body = {"taskId": task_id, "checkType": check_type}
        resp = self.rest_call_json(headers=headers, body=body)
        payload = self._ensure_success(resp, "query_report_history")
        data = payload.get("data") if isinstance(payload, dict) else {}
        rows = data.get("pageReportHistoryInfoList") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not rows:
            return ""
        latest = sorted(
            [r for r in rows if isinstance(r, dict) and r.get("createTime")],
            key=lambda x: str(x.get("createTime")),
            reverse=True,
        )
        return str(latest[0].get("createTime") or "").strip() if latest else ""

    def export_report(
        self,
        *,
        work_stage: str,
        task_id: str,
        report_list: list[str] | None = None,
    ) -> bytes:
        headers = self.init_unified_headers(
            operation="ReportExport",
            work_stage=work_stage,
            content_type="application/json",
        )
        body: dict[str, Any] = {"taskId": task_id}
        if report_list:
            body["reportList"] = list(report_list)
        request_headers = dict(headers)
        self.sign_request(request_headers, "POST", self.unified_path, body=body)
        full_url = f"{self.apigw_url}{self.unified_path}"
        resp = requests.post(
            full_url,
            headers=request_headers,
            data=self._compact_json_bytes(body),
            timeout=self.timeout_s,
        )
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "application/json" in content_type:
            try:
                payload = resp.json()
            except Exception:
                payload = {"raw": (resp.text or "")[:500]}
            raise CloudOpsClientError(f"export_report returned json: {payload}")
        if resp.status_code != 200:
            raise CloudOpsClientError(f"export_report failed: status={resp.status_code}")
        return resp.content
