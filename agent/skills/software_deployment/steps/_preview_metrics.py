"""SDUI 预览 metrics 裁剪 · 供 step.run 写入 state（投影器只读 metrics，不读盘）。"""
from __future__ import annotations

from typing import Any

_COMMISSION_LABELS = {
    "connection": "服务器连线检查",
    "lq_connection": "灵衢连线检查",
    "weak_light": "服务器弱光检查",
    "hccs_weak_light": "灵衢光链路检查",
}


def slim_scene_spec(scene: dict[str, Any] | None) -> dict[str, str]:
    raw = scene or {}
    keys = (
        ("product_specification", "productSpecification", "产品规格"),
        ("cooling", "cooling", "冷却场景"),
        ("training", "training", "训练场景"),
        ("pod_scenario", "podScenario", "Pod场景"),
    )
    out: dict[str, str] = {}
    for a, b, _label in keys:
        val = str(raw.get(a) or raw.get(b) or "").strip()
        if val:
            out[a if a in raw else b] = val
    return out


def slim_third_tasks(rows: list[dict[str, Any]], *, limit: int = 120) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        qty = row.get("deviceQuantity")
        done = row.get("finishNum")
        pct = 0
        if isinstance(qty, (int, float)) and qty > 0 and isinstance(done, (int, float)):
            pct = min(100, int(round(100 * float(done) / float(qty))))
        out.append(
            {
                "secondActivityName": str(row.get("secondActivityName") or ""),
                "thirdActivityName": str(row.get("thirdActivityName") or ""),
                "taskType": str(row.get("taskType") or ""),
                "deviceList": str(row.get("deviceList") or ""),
                "deviceQuantity": qty,
                "finishNum": done,
                "progressPct": pct,
                "status": str(row.get("status") or ""),
                "principal": str(row.get("principal") or ""),
                "startDate": str(row.get("startDate") or ""),
                "endDate": str(row.get("endDate") or ""),
                "managementUnit": str(row.get("managementUnit") or ""),
                "podIds": row.get("podIds") or [],
            }
        )
    return out


_DEVICE_TYPE_LABEL = {
    "SERVER": "智算服务器",
    "LQ_SWITCH": "灵衢交换机",
    "SWITCH": "交换机",
    "STORAGE": "存储",
}


def _task_status_label(status: str) -> str:
    st = (status or "").upper()
    if "INIT" in st or st in ("", "TASK_STATUS_UN_INIT", "UN_INIT"):
        return "未初始化"
    if "RUN" in st or "ING" in st:
        return "进行中"
    if "DONE" in st or "COMPLETE" in st or "SUCCESS" in st:
        return "已完成"
    return status or "—"


def slim_device_tasks(
    rows: list[dict[str, Any]],
    *,
    limit: int = 150,
    commission_flags: dict[str, bool] | None = None,
) -> list[dict[str, Any]]:
    flags = commission_flags or {}
    conn = "已通过" if flags.get("connection") else "未初始化"
    lq = "已通过" if flags.get("lq_connection") else "未初始化"
    weak = "已通过" if flags.get("weak_light") else "未初始化"
    hccs = "已通过" if flags.get("hccs_weak_light") else "未初始化"
    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        pod_id = row.get("superpodId")
        pod = f"Pod-{pod_id}" if pod_id not in (None, "", 0) else "Pod-1"
        dtype = str(row.get("deviceType") or "")
        out.append(
            {
                "deviceIp": str(row.get("deviceIp") or ""),
                "deviceName": str(row.get("deviceName") or ""),
                "deviceType": _DEVICE_TYPE_LABEL.get(dtype, dtype or "—"),
                "pod": pod,
                "thirdTaskName": str(row.get("thirdTaskName") or ""),
                "taskStatus": _task_status_label(str(row.get("taskStatus") or "")),
                "connection": conn,
                "lqConnection": lq,
                "weakLight": weak,
                "hccsWeakLight": hccs,
            }
        )
    return out


def device_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    ips: set[str] = set()
    pods: set[str] = set()
    by_type: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ip = str(row.get("deviceIp") or "").strip()
        if ip:
            ips.add(ip)
        pod_id = row.get("superpodId")
        if pod_id not in (None, ""):
            pods.add(str(pod_id))
        dtype = str(row.get("deviceType") or "OTHER")
        by_type[dtype] = by_type.get(dtype, 0) + 1
        label = _task_status_label(str(row.get("taskStatus") or ""))
        status_counts[label] = status_counts.get(label, 0) + 1
    return {
        "device_count": len(ips) or len(rows),
        "pod_count": len(pods),
        "by_type": by_type,
        "by_status": status_counts,
    }


def build_commission_failure_record(
    step_key: str,
    error_message: str,
    *,
    started_at: str = "",
    ended_at: str = "",
) -> dict[str, Any]:
    """命令调测失败时写入任务记录（无 result_dir）。"""
    err = str(error_message or "执行失败").strip()
    return {
        "stepKey": step_key,
        "taskType": _COMMISSION_LABELS.get(step_key, step_key),
        "taskName": step_key,
        "description": _COMMISSION_LABELS.get(step_key, step_key),
        "deviceCount": "—",
        "startedAt": _fmt_ts(started_at),
        "endedAt": _fmt_ts(ended_at),
        "executor": "driver.py",
        "status": "失败",
        "resultDir": "",
        "errorMessage": err,
        "summaryRows": [],
    }


def build_commission_record(
    step_key: str,
    result: dict[str, Any],
    *,
    started_at: str = "",
    ended_at: str = "",
) -> dict[str, Any]:
    detail = result.get("detail") if isinstance(result.get("detail"), dict) else {}
    task_name = str(
        detail.get("taskName")
        or detail.get("task_name")
        or result.get("task_id")
        or f"{step_key}_task"
    )
    success = detail.get("successNum")
    fail = detail.get("failNum")
    passed: str | None = None
    if success is not None or fail is not None:
        passed = "通过" if int(fail or 0) == 0 and int(success or 0) >= 0 else "不通过"
    elif detail.get("passed") is not None:
        passed = "通过" if detail.get("passed") else "不通过"

    summary_rows: list[list[str]] = []
    if passed:
        fiber = str(detail.get("fiberCount") or detail.get("testFiberCount") or "—")
        dev = str(detail.get("deviceCount") or detail.get("totalDevices") or success or "—")
        summary_rows.append([passed, fiber, dev])
    for item in detail.get("summaryRows") or detail.get("listData") or []:
        if not isinstance(item, dict):
            continue
        summary_rows.append(
            [
                str(item.get("optResult") or item.get("checkResult") or item.get("result") or "—"),
                str(item.get("fiberCount") or item.get("testFiber") or "—"),
                str(item.get("deviceCount") or item.get("deviceIp") or "—"),
            ]
        )

    return {
        "stepKey": step_key,
        "taskType": _COMMISSION_LABELS.get(step_key, step_key),
        "taskName": task_name,
        "description": str(detail.get("description") or detail.get("taskDesc") or _COMMISSION_LABELS.get(step_key, "")),
        "deviceCount": str(detail.get("deviceCount") or detail.get("totalDevices") or "—"),
        "startedAt": _fmt_ts(started_at),
        "endedAt": _fmt_ts(ended_at),
        "executor": str(detail.get("executor") or detail.get("operator") or "driver.py"),
        "status": "已完成" if result.get("ok") else "失败",
        "resultDir": str(result.get("result_dir") or ""),
        "errorMessage": "" if result.get("ok") else str(result.get("error") or result.get("message") or ""),
        "summaryRows": summary_rows[:8],
    }


def _fmt_ts(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return "—"
    return text[:19].replace("T", " ")
