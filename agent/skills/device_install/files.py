"""
device_install 文件处理器（BaseSkill.file_handler 鸭子类型）。

数据中心 API 化后：
  - 上游三表读取 / 产物写出统一走 dc_io（语义寻址，DC 不可达降级挂载盘）。
  - 产物预览/下载（resolve_artifact_path）：scratch → DC → 挂载盘，按文件名解析逻辑键。
  - 现场照片 / HITL 文件：上传到共享 scratch 上传区（run 内 fetch 会扫描）。
  - merge_run_patch（/run-patch · 见 run_patch.py）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from . import dc_io, dc_paths


def resolve_artifact_path(work_root: Path, path: str) -> Path:
    """产物预览/下载路径解析：按逻辑键文件名经 dc_io（scratch→DC→挂载盘）取本地文件。

    projectId 由 dc_io 经 `resolve_project_id` 从容器 env `AIDA_PROJECT_ID` 解析——
    生产一容器一项目，env 即当前项目（Manager 经 runtime-context 注入）。
    `/artifact` 是泛化端点（固定签名 skill+path），不逐请求透传 project（不破坏泛化分发）。
    """
    name = dc_paths.artifact_key_name(path or "")
    if not name:
        raise FileNotFoundError(path)
    hit = dc_io.fetch_output_by_name(work_root, name)
    if hit and hit.is_file():
        return hit.resolve()
    raise FileNotFoundError(path)


def infer_upload_kind(filename: str) -> str:
    """根据文件名推断 upload kind。"""
    name = filename or ""
    if re.search(r"\.(jpg|jpeg|png|bmp|webp|gif)$", name, re.I):
        return "image"
    return "input"


def _normalize_need_pattern(path: str) -> str:
    p = (path or "").strip()
    p = re.split(r"[（(]", p, maxsplit=1)[0].strip()
    return p.replace("\\", "/")


def check_need_files(root: Path, need_files: list[str]) -> dict[str, Any]:
    """按 HITL need_files 逐项检查（取文件名在共享上传区是否就绪）。"""
    inbox = dc_io.shared_uploads_dir(root, "inbox")
    items: list[dict[str, Any]] = []
    found_count = 0
    for i, raw in enumerate(need_files):
        rel = _normalize_need_pattern(raw)
        name = Path(rel).name if rel else raw
        ok = bool(name) and (inbox / name).is_file()
        if ok:
            found_count += 1
        items.append({
            "id": f"need-{i}",
            "label": name,
            "path": raw,
            "hint": "" if ok else "请上传该文件",
            "found": ok,
            "matched": name if ok else None,
        })
    total = len(items)
    return {
        "ok": found_count == total if total else True,
        "found_count": found_count,
        "total": total,
        "items": items,
        "device_install_root": str(root),
    }


def check_project_files(root: Path) -> dict[str, Any]:
    """扫描上游三份输入表是否已在数据中心 / 挂载盘就绪（只读）。

    projectId 经 dc_io 从容器 env `AIDA_PROJECT_ID` 解析（一容器一项目 · runtime-context 注入）。
    `/files/check` 为泛化端点（固定签名），不逐请求透传 project。
    """
    checks = [
        ("delivery_plan", "交付计划表", dc_paths.delivery_plan_loc(), ("交付计划", "delivery")),
        ("position_table", "设备位置表", dc_paths.position_loc(), ("设备位置", "位置表", "position")),
        ("arrival_table", "到货信息表", dc_paths.arrival_loc(), ("到货",)),
    ]
    items: list[dict[str, Any]] = []
    for i, (_key, label, loc, keywords) in enumerate(checks):
        found, where = dc_io.upstream_exists(loc, None, keywords=keywords)
        items.append({
            "id": f"upstream-{i}",
            "label": label,
            "path": where,
            "hint": "" if found else "请由上游模块交付至该位置",
            "found": found,
            "matched": where if found else None,
        })
    found_count = sum(1 for item in items if item["found"])
    return {
        "ok": found_count == len(items),
        "found_count": found_count,
        "total": len(items),
        "items": items,
        "device_install_root": str(root),
    }


def reset_workspace(root: Path) -> dict[str, Any]:
    """重置会话：清空本地 scratch 运行态与产物（保留共享上传区）+ 挂载盘降级产物。

    上游数据在数据中心（不受影响）；DC 无删除接口，产物以重传覆盖。
    """
    root = Path(root).resolve()
    removed: list[str] = []

    # 各 run 的 scratch out/state/images
    for run_dir in root.glob("*"):
        if not run_dir.is_dir() or run_dir.name == "_uploads" or run_dir.name == "_preview":
            continue
        removed.extend(
            dc_io.clear_run_scratch(root, run_dir.name, subdirs=("out", "state", "images"))
        )

    # 预览缓存
    preview = root / "_preview"
    if preview.is_dir():
        for p in list(preview.iterdir()):
            if p.is_file():
                try:
                    p.unlink()
                    removed.append(p.name)
                except OSError:
                    pass

    # 挂载盘降级产物目录
    disk_out = dc_paths.install_output_loc().disk_dir()
    if disk_out.is_dir():
        for p in list(disk_out.iterdir()):
            if p.is_file() and not p.name.startswith("~$"):
                try:
                    p.unlink()
                    removed.append(p.name)
                except OSError:
                    pass

    return {
        "ok": True,
        "removed_count": len(removed),
        "removed": removed,
        "message": "已清空运行态与产物（上游数据保留在数据中心），可重新启动主建设流程。",
    }


async def save_upload(root: Path, kind: str, file: UploadFile) -> dict[str, Any]:
    """单文件落盘到共享 scratch 上传区：图片 → images/；其余 → inbox/。"""
    import uuid

    if kind == "image":
        dest_dir = dc_io.shared_uploads_dir(root, "images")
        fname = file.filename or f"img-{uuid.uuid4().hex[:8]}.jpg"
    else:
        dest_dir = dc_io.shared_uploads_dir(root, "inbox")
        fname = file.filename or "uploaded.xlsx"

    dest = dest_dir / fname
    content = await file.read()
    dest.write_bytes(content)
    return {
        "ok": True,
        "kind": kind,
        "filename": fname,
        "path": str(dest),
        "size": len(content),
    }


def merge_run_patch(root: Path, run_state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """AIDA 通用 /run-patch 入口 · 实现见 run_patch.py。"""
    from .run_patch import merge_run_patch as _impl
    return _impl(root, run_state, payload)
