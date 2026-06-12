"""
交付预案 · Mock 文件读写与解析 API（0610）
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ..services.proposal_parse import (
    parse_acceptance_from_docx,
    parse_card_scale_from_md,
    parse_plan_xlsx,
    parse_raci_xlsx,
    parse_testcases_xlsx,
    read_saved_version,
    write_xlsx_table,
)

router = APIRouter(prefix="/api/v1", tags=["proposal-mock"])

# aida/mock数据 根目录
MOCK_ROOT = Path(__file__).resolve().parents[2] / "mock数据"


def _resolve_logical(logical_path: str) -> Path:
    p = (MOCK_ROOT / logical_path.replace("\\", "/")).resolve()
    try:
        p.relative_to(MOCK_ROOT.resolve())
    except ValueError as e:
        raise HTTPException(403, "path outside mock root") from e
    return p


def _ok(data: Any) -> dict:
    return {"code": 0, "message": "success", "data": data}


@router.get("/mock/file")
def get_mock_file(logicalPath: str = Query(..., description="IPO 逻辑路径")):
    path = _resolve_logical(logicalPath)
    if not path.is_file():
        raise HTTPException(404, f"file not found: {logicalPath}")

    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        if "责任矩阵" in path.name or "RACI" in path.name.upper():
            rows = parse_raci_xlsx(path)
            kind = "raci"
        elif "计划" in path.name or "进度" in path.name:
            rows = parse_plan_xlsx(path)
            kind = "plan"
        elif "测试用例" in path.name:
            rows = parse_testcases_xlsx(path)
            kind = "testcases"
        elif "验收策略" in path.name:
            rows = _parse_saved_acceptance(path)
            kind = "acceptance"
        else:
            rows = parse_raci_xlsx(path)
            kind = "generic"
        version = read_saved_version(path) if "输出结果" in logicalPath else 0
        return _ok({"kind": kind, "rows": rows, "version": version, "path": logicalPath})

    if suffix == ".md":
        text = path.read_text(encoding="utf-8")
        card_scale = parse_card_scale_from_md(path)
        return _ok({"kind": "markdown", "text": text, "cardScale": card_scale, "path": logicalPath})

    if suffix == ".docx":
        items = parse_acceptance_from_docx(path)
        return _ok({"kind": "acceptance", "rows": items, "path": logicalPath})

    return _ok({"kind": "raw", "text": path.read_text(encoding="utf-8", errors="replace")})


def _parse_saved_acceptance(path: Path) -> list[dict[str, str]]:
    from ..services.proposal_parse import _resolve_xlsx_data_start

    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
    headers, data_start = _resolve_xlsx_data_start(all_rows)
    alias = {
        "分类": "cat",
        "验收方案": "scheme",
        "验收标准": "standard",
        "验收里程碑": "milestone",
        "验收文档": "doc",
        "回款条款": "payment",
        "回款里程碑": "paymentMilestone",
    }
    idx = {alias.get(h, h): i for i, h in enumerate(headers) if h not in ("项目名称", "版本号")}
    out = []
    for row in all_rows[data_start:]:
        if not row:
            continue

        def get(k: str) -> str:
            if k not in idx or idx[k] >= len(row):
                return ""
            v = row[idx[k]]
            return "" if v is None else str(v).strip()

        if get("cat") in ("", "分类") and get("scheme") in ("", "验收方案"):
            continue
        if not get("cat") and not get("scheme"):
            continue
        out.append({
            "cat": get("cat"),
            "scheme": get("scheme"),
            "standard": get("standard"),
            "milestone": get("milestone"),
            "doc": get("doc"),
            "payment": get("payment"),
            "paymentMilestone": get("paymentMilestone"),
        })
    return out


class WriteMockFileBody(BaseModel):
    logicalPath: str
    kind: str = Field(..., description="raci | acceptance | testcases")
    projectName: str = "京东三期"
    version: int = 1
    rows: list[dict[str, Any]]


@router.post("/mock/file")
def post_mock_file(body: WriteMockFileBody):
    path = _resolve_logical(body.logicalPath)

    if body.kind == "raci":
        headers = ["技术栈", "活动分类", "活动", "GTS", "华为云", "伙伴", "客户"]
        row_maps = [
            {
                "技术栈": r.get("stack", ""),
                "活动分类": r.get("cat", ""),
                "活动": r.get("act", ""),
                "GTS": r.get("gts", ""),
                "华为云": r.get("hw", ""),
                "伙伴": r.get("partner", ""),
                "客户": r.get("customer", ""),
            }
            for r in body.rows
        ]
    elif body.kind == "acceptance":
        headers = ["分类", "验收方案", "验收标准", "验收里程碑", "验收文档", "回款条款", "回款里程碑"]
        row_maps = [
            {
                "分类": r.get("cat", ""),
                "验收方案": r.get("scheme", ""),
                "验收标准": r.get("standard", ""),
                "验收里程碑": r.get("milestone", ""),
                "验收文档": r.get("doc", ""),
                "回款条款": r.get("payment", ""),
                "回款里程碑": r.get("paymentMilestone", ""),
            }
            for r in body.rows
        ]
    elif body.kind == "testcases":
        headers = [
            "勾选", "用例编号", "一级分类", "二级分类", "三级分类",
            "测试目的", "测试组网", "预置条件", "测试步骤", "预期结果", "测试结果", "备注",
        ]
        row_maps = []
        for r in body.rows:
            row_maps.append({
                "勾选": "是" if r.get("selected") else "否",
                "用例编号": r.get("id", ""),
                "一级分类": r.get("l1", ""),
                "二级分类": r.get("l2", ""),
                "三级分类": r.get("l3", ""),
                "测试目的": r.get("purpose", ""),
                "测试组网": r.get("topology", ""),
                "预置条件": r.get("pre", ""),
                "测试步骤": "\n".join(r.get("steps") or []),
                "预期结果": "\n".join(r.get("expects") or []),
                "测试结果": r.get("result", ""),
                "备注": r.get("remark", ""),
            })
    else:
        raise HTTPException(400, f"unsupported kind: {body.kind}")

    write_xlsx_table(path, headers, row_maps, body.version, body.projectName)
    return _ok({"path": body.logicalPath, "version": body.version, "rowCount": len(row_maps)})


@router.post("/proposal/parse/tech-proposal")
async def parse_tech_proposal(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".docx", ".pdf"):
        raise HTTPException(400, "仅支持 .docx / .pdf")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        if suffix == ".docx":
            try:
                from ..services.officecli_parse import parse_acceptance_via_officecli
                rows = parse_acceptance_via_officecli(tmp_path)
            except Exception:
                rows = parse_acceptance_from_docx(tmp_path)
        else:
            rows = []
        return _ok({"rows": rows, "source": file.filename, "engine": "officecli"})
    finally:
        tmp_path.unlink(missing_ok=True)


DEFAULT_TESTCASES_XLSX = (
    "JD2项目_test-boq/早期介入/交付预案/输入文件/测试用例new.xlsx"
)


@router.post("/proposal/parse/testcases")
async def parse_testcases_upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".docx", ".pdf", ".xlsx", ".xlsm"):
        raise HTTPException(400, "仅支持 .docx / .pdf / .xlsx")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        from ..services.officecli_parse import merge_testcases_with_upload

        xlsx_path = _resolve_logical(DEFAULT_TESTCASES_XLSX)
        rows, source = merge_testcases_with_upload(xlsx_path, tmp_path)
        source["upload"] = file.filename
        return _ok({
            "rows": rows,
            "source": source,
            "engine": source.get("engine", "officecli"),
        })
    finally:
        tmp_path.unlink(missing_ok=True)
