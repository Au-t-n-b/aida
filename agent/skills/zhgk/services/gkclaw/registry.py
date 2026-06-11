"""
gkclaw registry · 任务状态机 + 包级幂等账本（契约 §5/§20）

文件存储（真相位置）：<runtime_dir>/gkclaw/<task_id>/{state.json,packages.json,...}
单写者假设（uvicorn workers=1）；写入走 临时文件+os.replace 原子替换。

状态机（v1 简化：无 App 事件通道，不单独维护 in_progress）：
  planned → dispatched → accepted → staged_returned → completed
  任意 → failed / superseded；包级异常 → 隔离（任务状态不动）
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATES = ("planned", "dispatched", "accepted", "staged_returned",
          "completed", "failed", "superseded")
DISPOSITIONS = ("processed", "duplicate", "conflict", "quarantine", "archived", "ignored")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def decide_inbound(
    task: dict[str, Any] | None,
    known_packages: list[dict[str, Any]],
    *,
    package_type: str,
    package_id: str,
    checksum: str,
    session_status: str,
) -> tuple[str, str]:
    """纯函数：入站包处置判定（契约 §20 矩阵）。返回 (disposition, note)。"""
    if task is None:
        return "quarantine", "未知 task_id：本地无此任务，留档不创建（契约 §7）"
    for p in known_packages:
        if p.get("package_id") == package_id:
            if p.get("checksum") == checksum:
                return "duplicate", "同 package_id 同 checksum：幂等成功"
            return "conflict", "同 package_id 异 checksum：包冲突，隔离"
    if task.get("state") == "superseded":
        return "archived", "任务已被取代（superseded）：仅留档，不合并不推进"

    if package_type == "task.import_ack":
        if task.get("state") == "completed":
            return "archived", "任务已完成后收到 ACK：留档"
        return "processed", ""
    if package_type == "task.result":
        is_final = session_status == "completed"
        if task.get("state") == "completed":
            if is_final:
                return "conflict", "final 后收到异内容 final：冲突，隔离"
            return "quarantine", "final 后收到阶段性结果：隔离（契约 §20）"
        return "processed", ""
    if package_type == "task.error":
        return "processed", ""
    return "quarantine", f"未知包类型 {package_type}"


class TaskRegistry:
    """任务/包/扫描三本账的文件持久层。"""

    def __init__(self, runtime_dir: Path | str):
        self.root = Path(runtime_dir) / "gkclaw"
        self.root.mkdir(parents=True, exist_ok=True)

    # ── 任务 ──

    def _dir(self, task_id: str) -> Path:
        return self.root / task_id

    def _state_file(self, task_id: str) -> Path:
        return self._dir(task_id) / "state.json"

    def create_task(self, *, task_id: str, task_payload: dict, zip_path: str,
                    table_fingerprint: str, project: dict,
                    dry_run: bool = False, **extra: Any) -> dict:
        d = self._dir(task_id)
        (d / "outbox").mkdir(parents=True, exist_ok=True)
        _atomic_write(d / "task.json", task_payload)
        task = {
            "task_id": task_id,
            "state": "planned",
            "project": dict(project or {}),
            "task_name": task_payload.get("task_name", ""),
            "assignees": task_payload.get("assignees", []),
            "zip_path": zip_path,
            "table_fingerprint": table_fingerprint,
            "dry_run": bool(dry_run),
            "web_access_url": "",
            "result_versions": 0,
            "final_result": "",
            "last_error": "",
            "created_at": _now(),
            "updated_at": _now(),
        }
        task.update(extra)
        _atomic_write(self._state_file(task_id), task)
        _atomic_write(d / "packages.json", [])
        return task

    def get(self, task_id: str) -> dict | None:
        f = self._state_file(task_id)
        if not f.exists():
            return None
        return json.loads(f.read_text(encoding="utf-8"))

    def task_payload(self, task_id: str) -> dict | None:
        f = self._dir(task_id) / "task.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def list_tasks(self) -> list[dict]:
        out = []
        for d in sorted(self.root.iterdir()):
            if d.is_dir() and not d.name.startswith("_") and (d / "state.json").exists():
                out.append(json.loads((d / "state.json").read_text(encoding="utf-8")))
        return out

    def save(self, task: dict) -> None:
        task["updated_at"] = _now()
        _atomic_write(self._state_file(task["task_id"]), task)

    def set_state(self, task_id: str, state: str, **extra: Any) -> dict:
        assert state in STATES, f"非法状态 {state}"
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"任务不存在: {task_id}")
        task["state"] = state
        task.update(extra)
        self.save(task)
        return task

    def mark_superseded(self, task_id: str) -> None:
        if self.get(task_id) is not None:
            self.set_state(task_id, "superseded")

    # ── 包账本 ──

    def packages(self, task_id: str) -> list[dict]:
        f = self._dir(task_id) / "packages.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

    def record_package(self, task_id: str, entry: dict) -> None:
        self._dir(task_id).mkdir(parents=True, exist_ok=True)
        entries = self.packages(task_id)
        entries.append({**entry, "at": _now()})
        _atomic_write(self._dir(task_id) / "packages.json", entries)

    # ── 结果版本与备注留档 ──

    def store_result_version(self, task_id: str, payload: dict, *, final: bool) -> Path:
        d = self._dir(task_id) / "results"
        d.mkdir(parents=True, exist_ok=True)
        task = self.get(task_id)
        n = int(task.get("result_versions", 0)) + 1
        p = d / f"result-{n:03d}.json"
        _atomic_write(p, payload)
        task["result_versions"] = n
        if final:
            task["final_result"] = f"results/{p.name}"
        self.save(task)
        return p

    def append_result_notes(self, task_id: str, notes: list[dict]) -> None:
        f = self._dir(task_id) / "result-notes.json"
        existing = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
        existing.extend(notes)
        _atomic_write(f, existing)

    def read_result_notes(self, task_id: str) -> list[dict]:
        f = self._dir(task_id) / "result-notes.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

    # ── 隔离区与扫描账本 ──

    def quarantine_dir(self) -> Path:
        d = self.root / "_quarantine"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _scan_file(self) -> Path:
        return self.root / "mail_scan.json"

    def scanned_mail_ids(self) -> set[int]:
        f = self._scan_file()
        if not f.exists():
            return set()
        return {int(k) for k in json.loads(f.read_text(encoding="utf-8"))}

    def mark_mail_scanned(self, mail_id: int, verdict: str) -> None:
        f = self._scan_file()
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        data[str(mail_id)] = {"verdict": verdict, "at": _now()}
        _atomic_write(f, data)
