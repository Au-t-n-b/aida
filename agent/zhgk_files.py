"""
工勘前置文件检查与上传路由（HITL 多文件补齐）。

v5 标准目录结构:
  {AIDA_BUSINESS_ROOT}/project/交付作业/智慧工勘/
    输入文件/     ← BOQ、人员信息、勘测结果表
    解析结果/     ← 中间状态（gkclaw 等）
    输出结果/     ← 步骤产物
  {AIDA_BUSINESS_ROOT}/org-assets/
    入场评估标准表.xlsx / 工勘常见高风险库.xlsx / 新版项目工勘报告模板.docx
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from agent.skills.zhgk.path_config import (
    get_base_table_path,
    get_risk_library_path,
    get_report_template_path,
)

# ── 固定模板文件（org-assets/，绝对路径校验）──────────────────────────────────
FIXED_ITEMS: list[dict[str, str]] = [
    {
        "id": "base_table",
        "label": "入场评估标准表",
        "path": "org-assets/入场评估标准表.xlsx",
        "hint": "组织资产；filter_build HITL 自行上传",
    },
    {
        "id": "risk_lib",
        "label": "工勘常见高风险库",
        "path": "org-assets/工勘常见高风险库.xlsx",
        "hint": "组织资产；filter_build HITL 自行上传",
    },
]

OPTIONAL_ITEMS: list[dict[str, str]] = [
    {
        "id": "report_tpl",
        "label": "工勘报告模板（可选）",
        "path": "org-assets/新版项目工勘报告模板.docx",
        "hint": "缺失时使用内置报告模板（需含 ≥9 个表格）",
    },
]

PERSONNEL_FILENAME = "远近一体化人员信息.xlsx"
PERSONNEL_REL = f"输入文件/{PERSONNEL_FILENAME}"

GKCLAW_ASSIGNEES_REL = "解析结果/gkclaw/assignees.json"
GKCLAW_ASSIGNEES_FILENAME = "assignees.json"

BOQ_ITEM = {
    "id": "boq",
    "label": "BOQ 清单",
    "path": "输入文件/*BOQ*.xlsx",
    "hint": "放到 输入文件/，文件名须含 BOQ",
}

SURVEY_RESULT_FILENAME = "已填写_全量勘测结果表.xlsx"
SURVEY_RESULT_REL = f"输入文件/{SURVEY_RESULT_FILENAME}"


def infer_upload_kind(filename: str) -> str:
    """根据文件名推断 upload kind。"""
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
    if re.search(r"\.(xlsx|xls|docx|doc)$", name, re.I):
        return "input"
    return "input"


def _normalize_need_pattern(path: str) -> str:
    p = (path or "").strip()
    p = re.split(r"[（(]", p, maxsplit=1)[0].strip()
    return p.replace("\\", "/")


def _match_input_survey_result(root: Path, rel: str) -> tuple[bool, str | None]:
    norm = rel.replace("\\", "/")
    if "/输入文件/" not in norm and "/Input/" not in norm:
        return False, None
    stem = Path(_normalize_need_pattern(rel)).name
    if not any(k in stem for k in ("勘测结果表", "复勘结果表")):
        return False, None
    input_dir = root / "输入文件"
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

    # org-assets 模板用绝对路径校验
    if rel.startswith("org-assets/"):
        from agent.skills.zhgk.bridge import get_org_assets_root
        abs_path = get_org_assets_root() / rel.split("org-assets/", 1)[1]
        if abs_path.is_file():
            return True, rel
        return False, None

    if "*" in rel:
        matches = sorted(root.glob(rel))
        if matches:
            return True, str(matches[0].relative_to(root))
        return False, None
    full = root / rel
    if full.is_file():
        return True, str(full.relative_to(root))
    ok, matched = _match_input_survey_result(root, rel)
    if ok:
        return ok, matched
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
            hint = f"将保存为 输入文件/{PERSONNEL_FILENAME}（本地文件名可不同）"
        elif not ok and "org-assets/" in rel:
            hint = "请上传（组织资产 / 底表 / 模板文件）"
        elif not ok and "/输入文件/" in rel:
            if any(k in label for k in ("勘测结果表", "复勘结果表")):
                hint = f"上传 .xlsx 即可（将保存为 输入文件/{SURVEY_RESULT_FILENAME}）"
            else:
                hint = "请上传到 输入文件/"
        elif not ok and "assignees.json" in raw:
            hint = (
                "请上传 assignees.json 到 解析结果/gkclaw/；"
                '格式：[{"surveyor_name": "姓名", "surveyor_code": "工号"}]'
            )
        elif not ok and "/gkclaw/" in rel:
            hint = "请上传到 解析结果/gkclaw/"
        elif not ok and ("/解析结果/" in rel or "/输出结果/" in rel):
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
    """扫描工作区，返回逐项齐备状态。模板项用绝对路径校验 org-assets/。"""
    items: list[dict[str, Any]] = []
    found_count = 0

    # 必选模板（org-assets/ 绝对路径）
    _template_checks = [
        ("base_table", "入场评估标准表", get_base_table_path()),
        ("risk_lib", "工勘常见高风险库", get_risk_library_path()),
    ]
    for item_id, label, abs_path in _template_checks:
        ok = Path(abs_path).is_file()
        if ok:
            found_count += 1
        items.append({
            "id": item_id,
            "label": label,
            "path": abs_path,
            "hint": "组织资产；filter_build HITL 自行上传",
            "found": ok,
            "matched": abs_path if ok else None,
        })

    # BOQ（输入文件/ glob）
    input_dir = root / "输入文件"
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
    report_tpl_path = get_report_template_path()
    ok = Path(report_tpl_path).is_file()
    items.append({
        "id": "report_tpl",
        "label": "工勘报告模板（可选）",
        "path": report_tpl_path,
        "hint": "缺失时使用内置报告模板（需含 ≥9 个表格）",
        "found": ok,
        "matched": report_tpl_path if ok else None,
        "optional": True,
    })

    total = len(_template_checks) + 1  # 必选：base_table + risk_lib + BOQ
    return {
        "ok": found_count == total,
        "found_count": found_count,
        "total": total,
        "items": items,
        "zhgk_root": str(root),
    }


async def save_upload(root: Path, kind: str, file: UploadFile) -> dict[str, Any]:
    """单文件落盘（标准路径映射）。"""
    import uuid
    from agent.skills.zhgk.bridge import get_org_assets_root

    if kind == "boq":
        dest_dir = root / "输入文件"
        fname = file.filename or "uploaded_BOQ.xlsx"
        if "BOQ" not in fname:
            fname = f"BOQ-{fname}"
    elif kind == "template":
        dest_dir = get_org_assets_root()
        fname = file.filename or "uploaded_template.xlsx"
        if "入场评估标准" in fname:
            fname = "入场评估标准表.xlsx"
        elif "工勘常见高风险库" in fname or "风险库" in fname:
            fname = "工勘常见高风险库.xlsx"
    elif kind == "image":
        dest_dir = root / "输入文件" / "勘测图片文件夹"
        fname = file.filename or f"img-{uuid.uuid4().hex[:8]}.jpg"
    elif kind == "personnel":
        dest_dir = root / "输入文件"
        fname = PERSONNEL_FILENAME
    elif kind == "gkclaw_assignees":
        dest_dir = root / "解析结果" / "gkclaw"
        fname = GKCLAW_ASSIGNEES_FILENAME
    elif kind == "extra_items":
        dest_dir = root / "输入文件"
        fname = "追加工勘项表.xlsx"
    elif kind == "survey_result":
        dest_dir = root / "输入文件"
        fname = SURVEY_RESULT_FILENAME
    elif kind == "input":
        dest_dir = root / "输入文件"
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
        "path": str(dest.relative_to(root)) if str(dest).startswith(str(root)) else str(dest),
        "size": len(content),
    }
