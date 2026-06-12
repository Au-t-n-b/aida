"""CloudOps ZTP export API — 对齐 generated_ztp_api.call_cloudops_api。"""

from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_URL_PROD = (
    "https://apigw-cn-south02.huawei.com/api/apiaccess/infra/cloudops/v1/machine/ztp-build/export"
)
DEFAULT_URL_TEST = (
    "https://apigw-beta.huawei.com/api/apiaccess/infra/cloudops/v1/machine/ztp-build/export"
)


def call_cloudops_export(api_request: dict[str, Any], *, test_env: bool = False) -> requests.Response:
    token = os.environ.get("CLOUDOPS_AUTHORIZATION") or os.environ.get("CPCIA_AUTHORIZATION")
    app_id = os.environ.get("CLOUDOPS_X_HW_ID") or os.environ.get("CPCIA_APP_ID")
    if not token:
        raise ValueError(
            "调用 CloudOps 需要环境变量 CLOUDOPS_AUTHORIZATION（或 CPCIA_AUTHORIZATION）"
        )
    if not app_id:
        raise ValueError("调用 CloudOps 需要环境变量 CLOUDOPS_X_HW_ID（或 CPCIA_APP_ID）")

    url = os.environ.get("CLOUDOPS_EXPORT_URL")
    if not url:
        url = DEFAULT_URL_TEST if test_env else DEFAULT_URL_PROD

    headers = {
        "X-HW-ID": app_id,
        "Authorization": token,
    }
    return requests.post(url, headers=headers, json=api_request, timeout=600)
