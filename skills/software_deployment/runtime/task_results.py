# -*- coding: utf-8 -*-
"""步骤 9+ 执行机 Toolkit 任务结果的**统一存储规范**。

约定（对齐 CPCIA Agent `deploymentandtest/<dialogue_id>/<check>/`）：

    ProjectData/results/<task_type>/<task_name>/
        report.zip      原始报告（ReportExport 返回的二进制，原样落盘）
        extracted/      report.zip 解压后的原始文件（best-effort）
        result.json     解析后的结构化结果（各子命令自行写入，缺省为空）
        receipt.json    任务回执：taskId、下发 body、末次查询、报告路径、时间

并维护 ProjectData/results/index.json 作为全部任务运行的索引（供大盘/续做读取）。

`plan/Output/` 仍只放 1~6 步计划产物；`plan/RunTime/` 仍只放状态/链路时间戳。
执行机返回的「运行结果」一律进 `ProjectData/results/`。
"""
from __future__ import annotations

import json
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .file_registry import register_file
    from .file_tags import AgentTag, FileTagName, report_tag_for_task
except ImportError:
    from file_registry import register_file  # type: ignore
    from file_tags import AgentTag, FileTagName, report_tag_for_task  # type: ignore


def results_root(skill_dir: str | Path) -> Path:
    return Path(skill_dir).resolve() / "ProjectData" / "results"


def task_dir(skill_dir: str | Path, task_type: str, task_name: str) -> Path:
    safe_type = _safe(task_type) or "unknown"
    safe_name = _safe(task_name) or f"task_{int(time.time())}"
    return results_root(skill_dir) / safe_type / safe_name


def _safe(name: str) -> str:
    bad = '<>:"/\\|?*'
    out = "".join("_" if ch in bad else ch for ch in str(name or "").strip())
    return out.strip(". ")


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


@dataclass
class SavedResult:
    task_type: str
    task_name: str
    task_id: str
    dir: Path
    report_path: Path | None = None
    extracted_dir: Path | None = None
    result_path: Path | None = None
    receipt_path: Path | None = None
    extracted_files: list[str] = field(default_factory=list)


def save_task_result(
    *,
    skill_dir: str | Path,
    task_type: str,
    task_name: str,
    task_id: str,
    work_stage: str,
    execute_body: dict[str, Any] | None = None,
    last_query: dict[str, Any] | None = None,
    report_bytes: bytes | None = None,
    report_filename: str = "report.zip",
    report_suffix: str = "",
    parsed_result: Any = None,
    extract_zip: bool = True,
    extra: dict[str, Any] | None = None,
) -> SavedResult:
    """落盘一次任务运行的全部产物，并更新索引。"""
    base = task_dir(skill_dir, task_type, task_name)
    base.mkdir(parents=True, exist_ok=True)
    saved = SavedResult(task_type=task_type, task_name=task_name, task_id=task_id, dir=base)

    if report_bytes is not None:
        name = report_filename
        if report_suffix and (not name or name == "report.zip"):
            ext = str(report_suffix).strip().lstrip(".")
            name = f"report.{ext}" if ext else "report.zip"
        safe_name = _safe(name) or "report.zip"
        report_path = base / safe_name
        report_path.write_bytes(report_bytes)
        saved.report_path = report_path
        if extract_zip and safe_name.lower().endswith(".zip"):
            extracted = base / "extracted"
            try:
                if zipfile.is_zipfile(report_path):
                    extracted.mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(report_path) as zf:
                        zf.extractall(extracted)
                        saved.extracted_files = [n for n in zf.namelist() if not n.endswith("/")]
                    saved.extracted_dir = extracted
            except Exception:
                saved.extracted_dir = None

    if parsed_result is not None:
        result_path = base / "result.json"
        payload = parsed_result if isinstance(parsed_result, (dict, list)) else {"value": parsed_result}
        result_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        saved.result_path = result_path

    finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    receipt: dict[str, Any] = {
        "schemaVersion": 1,
        "taskType": task_type,
        "taskName": task_name,
        "taskId": task_id,
        "workStage": work_stage,
        "executeBody": execute_body or {},
        "lastQuery": last_query or {},
        "reportPath": str(saved.report_path) if saved.report_path else "",
        "extractedDir": str(saved.extracted_dir) if saved.extracted_dir else "",
        "extractedFiles": saved.extracted_files,
        "resultPath": str(saved.result_path) if saved.result_path else "",
        "finishedAt": finished_at,
    }
    if isinstance(extra, dict):
        receipt.update(extra)
    receipt_path = base / "receipt.json"
    _save_json(receipt_path, receipt)
    saved.receipt_path = receipt_path

    # 文件标签登记（对齐 Agent：原始报告 tag=task_type；解析 JSON tag=REPORT_JSON）
    report_tag = report_tag_for_task(task_type)
    result_tag = FileTagName.REPORT_JSON
    if saved.report_path:
        try:
            register_file(
                skill_dir,
                path=saved.report_path,
                tag_name=report_tag,
                agent_name=AgentTag.DEPLOYMENT,
                task_id=task_id,
            )
        except Exception:
            pass
    if saved.result_path:
        try:
            register_file(
                skill_dir,
                path=saved.result_path,
                tag_name=result_tag,
                agent_name=AgentTag.DEPLOYMENT,
                parsed_path=str(saved.result_path),
                parsed_status="PARSED",
                task_id=task_id,
            )
        except Exception:
            pass

    receipt["tags"] = {
        "reportZip": report_tag,
        "resultJson": result_tag,
    }
    _save_json(receipt_path, receipt)

    _append_index(
        skill_dir,
        {
            "taskType": task_type,
            "taskName": task_name,
            "taskId": task_id,
            "workStage": work_stage,
            "dir": str(base),
            "reportPath": receipt["reportPath"],
            "reportTag": report_tag,
            "resultPath": receipt["resultPath"],
            "resultTag": result_tag if saved.result_path else "",
            "receiptPath": str(receipt_path),
            "finishedAt": finished_at,
        },
    )
    return saved


def _append_index(skill_dir: str | Path, entry: dict[str, Any]) -> None:
    idx_path = results_root(skill_dir) / "index.json"
    idx = _load_json(idx_path)
    runs = idx.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(entry)
    idx["schemaVersion"] = 1
    idx["runs"] = runs[-200:]
    idx["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_json(idx_path, idx)


def latest_run(skill_dir: str | Path, task_type: str | None = None) -> dict[str, Any]:
    idx = _load_json(results_root(skill_dir) / "index.json")
    runs = idx.get("runs")
    if not isinstance(runs, list):
        return {}
    for entry in reversed(runs):
        if not isinstance(entry, dict):
            continue
        if task_type is None or str(entry.get("taskType")) == task_type:
            return entry
    return {}
