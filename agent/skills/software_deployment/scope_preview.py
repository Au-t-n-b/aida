"""Preview commission device scope (resolve_devices dry-run)."""
from __future__ import annotations

from typing import Any

from .bridge import get_sd_root, import_sd_script

STEP_TO_COMMAND: dict[str, str] = {
    "connection": "connection",
    "lq_connection": "lq_connection",
    "weak_light": "weak_light",
    "hccs_weak_light": "hccs_weak_light",
}


def preview_commission_scope(body: dict[str, Any]) -> dict[str, Any]:
    root = get_sd_root()
    step_key = str(body.get("step_key") or "").strip()
    command = str(body.get("command") or STEP_TO_COMMAND.get(step_key) or "").strip()
    if not command:
        return {"ok": False, "error": f"未知调测步骤：{step_key or command}"}

    scope = str(body.get("scope") or "all").strip()
    pod_ids = body.get("pod_ids")
    devices = body.get("devices")
    task_no = str(body.get("task_no") or "").strip()
    only_installed = body.get("only_installed", True)

    if isinstance(pod_ids, list):
        pod_ids = [int(p) for p in pod_ids if str(p).strip() != ""]
    else:
        pod_ids = None

    if isinstance(devices, list):
        devices = [str(d).strip() for d in devices if str(d).strip()]
    else:
        devices = None

    spec_mod = import_sd_script(root, "9_commission/shared/task_catalog/scripts", "task_catalog")
    spec = spec_mod.resolve_task(command)
    if spec is None:
        return {"ok": False, "error": f"未识别命令：{command}"}

    resolver = import_sd_script(root, "9_commission/shared/device_scope/scripts", "device_resolver")
    rr = resolver.resolve_devices(
        root,
        scope=scope,
        pod_ids=pod_ids,
        devices=devices,
        task_no=task_no,
        only_installed=bool(only_installed),
        device_kind=spec.device_kind,
        task_type=spec.task_type,
    )
    if not rr.ok:
        return {
            "ok": False,
            "error": rr.message,
            "device_count": 0,
            "source": rr.source,
        }
    return {
        "ok": True,
        "device_count": len(rr.ips),
        "source": rr.source,
        "message": rr.message or "",
        "pod_ids": rr.pod_ids,
        "task_no": rr.task_no,
    }
