"""
source_files · 上游实施计划文件目录（直接路径读取）。

上游模块产出《设备安装实施计划.xlsx》（双 Sheet：实施计划 + SN扫码表），
放在 DEVICE_INSTALL_SOURCE_ROOT；plan_receive 读取并解析。

优先级：
  1. 环境变量 DEVICE_INSTALL_SOURCE_ROOT
  2. 默认：<work_root>/ProjectData/Input/
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .dispatch_plan_parser import DISPATCH_PLAN_FILENAME, resolve_dispatch_plan_path

_DISPATCH_LABEL = "设备安装实施计划（上游交付）"


def get_source_dir(work_root: Path | str | None = None) -> Path:
    """源文件目录。环境变量优先；否则用工作区 ProjectData/Input/。"""
    raw = os.environ.get("DEVICE_INSTALL_SOURCE_ROOT", "").strip()
    if raw:
        return Path(raw).resolve()
    if work_root:
        return (Path(work_root) / "ProjectData" / "Input").resolve()
    from ..bridge import get_device_install_root
    return (get_device_install_root() / "ProjectData" / "Input").resolve()


def check_dispatch_plan(source_dir: Path | str | None = None, *, work_root: Path | str | None = None) -> dict[str, object]:
    """检查源目录是否已有《设备安装实施计划.xlsx》。"""
    src = Path(source_dir).resolve() if source_dir else get_source_dir(work_root)
    plan_path = resolve_dispatch_plan_path(src)
    ok = plan_path is not None
    return {
        "ok": ok,
        "source_dir": str(src),
        "filename": DISPATCH_PLAN_FILENAME,
        "path": str(plan_path) if plan_path else str(src / DISPATCH_PLAN_FILENAME),
        "label": _DISPATCH_LABEL,
        "missing": [] if ok else [DISPATCH_PLAN_FILENAME],
    }


def sync_dispatch_plan_to_input(source_dir: Path, input_dir: Path) -> str | None:
    """将源目录的实施计划复制到 Input/（同目录则仅校验）；返回同步后的文件名。"""
    check = check_dispatch_plan(source_dir)
    if not check["ok"]:
        missing = check["missing"]
        raise RuntimeError(
            f"上游实施计划未就绪（目录：{source_dir}）。缺少：{', '.join(missing)}。"
            f"请由上游模块产出 {DISPATCH_PLAN_FILENAME} 并放入 DEVICE_INSTALL_SOURCE_ROOT。"
        )

    src = source_dir.resolve()
    dest = input_dir.resolve()
    fname = DISPATCH_PLAN_FILENAME
    sp = src / fname
    if src != dest:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sp, dest / fname)
    return fname


# 兼容 files.check_project_files 等旧引用
SOURCE_FILES = {"dispatch_plan": DISPATCH_PLAN_FILENAME}


def check_source_files(source_dir: Path | str | None = None, *, work_root: Path | str | None = None) -> dict[str, object]:
    """兼容别名 → check_dispatch_plan（包装为 items 列表供 preflight 展示）。"""
    chk = check_dispatch_plan(source_dir, work_root=work_root)
    items = [{
        "key": "dispatch_plan",
        "label": _DISPATCH_LABEL,
        "filename": DISPATCH_PLAN_FILENAME,
        "path": chk["path"],
        "found": chk["ok"],
    }]
    return {
        "ok": chk["ok"],
        "source_dir": chk["source_dir"],
        "missing": chk["missing"],
        "items": items,
    }
