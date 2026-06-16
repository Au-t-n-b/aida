"""从 ProjectData/results 读取 receipt/result，组装调测任务记录展示字段。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _rel_project_path(skill_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(skill_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def resolve_task_run_dir(skill_root: Path, record: dict[str, Any]) -> Path | None:
    """定位单次命令调测的结果目录（含 receipt.json）。"""
    step_key = str(record.get("stepKey") or "").strip()
    task_name = str(record.get("taskName") or "").strip()
    result_dir = str(record.get("resultDir") or "").strip().replace("\\", "/")

    candidates: list[Path] = []
    if result_dir:
        p = Path(result_dir)
        if p.is_absolute():
            candidates.append(p)
        elif result_dir.startswith("ProjectData/"):
            candidates.append(skill_root / result_dir)
        elif step_key and task_name:
            candidates.append(skill_root / "ProjectData" / "results" / step_key / task_name)
    if step_key and task_name:
        candidates.append(skill_root / "ProjectData" / "results" / step_key / task_name)

    seen: set[str] = set()
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        if (cand / "receipt.json").is_file():
            return cand.resolve()

    if not step_key:
        return None
    type_dir = skill_root / "ProjectData" / "results" / step_key
    if not type_dir.is_dir():
        return None
    subs = sorted(
        (d for d in type_dir.iterdir() if d.is_dir() and (d / "receipt.json").is_file()),
        key=lambda d: d.name,
        reverse=True,
    )
    if task_name:
        for d in subs:
            if d.name == task_name:
                return d.resolve()
    return subs[0].resolve() if subs else None


def _failed_devices_from_result(result: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    devices = result.get("devices")
    if not isinstance(devices, list):
        return out
    for row in devices:
        if not isinstance(row, dict):
            continue
        verdict = str(row.get("result") or row.get("checkResult") or "").strip()
        if verdict in ("Pass", "通过", "SUCCESS", "成功"):
            continue
        if verdict in ("", "—") and row.get("result") != "Fail":
            continue
        ip = str(
            row.get("ip")
            or row.get("deviceIp")
            or row.get("nodeIp")
            or row.get("nodeIP")
            or ""
        ).strip()
        reason = str(row.get("checkResult") or row.get("reason") or row.get("result") or "失败").strip()
        if ip or reason:
            out.append({"ip": ip or "—", "reason": reason})
    return out


def _artifact_items(skill_root: Path, run_dir: Path) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    patterns = (
        ("report.zip", "原始报告 ZIP", "other"),
        ("report.xlsx", "原始报告 XLSX", "xlsx"),
        ("result.json", "解析结果 JSON", "json"),
        ("receipt.json", "任务回执", "json"),
    )
    for name, label, kind in patterns:
        p = run_dir / name
        if p.is_file():
            items.append(
                {
                    "label": label,
                    "path": _rel_project_path(skill_root, p),
                    "kind": kind,
                }
            )
    agg = skill_root / "ProjectData" / "results" / "调测报告汇总_latest.xlsx"
    if agg.is_file():
        items.append(
            {
                "label": "调测报告汇总",
                "path": _rel_project_path(skill_root, agg),
                "kind": "xlsx",
            }
        )
    return items


def load_report_bundle(skill_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    """读取磁盘产物，返回结构化汇报字段（无目录则空 dict）。"""
    run_dir = resolve_task_run_dir(skill_root, record)
    if run_dir is None:
        return {}

    receipt = _load_json(run_dir / "receipt.json")
    result = _load_json(run_dir / "result.json")
    last_query = receipt.get("lastQuery") if isinstance(receipt.get("lastQuery"), dict) else {}
    query_data = last_query.get("data") if isinstance(last_query.get("data"), dict) else {}

    success = query_data.get("successNum")
    if success is None:
        success = result.get("successNum")
    fail = query_data.get("failNum")
    if fail is None:
        fail = result.get("failNum")
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    if success is None and summary.get("passed") is not None:
        success = summary.get("passed")
    if fail is None and summary.get("failed") is not None:
        fail = summary.get("failed")

    total = query_data.get("totalNums")
    if total is None and success is not None and fail is not None:
        try:
            total = int(success) + int(fail)
        except (TypeError, ValueError):
            total = None

    passed: bool | None = None
    if success is not None or fail is not None:
        try:
            passed = int(fail or 0) == 0 and int(success or 0) >= 0
        except (TypeError, ValueError):
            passed = None
    elif result.get("passed") is not None:
        passed = bool(result.get("passed"))

    conclusion = "通过" if passed is True else ("不通过" if passed is False else "—")
    failed_devices = _failed_devices_from_result(result)
    if not failed_devices and fail not in (None, 0, "0") and int(fail or 0) > 0:
        failed_devices = [{"ip": "—", "reason": f"共 {fail} 台失败，明细见 report.zip"}]

    task_id = str(receipt.get("taskId") or record.get("taskId") or "")
    task_name = str(receipt.get("taskName") or run_dir.name)
    finished_at = str(receipt.get("finishedAt") or record.get("endedAt") or "")
    markdown = str(result.get("markdown") or "").strip()
    scope = str(receipt.get("scope") or "")
    pod_ids = receipt.get("podIds") if isinstance(receipt.get("podIds"), list) else []

    return {
        "taskId": task_id,
        "taskName": task_name,
        "resultDir": _rel_project_path(skill_root, run_dir),
        "successNum": success,
        "failNum": fail,
        "totalNums": total,
        "passed": passed,
        "conclusion": conclusion,
        "finishedAt": finished_at,
        "failedDevices": failed_devices[:20],
        "artifacts": _artifact_items(skill_root, run_dir),
        "markdownExtra": markdown,
        "scope": scope,
        "podIds": pod_ids,
        "deviceCount": receipt.get("deviceCount") or record.get("deviceCount"),
    }


def enrich_commission_record(record: dict[str, Any], skill_root: Path) -> dict[str, Any]:
    """合并磁盘汇报字段，供任务记录表与详情使用。"""
    out = dict(record)
    bundle = load_report_bundle(skill_root, out)
    if not bundle:
        return out

    for key, val in bundle.items():
        if val in (None, "", [], {}):
            continue
        out[key] = val

    succ = out.get("successNum")
    fail = out.get("failNum")
    if succ is not None or fail is not None:
        out["passFail"] = f"{succ if succ is not None else '?'}/{fail if fail is not None else '?'}"
    if bundle.get("conclusion"):
        out["conclusion"] = bundle["conclusion"]
        if not out.get("summaryRows"):
            dev = str(out.get("deviceCount") or succ or "—")
            out["summaryRows"] = [[bundle["conclusion"], str(succ or "—"), str(fail or "—"), dev]]
    return out
