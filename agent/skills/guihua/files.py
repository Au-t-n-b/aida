"""
guihua 文件补齐处理器（BaseSkill.file_handler 鸭子类型）。

比 zhgk 简单：只有一种上传 purpose「资料包 bundle」，统一落 ProjectData/Input/。
提供 main.py 文件端点需要的 4 个函数：
  infer_upload_kind / save_upload / check_need_files / check_project_files
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile

_BUNDLE_EXTS = {".xlsx", ".xls", ".csv", ".zip", ".pdf", ".doc", ".docx", ".md",
                ".stp", ".step", ".iges", ".stl", ".json", ".png", ".jpg", ".jpeg"}

# 建模仿真输出文件（随包样本）目录：SDUI OutputDocsGrid 的下载源。
_OUTPUT_FILES_DIR = (Path(__file__).parent / "vendor" / "jmfz" / "output_files").resolve()


def resolve_artifact_path(root: Path, path: str) -> Path:
    """SDUI 输出文件下载解析：把 OutputDocsGrid 卡片的 path（文件名）映射回随包样本目录。

    main.py `_resolve_skill_artifact_file` 会优先调用本钩子；命中即从 vendor 样本目录提供，
    未命中抛 FileNotFoundError，让其回退到 work_root/ProjectData 既有逻辑（不影响上传/RunTime 产物）。
    仅按文件名取，并用 relative_to 校验防止路径穿越。
    """
    name = Path((path or "").replace("\\", "/")).name
    if not name:
        raise FileNotFoundError(path)
    candidate = (_OUTPUT_FILES_DIR / name).resolve()
    try:
        candidate.relative_to(_OUTPUT_FILES_DIR)
    except ValueError as exc:
        raise FileNotFoundError(path) from exc
    if not candidate.is_file():
        raise FileNotFoundError(path)
    return candidate


def infer_upload_kind(filename: str) -> str:
    """guihua 只有一种 kind：bundle（落 Input/）。"""
    return "bundle"


async def save_upload(root: Path, kind: str, file: UploadFile) -> dict[str, Any]:
    dest_dir = root / "ProjectData" / "Input"
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = file.filename or f"bundle-{uuid.uuid4().hex[:8]}.bin"
    dest = dest_dir / fname
    content = await file.read()
    dest.write_bytes(content)
    return {
        "ok": True,
        "kind": "bundle",
        "filename": fname,
        "path": str(dest.relative_to(root)),
        "size": len(content),
    }


def _input_files(root: Path) -> list[Path]:
    idir = root / "ProjectData" / "Input"
    if not idir.exists():
        return []
    return [p for p in sorted(idir.glob("*")) if p.is_file() and p.suffix.lower() in _BUNDLE_EXTS]


def check_project_files(root: Path) -> dict[str, Any]:
    """默认前置集：Input/ 至少一个资料包文件。"""
    files = _input_files(root)
    ok = len(files) > 0
    return {
        "ok": ok,
        "found_count": 1 if ok else 0,
        "total": 1,
        "items": [{
            "id": "bundle",
            "label": "建模仿真资料包（设备信息表.md / 机房机柜信息表.xlsx）",
            "path": "ProjectData/Input/*",
            "hint": "放到 Input/；无上传则用内置样本离线生成适配表",
            "found": ok,
            "matched": str(files[0].relative_to(root)) if ok else None,
        }],
        "guihua_root": str(root),
    }


def check_need_files(root: Path, need_files: list[str]) -> dict[str, Any]:
    """按当前 HITL need_files 检查；guihua 的缺料统一是「Input 有无文件」。"""
    files = _input_files(root)
    ok = len(files) > 0
    items = [{
        "id": f"need-{i}",
        "label": Path(re.split(r"[（(]", raw)[0].strip()).name or raw,
        "path": raw,
        "hint": "上传资料包到 Input/（可多选）",
        "found": ok,
        "matched": str(files[0].relative_to(root)) if ok else None,
    } for i, raw in enumerate(need_files or ["ProjectData/Input/*"])]
    return {
        "ok": ok,
        "found_count": sum(1 for it in items if it["found"]),
        "total": len(items),
        "items": items,
        "guihua_root": str(root),
    }
