"""Shared HITL helpers for software_deployment steps."""
from __future__ import annotations

from typing import Any

from ...base import CheckResult


def confirmations(project: dict[str, Any] | None) -> dict[str, Any]:
    raw = (project or {}).get("confirmations")
    return raw if isinstance(raw, dict) else {}


def is_confirmed(project: dict[str, Any] | None, key: str) -> bool:
    return bool(confirmations(project).get(key))


def confirm_input(key: str, label: str, description: str = "") -> list[dict[str, Any]]:
    return [{
        "id": key,
        "label": label,
        "options": [
            {"label": "确认执行", "value": "confirm", "description": description},
        ],
    }]


def confirm_gate(
    project: dict[str, Any] | None,
    key: str,
    label: str,
    *,
    note: str = "",
    description: str = "",
) -> CheckResult:
    if is_confirmed(project, key):
        return {"ok": True, "missing": [], "found": [], "note": ""}
    return {
        "ok": False,
        "missing": [],
        "found": [],
        "note": note or f"{label} 需要确认",
        "need_inputs": confirm_input(key, label, description),
    }


def executor_config_input() -> list[dict[str, Any]]:
    return [{
        "id": "toolkit_executor_config",
        "label": "填写调测设备 IP/SK",
        "input_type": "text",
        "placeholder": '{ "base_url_ip": "100.100.166.137", "secret_key": "...", "base_url_port": "28880" }',
        "help": "请提交 JSON；base_url_port 可省略，默认 28880。",
        "options": [{"label": "提交配置", "value": "confirm"}],
    }]
