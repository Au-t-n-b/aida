"""
工勘 ProjectData 前置文件检查与上传路由（HITL 多文件补齐）。

v4 目录结构（与 path_config.py 保持一致）：
  ProjectData/
    Template/    ← 底表 / 模板（入场评估标准表、风险库、报告模板）—— FIXED_ITEMS
    Input/       ← 项目输入文件（BOQ、远近一体化人员信息）
    Output/      ← 步骤产物（全量结果表、问题清单、风险表、工勘报告）
    RunTime/     ← 中间状态快照
    Images/      ← 照片
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import UploadFile

# ── 固定模板文件（Template/）──────────────────────────────────────────────
# 与 path_config.get_base_table_path / get_risk_library_path / get_report_template_path 一致
FIXED_ITEMS: list[dict[str, str]] = [
    {
        "id": "base_table",
        "label": "入场评估标准表",
        "path": "ProjectData/Template/入场评估标准表.xlsx",
        "hint": "放到 Template/；filter_build HITL 自行上传（组织资产，不随项目 demo 打包）",
    },
    {
        "id": "risk_lib",
        "label": "工勘常见高风险库",
        "path": "ProjectData/Template/工勘常见高风险库.xlsx",
        "hint": "放到 Template/；filter_build HITL 自行上传（组织资产，不随项目 demo 打包）",
    },
]

# 报告模板为可选（缺失时 report_gen 使用内置默认模板）
OPTIONAL_ITEMS: list[dict[str, str]] = [
    {
        "id": "report_tpl",
        "label": "工勘报告模板（可选）",
        "path": "ProjectData/Template/新版项目工勘报告模板.docx",
        "hint": "放到 Template/；缺失时使用内置报告模板（需含 ≥9 个表格）",
    },
]

PERSONNEL_FILENAME = "远近一体化人员信息.xlsx"
PERSONNEL_REL = f"ProjectData/Input/{PERSONNEL_FILENAME}"

# GKCLAW 任务下发 · task_dispatch HITL（缺人员时 need_files 指向此路径）
GKCLAW_ASSIGNEES_REL = "ProjectData/RunTime/gkclaw/assignees.json"
GKCLAW_ASSIGNEES_FILENAME = "assignees.json"

BOQ_ITEM = {
    "id": "boq",
    "label": "BOQ 清单",
    "path": "ProjectData/Input/*BOQ*.xlsx",
    "hint": "放到 Input/，文件名须含 BOQ",
}

# wait_survey / 复勘 HITL 上传的规范落点名（与 wait_survey.UPLOADED_FILENAME 一致）
SURVEY_RESULT_FILENAME = "已填写_全量勘测结果表.xlsx"
SURVEY_RESULT_REL = f"ProjectData/Input/{SURVEY_RESULT_FILENAME}"


def infer_upload_kind(filename: str) -> str:
    """根据文件名推断 upload kind（v4 映射）。"""
    name = filename or ""
    if re.search(r"BOQ", name, re.I):
        return "boq"
    if re.search(r"assignees", name, re.I):
        return "gkclaw_assignees"
    if re.search(r"远近|人员信息|人员表|personnel", name, re.I):
        return "personnel"
    if "追加工勘项表" in name or "追加勘测条目" in name:
        return "extra_items"
    if re.search(r"全量勘测结果表|复勘结果表|勘测结果表|已填写", name, re.I):
        return "survey_result"
    if "入场评估标准" in name:
        return "template"
    if "工勘常见高风险库" in name or "风险库" in name:
        return "template"
    if "工勘报告模板" in name or "报告模板" in name:
        return "template"
    if re.search(r"\.(jpg|jpeg|png|bmp|webp|gif)$", name, re.I):
        return "image"
    # 通用 xlsx/docx 兜底到 Input/
    if re.search(r"\.(xlsx|xls|docx|doc)$", name, re.I):
        return "input"
    return "input"


def _normalize_need_pattern(path: str) -> str:
    """去掉 HITL 文案里的中文说明，保留 glob 路径。"""
    p = (path or "").strip()
    p = re.split(r"[（(]", p, maxsplit=1)[0].strip()
    return p.replace("\\", "/")


def _match_input_survey_result(root: Path, rel: str) -> tuple[bool, str | None]:
    """HITL 文案常无 .xlsx 后缀；匹配 Input 下勘测/复勘结果表。"""
    norm = rel.replace("\\", "/")
    if "/Input/" not in norm:
        return False, None
    stem = Path(_normalize_need_pattern(rel)).name
    if not any(k in stem for k in ("勘测结果表", "复勘结果表")):
        return False, None
    input_dir = root / "ProjectData" / "Input"
    if not input_dir.is_dir():
        return False, None

    candidates: list[Path] = []
    for name in (SURVEY_RESULT_FILENAME, f"{stem}.xlsx"):
        p = input_dir / name
        if p.is_file():
            candidates.append(p)
    for pattern in (f"{stem}*.xlsx", "*全量勘测结果表*.xlsx", "*复勘结果表*.xlsx", "*勘测结果表*.xlsx"):
        for p in sorted(input_dir.glob(pattern)):
            if "boq" in p.name.lower():
                continue
            if p.is_file() and p not in candidates:
                candidates.append(p)
    if not candidates:
        return False, None
    best = candidates[0]
    return True, str(best.relative_to(root))


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
    # HITL：ProjectData/Input/复勘结果表（无扩展名）→ 接受 *.xlsx
    ok, matched = _match_input_survey_result(root, rel)
    if ok:
        return ok, matched
    # 兼容 rel + .xlsx
    with_xlsx = root / f"{rel}.xlsx"
    if with_xlsx.is_file():
        return True, str(with_xlsx.relative_to(root))
    return False, None


def check_need_files(root: Path, need_files: list[str]) -> dict[str, Any]:
    """按当前 HITL 的 need_files 逐项检查（支持 glob）。"""
    items: list[dict[str, Any]] = []
    found_count = 0
    for i, raw in enumerate(need_files):
        rel = _normalize_need_pattern(raw)
        ok, matched = _match_need_path(root, raw)
        if ok:
            found_count += 1
        label = Path(rel).name if rel else raw
        hint = ""
        if not ok and "远近一体化人员信息" in raw:
            hint = f"将保存为 Input/{PERSONNEL_FILENAME}（本地文件名可不同）"
        elif not ok and "/Template/" in rel:
            hint = "请上传到 Template/（底表/模板文件）"
        elif not ok and "/Input/" in rel:
            if any(k in label for k in ("勘测结果表", "复勘结果表")):
                hint = f"上传 .xlsx 即可（将保存为 Input/{SURVEY_RESULT_FILENAME}）"
            else:
                hint = "请上传到 Input/"
        elif not ok and "assignees.json" in raw:
            hint = (
                "请上传 assignees.json 到 RunTime/gkclaw/；"
                '格式：[{"surveyor_name": "姓名", "surveyor_code": "工号"}]'
            )
        elif not ok and "/gkclaw/" in rel:
            hint = "请上传到 RunTime/gkclaw/"
        elif not ok and ("/RunTime/" in rel or "/Output/" in rel):
            hint = "由上一步自动生成；可点「继续工勘」重跑流程"
        items.append({
            "id": f"need-{i}",
            "label": label,
            "path": raw,
            "hint": hint,
            "found": ok,
            "matched": matched,
        })
    total = len(items)
    return {
        "ok": found_count == total if total else True,
        "found_count": found_count,
        "total": total,
        "items": items,
        "zhgk_root": str(root),
    }


def check_project_files(root: Path) -> dict[str, Any]:
    """扫描工作区，返回逐项齐备状态（Template/ 必选项 + BOQ + 可选报告模板）。"""
    items: list[dict[str, Any]] = []
    found_count = 0

    # 必选模板文件（Template/）
    for spec in FIXED_ITEMS:
        full = root / spec["path"]
        ok = full.is_file()
        if ok:
            found_count += 1
        items.append({
            **spec,
            "found": ok,
            "matched": str(full.relative_to(root)) if ok else None,
        })

    # BOQ（Input/ glob）
    input_dir = root / "ProjectData" / "Input"
    boq_files = list(input_dir.glob("*BOQ*.xlsx")) if input_dir.exists() else []
    boq_ok = len(boq_files) > 0
    if boq_ok:
        found_count += 1
    items.append({
        **BOQ_ITEM,
        "found": boq_ok,
        "matched": str(boq_files[0].relative_to(root)) if boq_ok else None,
    })

    # 可选报告模板（不计入 found_count 分母）
    for spec in OPTIONAL_ITEMS:
        full = root / spec["path"]
        ok = full.is_file()
        items.append({
            **spec,
            "found": ok,
            "matched": str(full.relative_to(root)) if ok else None,
            "optional": True,
        })

    total = len(FIXED_ITEMS) + 1  # 必选项：base_table + risk_lib + BOQ
    return {
        "ok": found_count == total,
        "found_count": found_count,
        "total": total,
        "items": items,
        "zhgk_root": str(root),
    }


async def save_upload(root: Path, kind: str, file: UploadFile) -> dict[str, Any]:
    """单文件落盘（v4 路径映射）。"""
    import uuid

    if kind == "boq":
        dest_dir = root / "ProjectData" / "Input"
        fname = file.filename or "uploaded_BOQ.xlsx"
        if "BOQ" not in fname:
            fname = f"BOQ-{fname}"
    elif kind == "template":
        # 底表 / 模板文件统一存到 Template/；固定底表名归一化，供 step 精确检查。
        dest_dir = root / "ProjectData" / "Template"
        fname = file.filename or "uploaded_template.xlsx"
        if "入场评估标准" in fname:
            fname = "入场评估标准表.xlsx"
        elif "工勘常见高风险库" in fname or "风险库" in fname:
            fname = "工勘常见高风险库.xlsx"
    elif kind == "image":
        dest_dir = root / "ProjectData" / "Images"
        fname = file.filename or f"img-{uuid.uuid4().hex[:8]}.jpg"
    elif kind == "personnel":
        dest_dir = root / "ProjectData" / "Input"
        fname = PERSONNEL_FILENAME
    elif kind == "gkclaw_assignees":
        dest_dir = root / "ProjectData" / "RunTime" / "gkclaw"
        fname = GKCLAW_ASSIGNEES_FILENAME
    elif kind == "extra_items":
        dest_dir = root / "ProjectData" / "Input"
        fname = "追加工勘项表.xlsx"
    elif kind == "survey_result":
        dest_dir = root / "ProjectData" / "Input"
        fname = SURVEY_RESULT_FILENAME
    elif kind == "input":
        dest_dir = root / "ProjectData" / "Input"
        fname = file.filename or "uploaded.xlsx"
    else:
        raise ValueError(
            f"unknown kind: {kind!r}（已知 kind: boq / template / image / personnel / gkclaw_assignees / extra_items / survey_result / input）"
        )

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
