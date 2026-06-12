# -*- coding: utf-8 -*-
"""项目文件登记表（本地版，模拟 CPCIA `project_file_info` 表）。

MVP 用 JSON 落盘：`ProjectData/plan/RunTime/file_index.json`。
对接数据库时，把 `register_file` / `query_by_tag` 换成 `project_file_info_db`
的 `insert_project_file_info` / `query_project_file_info_by_agent_name_tag`，
字段名与 Agent 对齐，调用方不变。

每条记录字段（对齐 Agent insert_project_file_info）：
    tag_name      文件标签（见 file_tags.FileTagName）
    agent_name    来源 Agent（见 file_tags.AgentTag）
    filename      文件名
    file_path     绝对/相对路径（MVP 用绝对）
    parsed_path   解析产物路径（缺省空）
    parsed_status NOT_PARSED / PARSED
    status        ACTIVE / INACTIVE
    doc_id        文档 id（MVP 用相对路径作占位）
    task_id       关联任务（结果文件用，可空）
    registered_at UTC ISO
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from .file_tags import AgentTag, FileTagName, infer_tag_from_filename
except ImportError:
    from file_tags import AgentTag, FileTagName, infer_tag_from_filename  # type: ignore


def _index_path(skill_dir: str | Path) -> Path:
    return Path(skill_dir).resolve() / "ProjectData" / "plan" / "RunTime" / "file_index.json"


def _skill_root(skill_dir: str | Path) -> Path:
    return Path(skill_dir).resolve()


def _rel_doc_id(skill_dir: str | Path, path: Path) -> str:
    """以 skill 根为基准的相对路径，作为 MVP 的 doc_id 占位。"""
    try:
        return path.resolve().relative_to(_skill_root(skill_dir)).as_posix()
    except Exception:
        return path.name


def _load(skill_dir: str | Path) -> dict[str, Any]:
    p = _index_path(skill_dir)
    if not p.is_file():
        return {"schemaVersion": 1, "files": []}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("files"), list):
            return raw
    except Exception:
        pass
    return {"schemaVersion": 1, "files": []}


def _save(skill_dir: str | Path, data: dict[str, Any]) -> None:
    p = _index_path(skill_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register_file(
    skill_dir: str | Path,
    *,
    path: str | Path,
    tag_name: str,
    agent_name: str = AgentTag.DEPLOYMENT,
    parsed_path: str = "",
    parsed_status: str = "NOT_PARSED",
    status: str = "ACTIVE",
    task_id: str = "",
) -> dict[str, Any]:
    """登记一个文件（同 path+tag 视为同条，更新 registered_at 并置最新）。"""
    fpath = Path(path)
    doc_id = _rel_doc_id(skill_dir, fpath)
    entry = {
        "tag_name": str(tag_name or FileTagName.DEFAULT),
        "agent_name": str(agent_name or AgentTag.DEPLOYMENT),
        "filename": fpath.name,
        "file_path": str(fpath),
        "parsed_path": str(parsed_path or ""),
        "parsed_status": str(parsed_status or "NOT_PARSED"),
        "status": str(status or "ACTIVE"),
        "doc_id": doc_id,
        "task_id": str(task_id or ""),
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    data = _load(skill_dir)
    files = data["files"]
    # 旧的同 doc_id+tag 记录置 INACTIVE（保留历史），新记录追加。
    for old in files:
        if isinstance(old, dict) and old.get("doc_id") == doc_id and old.get("tag_name") == entry["tag_name"]:
            old["status"] = "INACTIVE"
    files.append(entry)
    _save(skill_dir, data)
    return entry


def register_file_auto_tag(
    skill_dir: str | Path,
    *,
    path: str | Path,
    agent_name: str = AgentTag.DEPLOYMENT,
    **kwargs: Any,
) -> dict[str, Any]:
    """按文件名推断标签后登记。"""
    tag = infer_tag_from_filename(Path(path).name)
    return register_file(skill_dir, path=path, tag_name=tag, agent_name=agent_name, **kwargs)


def query_by_tag(
    skill_dir: str | Path,
    tag_name: str,
    *,
    agent_name: str | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    data = _load(skill_dir)
    out: list[dict[str, Any]] = []
    for item in data.get("files", []):
        if not isinstance(item, dict):
            continue
        if item.get("tag_name") != tag_name:
            continue
        if agent_name is not None and item.get("agent_name") != agent_name:
            continue
        if active_only and item.get("status") != "ACTIVE":
            continue
        out.append(item)
    return out


def latest_by_tag(skill_dir: str | Path, tag_name: str, **kwargs: Any) -> dict[str, Any]:
    rows = query_by_tag(skill_dir, tag_name, **kwargs)
    return rows[-1] if rows else {}


def list_all(skill_dir: str | Path, *, active_only: bool = False) -> list[dict[str, Any]]:
    data = _load(skill_dir)
    rows = [f for f in data.get("files", []) if isinstance(f, dict)]
    if active_only:
        rows = [f for f in rows if f.get("status") == "ACTIVE"]
    return rows


# 默认扫描目录与对应来源 Agent（相对 skill 根）。
_SCAN_DIRS: list[tuple[str, str]] = [
    ("ProjectData/input/plan_receive", AgentTag.DEPLOYMENT),
    ("ProjectData/input/plan_split", AgentTag.DEPLOYMENT),
    ("ProjectData/input/plan_dispatch", AgentTag.DESIGN),
    ("ProjectData/input/cloudops", AgentTag.DEPLOYMENT),
    ("ProjectData/plan/Output", AgentTag.DEPLOYMENT),
]

_SCAN_EXTS = {".xlsx", ".xls", ".docx", ".zip", ".json", ".csv"}


def scan_and_register_existing(
    skill_dir: str | Path,
    *,
    dirs: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """按文件名规则批量登记已存在的上传/产物文件（补登历史，全量对齐用）。

    幂等：同 doc_id+tag 已 ACTIVE 则跳过，不重复追加。
    """
    root = _skill_root(skill_dir)
    targets = dirs or _SCAN_DIRS
    existing = {
        (r.get("doc_id"), r.get("tag_name"))
        for r in list_all(skill_dir, active_only=True)
    }
    registered: list[dict[str, Any]] = []
    for rel, agent in targets:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if not path.is_file() or path.suffix.lower() not in _SCAN_EXTS:
                continue
            tag = infer_tag_from_filename(path.name)
            doc_id = _rel_doc_id(skill_dir, path)
            if (doc_id, tag) in existing:
                continue
            entry = register_file(skill_dir, path=path, tag_name=tag, agent_name=agent)
            registered.append(entry)
            existing.add((doc_id, tag))
    return registered
