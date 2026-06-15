"""Shared HITL helpers for software_deployment steps."""
from __future__ import annotations

from typing import Any

from ...base import CheckResult
from .scope_parse import ScopeParams, normalize_parsed


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


def commission_state(project: dict[str, Any] | None) -> dict[str, Any]:
    raw = (project or {}).get("commission")
    return dict(raw) if isinstance(raw, dict) else {}


def is_scope_ready_for(project: dict[str, Any] | None, command: str) -> bool:
    comm = commission_state(project)
    return (
        str(comm.get("phase") or "") == "ready"
        and str(comm.get("pending_command") or "") == command
        and normalize_parsed(comm.get("parsed")) is not None
    )


def apply_parsed_to_project(project: dict[str, Any]) -> dict[str, Any]:
    """将 commission.parsed 同步到 project 顶层字段（供 device_resolver / task_runner）。"""
    p = dict(project or {})
    comm = commission_state(p)
    parsed = normalize_parsed(comm.get("parsed"))
    if not parsed:
        return p
    p["scope"] = parsed.get("scope", "all")
    if parsed.get("pod_ids"):
        p["pod_ids"] = list(parsed["pod_ids"])
    else:
        p.pop("pod_ids", None)
    if parsed.get("devices"):
        p["devices"] = list(parsed["devices"])
    else:
        p.pop("devices", None)
    if parsed.get("task_no"):
        p["task_no"] = parsed["task_no"]
    else:
        p.pop("task_no", None)
    p["only_installed"] = bool(parsed.get("only_installed", True))
    p["commission"] = comm
    return p


def scope_input_hitl(command: str, label: str, parse_error: str = "") -> list[dict[str, Any]]:
    help_lines = [
        "示例：全量 / POD01 / POD01 排除 10.1.1.1 / 只测 10.1.1.2",
        "按参数文件指定设备 / （任务号）未通过的设备",
    ]
    if parse_error:
        help_lines.insert(0, parse_error)
    return [{
        "id": "commission_scope_input",
        "label": f"设备范围 · {label}",
        "input_type": "text",
        "placeholder": "POD01 / 全量 / 只测 10.1.1.2,10.1.1.3 …",
        "help": "\n".join(help_lines),
        "command": command,
        "options": [{"label": "解析范围", "value": "submit_scope"}],
    }]


def scope_confirm_input(command: str, label: str, description: str = "") -> list[dict[str, Any]]:
    return [{
        "id": command,
        "label": f"确认执行 · {label}",
        "options": [
            {"label": "确认执行", "value": "confirm", "description": description},
            {"label": "重新填写", "value": "back", "description": "返回修改设备范围"},
        ],
    }]
