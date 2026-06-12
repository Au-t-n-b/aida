# -*- coding: utf-8 -*-
"""CloudOps 步骤 5～6 材料前置检查：缺件时生成可读的引导文案。"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Step6Preflight:
    ok: bool
    missing: list[str] = field(default_factory=list)
    manual_path: str = ""
    checklist_ok: bool = False
    checklist_source: str = ""
    cloudops_inbox: str = ""


def cloudops_input_dir(skill_dir: str) -> str:
    return os.path.join(os.path.abspath(skill_dir), "ProjectData", "input", "cloudops")


def preflight_step6(
    skill_dir: str,
    chain: dict[str, Any],
) -> Step6Preflight:
    """步骤 6 执行前：手工补充表 + 设备安装完工清单。"""
    from .checklist_to_full import resolve_manual_path

    root = Path(skill_dir).resolve()
    os.environ.setdefault("SD_SKILL_ROOT", str(root))
    rt = root / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from sd_script_import import import_sd_script  # noqa: WPS433

    probe_checklist = import_sd_script(root, "5_cloudops_supplement", "supplement").probe_checklist

    inbox = cloudops_input_dir(skill_dir)
    manual = resolve_manual_path(skill_dir, chain)
    checklist_ok, checklist_src = probe_checklist(skill_dir=skill_dir)

    missing: list[str] = []
    if not manual or not os.path.isfile(manual):
        missing.append(
            "**CloudOps 手工补充表**未找到。请先完成步骤 5 登记，或确认存在：\n"
            "   `plan/Output/CloudOps配置_手工补充.xlsx`"
        )
    if not checklist_ok:
        missing.append(
            "**设备安装完工清单**未找到。请上传或放入目录（文件名须含「完工清单」或「设备安装完工清单」）：\n"
            f"   `{inbox}`\n"
            "   亦可放在 `ProjectData/input/` 根目录；表头须含 **设备名称**、**ESN**（或 SN/序列号）。"
        )

    return Step6Preflight(
        ok=len(missing) == 0,
        missing=missing,
        manual_path=manual or "",
        checklist_ok=checklist_ok,
        checklist_source=checklist_src,
        cloudops_inbox=inbox,
    )


def format_missing_materials_context(pf: Step6Preflight, *, step_label: str = "步骤 6") -> str:
    lines = [
        f"⚠️ **{step_label} 前检查：材料未齐**",
        "",
        "补全下列项后，请点 **「重新检查」** 或上传卡 **「完成上传并继续」**：",
        "",
    ]
    for i, block in enumerate(pf.missing, 1):
        lines.append(f"{i}. {block}")
        lines.append("")
    if pf.checklist_ok and pf.checklist_source:
        lines.append(f"（完工清单已就绪：{pf.checklist_source}）")
    if pf.manual_path:
        lines.append(f"（手工表：`{pf.manual_path}`）")
    return "\n".join(lines).strip()
