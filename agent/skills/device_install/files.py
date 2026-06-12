"""
device_install 文件处理器（BaseSkill.file_handler 鸭子类型）。

主流程由 plan_receive 从源文件目录（DEVICE_INSTALL_SOURCE_ROOT）读取上游《设备安装实施计划》；业务编辑走 EditableTable。
本模块提供：
  - 现场照片上传（Images/）
  - 遗留 file_handler 端点兼容（/upload · /files/check）
  - merge_run_patch（/run-patch · 任务进展改百分比等不重跑流水线的补丁，见 run_patch.py）
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import UploadFile


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


def _match_need_path(root: Path, pattern: str) -> tuple[bool, str | None]:
    rel = _normalize_need_pattern(pattern)
    if not rel:
        return False, None
    if "*" in rel:
        matches = sorted(root.glob(rel))
        if matches:
            return True, str(matches[0].relative_to(root))
        return False, None
    full = root / rel
    if full.is_file():
        return True, str(full.relative_to(root))
    return False, None


def check_need_files(root: Path, need_files: list[str]) -> dict[str, Any]:
    """按 HITL need_files 逐项检查（支持 glob）。"""
    items: list[dict[str, Any]] = []
    found_count = 0
    for i, raw in enumerate(need_files):
        rel = _normalize_need_pattern(raw)
        ok, matched = _match_need_path(root, raw)
        if ok:
            found_count += 1
        label = Path(rel).name if rel else raw
        items.append({
            "id": f"need-{i}",
            "label": label,
            "path": raw,
            "hint": "" if ok else "请上传到 Input/",
            "found": ok,
            "matched": matched,
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
    """扫描工作区：检查源文件目录是否已有上游《设备安装实施计划》。"""
    from .services.source_files import check_dispatch_plan, get_source_dir
    from .services.dispatch_plan_parser import DISPATCH_PLAN_FILENAME

    input_dir = root / "ProjectData" / "Input"
    source_dir = get_source_dir(root)
    src = check_dispatch_plan(source_dir)
    items: list[dict[str, Any]] = [{
        "id": "src-dispatch_plan",
        "label": f"源目录·{src.get('label', DISPATCH_PLAN_FILENAME)}",
        "path": str(src.get("path", "")),
        "hint": "" if src.get("ok") else "请由上游模块产出并放入源文件目录",
        "found": bool(src.get("ok")),
        "matched": DISPATCH_PLAN_FILENAME if src.get("ok") else None,
    }]

    inp_matches = list(input_dir.glob(DISPATCH_PLAN_FILENAME)) if input_dir.exists() else []
    items.append({
        "id": "input-dispatch_plan",
        "label": f"Input·{DISPATCH_PLAN_FILENAME}",
        "path": f"ProjectData/Input/{DISPATCH_PLAN_FILENAME}",
        "hint": "" if inp_matches else "启动后 plan_receive 将从源目录同步",
        "found": bool(inp_matches),
        "matched": str(inp_matches[0].relative_to(root)) if inp_matches else None,
    })

    found_count = sum(1 for item in items if item["found"])
    return {
        "ok": bool(src.get("ok")),
        "found_count": found_count,
        "total": len(items),
        "items": items,
        "device_install_root": str(root),
        "source_dir": src.get("source_dir", ""),
    }


def reset_workspace(root: Path) -> dict[str, Any]:
    """重置会话：清空工作区运行态与产物，保留 Input/ 输入文件。

    清除 ProjectData 下 Output / RunTime / Start / Images；Input/ 不动。
    上游源目录 DEVICE_INSTALL_SOURCE_ROOT 不在 work_root 内，不受影响。
    """
    root = Path(root).resolve()
    pd = root / "ProjectData"
    removed: list[str] = []

    def _clear_dir(rel: str) -> None:
        d = pd / rel
        if not d.is_dir():
            return
        for p in list(d.iterdir()):
            if p.is_file() and not p.name.startswith("~$"):
                try:
                    p.unlink()
                    removed.append(str(p.relative_to(root)))
                except OSError:
                    pass

    for sub in ("Output", "RunTime", "Start", "Images"):
        _clear_dir(sub)

    # 输出目录被 DEVICE_INSTALL_OUTPUT_ROOT 外置（服务器/数据中心落点，
    # 不在 ProjectData/Output 内）时，单独清理其中的产物文件。
    from .path_config import get_output_dir
    out_dir = get_output_dir().resolve()
    if out_dir != (pd / "Output").resolve() and out_dir.is_dir():
        for p in list(out_dir.iterdir()):
            if p.is_file() and not p.name.startswith("~$"):
                try:
                    p.unlink()
                    try:
                        rel = str(p.relative_to(root))
                    except ValueError:
                        rel = str(p)
                    removed.append(rel)
                except OSError:
                    pass

    return {
        "ok": True,
        "removed_count": len(removed),
        "removed": removed,
        "message": "已清空运行态与产物（Input 已保留），可重新启动主建设流程。",
    }


async def save_upload(root: Path, kind: str, file: UploadFile) -> dict[str, Any]:
    """单文件落盘：图片 → Images/；其余 → Input/。"""
    import uuid

    if kind == "image":
        dest_dir = root / "ProjectData" / "Images"
        fname = file.filename or f"img-{uuid.uuid4().hex[:8]}.jpg"
    else:
        dest_dir = root / "ProjectData" / "Input"
        fname = file.filename or "uploaded.xlsx"

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / fname
    content = await file.read()
    dest.write_bytes(content)
    return {
        "ok": True,
        "kind": kind,
        "filename": fname,
        "path": str(dest.relative_to(root)),
        "size": len(content),
    }


def merge_run_patch(root: Path, run_state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """AIDA 通用 /run-patch 入口 · 实现见 run_patch.py。"""
    from .run_patch import merge_run_patch as _impl
    return _impl(root, run_state, payload)
