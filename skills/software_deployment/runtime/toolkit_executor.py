# -*- coding: utf-8 -*-
"""步骤 7：登记执行机 IP/SK（写入 toolkit_executor.json，供步骤 8 Toolkit 联调读取）。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def executor_config_path(skill_root: Path) -> Path:
    return skill_root / "ProjectData" / "plan" / "RunTime" / "toolkit_executor.json"


def load_executor_config(skill_root: Path) -> dict[str, Any]:
    p = executor_config_path(skill_root)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def save_executor_config(skill_root: Path, data: dict[str, Any]) -> Path:
    p = executor_config_path(skill_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def mask_secret(sk: str) -> str:
    s = str(sk or "").strip()
    if len(s) <= 4:
        return "****" if s else ""
    return f"{s[:2]}****{s[-2:]}"


def parse_executor_from_hitl(result: dict[str, Any]) -> dict[str, str]:
    """解析步骤 7 表单或旧版 JSON 文本回传。"""
    if not isinstance(result, dict):
        return {}

    ip = str(
        result.get("base_url_ip")
        or result.get("ip")
        or result.get("调测IP")
        or ""
    ).strip()
    sk = str(
        result.get("secret_key")
        or result.get("sk")
        or result.get("SK")
        or ""
    ).strip()
    port = str(result.get("base_url_port") or result.get("port") or "28880").strip() or "28880"
    if ip and sk:
        return {
            "base_url_ip": ip,
            "base_url_port": port,
            "secret_key": sk,
        }

    raw_text = ""
    for key in ("text", "value", "input", "content"):
        if key in result and isinstance(result.get(key), str):
            raw_text = str(result.get(key)).strip()
            break
    if not raw_text:
        return {}
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        "base_url_ip": str(parsed.get("base_url_ip") or parsed.get("ip") or "").strip(),
        "base_url_port": str(parsed.get("base_url_port") or parsed.get("port") or "28880").strip() or "28880",
        "secret_key": str(parsed.get("secret_key") or parsed.get("sk") or "").strip(),
    }


def emit_hitl_executor_configure(
    emit,
    *,
    thread_id: str,
    skill_name: str,
    run_id: str,
    request_id: str,
    existing: dict[str, Any] | None = None,
) -> None:
    ex = existing or {}
    emit(
        {
            "event": "hitl.form_request",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": int(time.time() * 1000),
            "payload": {
                "requestId": f"{request_id}:toolkit-executor",
                # 不设固定 cardId：每次 append 新表单到对话底部，避免「修改调测设备」
                # 在 replace 模式下覆盖上方已提交的旧表单且用户仍盯着完成卡。
                "purpose": "toolkit_executor_configure",
                "title": "设置调测设备",
                "helpText": "端口默认 28880；现场需已启动 Toolkit 网关服务。",
                "fields": [
                    {
                        "key": "base_url_ip",
                        "label": "调测IP",
                        "placeholder": "请输入",
                        "required": True,
                        "inputType": "text",
                        "defaultValue": str(ex.get("base_url_ip") or ""),
                    },
                    {
                        "key": "secret_key",
                        "label": "SK",
                        "placeholder": "请输入",
                        "required": True,
                        "inputType": "password",
                        "defaultValue": "",
                    },
                ],
                "confirmLabel": "确认",
                "cancelLabel": "取消",
                "resumeAction": "toolkit_executor_configured",
                "onCancelAction": "sd_start",
                "moduleId": "software_deployment",
                "stepId": "software_deployment.toolkit_executor",
            },
        }
    )
