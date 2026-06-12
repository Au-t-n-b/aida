# -*- coding: utf-8 -*-
"""步骤 9+ 共享：执行机/网关配置加载 + CloudOpsClient 构建 + 通用门禁。

复用导入 Toolkit 的 `cloudops_client`（CreateTask/TaskStatusQuery/ReportExport）。
连线检查、灵衢连线检查及后续子命令都从这里取 client，避免各自重复加载。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_STEP8_SCRIPTS = (
    Path(__file__).resolve().parent.parent
    / "software_deployment"
    / "8_toolkit_import"
    / "scripts"
)
if str(_STEP8_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_STEP8_SCRIPTS))

from cloudops_client import CloudOpsClient, CloudOpsClientError, GatewayEnv  # noqa: E402

__all__ = [
    "CloudOpsClient",
    "CloudOpsClientError",
    "GatewayEnv",
    "plan_runtime_dir",
    "load_executor_config",
    "load_gateway_config",
    "build_client",
    "preflight_toolkit",
]


def _skill_root(skill_dir: str | Path) -> Path:
    return Path(skill_dir).resolve()


def plan_runtime_dir(skill_dir: str | Path) -> Path:
    return _skill_root(skill_dir) / "ProjectData" / "plan" / "RunTime"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def load_executor_config(skill_dir: str | Path) -> dict[str, Any]:
    return _load_json(plan_runtime_dir(skill_dir) / "toolkit_executor.json")


def load_gateway_config(skill_dir: str | Path) -> tuple[bool, str, GatewayEnv | None]:
    raw = _load_json(plan_runtime_dir(skill_dir) / "gateway.json")
    apigw_url = str(os.environ.get("CLOUDOPS_APIGW_URL") or raw.get("apigw_url") or "").strip()
    gateway_key = str(os.environ.get("CLOUDOPS_GATEWAY_KEY") or raw.get("gateway_key") or "").strip()
    hw_app_id = str(os.environ.get("CLOUDOPS_HW_APP_ID") or raw.get("hw_app_id") or "").strip()
    if not apigw_url or not gateway_key or not hw_app_id:
        return (
            False,
            "缺少 APIGW 配置：请编辑 `ProjectData/plan/RunTime/gateway.json` 或设置 `CLOUDOPS_*` 环境变量。",
            None,
        )
    return True, "", GatewayEnv(apigw_url=apigw_url, gateway_key=gateway_key, hw_app_id=hw_app_id)


def build_client(skill_dir: str | Path) -> CloudOpsClient:
    ok_gw, msg, gateway = load_gateway_config(skill_dir)
    if not ok_gw or gateway is None:
        raise CloudOpsClientError(msg or "gateway missing")
    ex = load_executor_config(skill_dir)
    return CloudOpsClient(
        gateway=gateway,
        base_url_ip=str(ex.get("base_url_ip") or ""),
        base_url_port=str(ex.get("base_url_port") or "28880"),
        secret_key=str(ex.get("secret_key") or ""),
    )


def preflight_toolkit(skill_dir: str | Path) -> tuple[bool, list[str]]:
    """步骤 9+ 通用门禁：步骤 8 已导入 + 执行机/网关有效。"""
    missing: list[str] = []
    chain = _load_json(plan_runtime_dir(skill_dir) / "deploy_chain.json")
    if not str(chain.get("step8_toolkit_import_at") or "").strip():
        missing.append("请先完成 **步骤 8：导入 CloudOps 到 Toolkit**。")
    if not str(chain.get("step7_executor_config_at") or "").strip():
        missing.append("请先完成 **步骤 7：设置调测设备**。")
    ok_gw, msg_gw, _ = load_gateway_config(skill_dir)
    if not ok_gw:
        missing.append(msg_gw)
    ex = load_executor_config(skill_dir)
    if not str(ex.get("base_url_ip") or "").strip():
        missing.append("执行机缺少 `base_url_ip`。")
    if not str(ex.get("secret_key") or "").strip():
        missing.append("执行机缺少 `secret_key`。")
    return (len(missing) == 0, missing)
