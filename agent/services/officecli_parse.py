"""
交付预案 · officecli 多模态解析（技术建议书 / 测试用例）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

SKILL_SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "officecli" / "scripts"


def _ensure_scripts_path() -> None:
    p = str(SKILL_SCRIPTS)
    if p not in sys.path:
        sys.path.insert(0, p)


def parse_acceptance_via_officecli(docx_path: Path) -> list[dict[str, str]]:
    """技术建议书 docx → 验收策略表（officecli 管线A）。"""
    _ensure_scripts_path()
    import service_advice_post

    rows = service_advice_post.extract(docx_path)
    return service_advice_post.to_frontend_items(rows)


def _map_testcase_to_frontend(case: dict[str, Any]) -> dict[str, Any]:
    cat = case.get("category", "服务部分")
    chapter = case.get("chapter", "")
    l1_map = {
        "硬件设备": "计算子系统测试用例",
        "软件部分": "计算子系统测试用例",
        "服务部分": "算力集群性能测试用例",
    }
    l1 = l1_map.get(cat, "计算子系统测试用例")
    l2 = chapter.split(" ", 1)[-1] if chapter else cat
    pre = case.get("preconditions", [])
    if isinstance(pre, str):
        pre = [pre] if pre else []
    steps = case.get("test_steps", case.get("steps", []))
    expects = case.get("expected_result", case.get("expects", []))
    return {
        "id": str(case.get("case_id", case.get("id", ""))),
        "l1": l1,
        "l2": l2,
        "l3": str(case.get("test_purpose", case.get("l3", ""))),
        "purpose": str(case.get("test_purpose", case.get("purpose", ""))),
        "topology": str(case.get("test_network", case.get("topology", "NA"))),
        "pre": "\n".join(pre) if isinstance(pre, list) else str(pre),
        "steps": steps if isinstance(steps, list) else [],
        "expects": expects if isinstance(expects, list) else [],
        "result": str(case.get("result", "")),
        "remark": str(case.get("remarks", case.get("remark", ""))),
    }


def parse_testcases_via_officecli(path: Path) -> list[dict[str, Any]]:
    """测试用例 docx/xlsx → 结构化用例列表。"""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        _ensure_scripts_path()
        import testcase_post

        result = testcase_post.extract(str(path))
        return [_map_testcase_to_frontend(c) for c in result.get("cases", [])]

    if suffix in (".xlsx", ".xlsm"):
        return _parse_testcases_xlsx_officecli(path)

    return []


def _parse_testcases_xlsx_officecli(path: Path) -> list[dict[str, Any]]:
    from .officecli_client import xlsx_sheet_rows

    try:
        matrix = xlsx_sheet_rows(path, "测试用例")
    except Exception:
        try:
            matrix = xlsx_sheet_rows(path, "Sheet1")
        except Exception:
            from .proposal_parse import parse_testcases_xlsx
            return parse_testcases_xlsx(path)

    if not matrix:
        return []

    headers = [str(h or "").strip() for h in matrix[0]]
    alias = {
        "用例编号": "id",
        "一级分类": "l1",
        "二级分类": "l2",
        "三级分类": "l3",
        "测试目的": "purpose",
        "测试组网": "topology",
        "预置条件": "pre",
        "测试步骤": "steps",
        "预期结果": "expects",
        "测试结果": "result",
        "备注": "remark",
    }
    idx = {alias.get(h, h): i for i, h in enumerate(headers) if h not in ("项目名称", "版本号", "勾选")}

    out: list[dict[str, Any]] = []
    for row in matrix[1:]:
        if not row or all(not str(v).strip() for v in row):
            continue

        def get(k: str) -> str:
            if k not in idx or idx[k] >= len(row):
                return ""
            v = row[idx[k]]
            return "" if v is None else str(v).strip()

        if not get("id") or get("id") == "用例编号":
            continue
        steps_raw = get("steps")
        expects_raw = get("expects")
        out.append({
            "id": get("id"),
            "l1": get("l1"),
            "l2": get("l2"),
            "l3": get("l3"),
            "purpose": get("purpose"),
            "topology": get("topology"),
            "pre": get("pre"),
            "steps": [s.strip() for s in steps_raw.split("\n") if s.strip()] if steps_raw else [],
            "expects": [s.strip() for s in expects_raw.split("\n") if s.strip()] if expects_raw else [],
            "result": get("result"),
            "remark": get("remark"),
        })
    return out


_DETAIL_FIELDS = ("steps", "expects", "pre", "purpose", "topology", "remark", "result", "l3")


def _load_default_testcases_xlsx(xlsx_path: Path) -> list[dict[str, Any]]:
    """从 mock 测试用例new.xlsx 读取默认条目（SSOT 目录）。"""
    if not xlsx_path.is_file():
        return []
    try:
        return parse_testcases_via_officecli(xlsx_path)
    except Exception:
        from .proposal_parse import parse_testcases_xlsx

        return parse_testcases_xlsx(xlsx_path)


def _merge_testcases_by_id(
    xlsx_rows: list[dict[str, Any]],
    upload_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """xlsx 为目录 SSOT；上传 docx 按用例编号补全详情字段。"""
    by_id: dict[str, dict[str, Any]] = {}
    for row in xlsx_rows:
        cid = str(row.get("id", "")).strip()
        if cid:
            by_id[cid] = dict(row)

    for row in upload_rows:
        cid = str(row.get("id", "")).strip()
        if not cid:
            continue
        if cid in by_id:
            for field in _DETAIL_FIELDS:
                val = row.get(field)
                if val:
                    by_id[cid][field] = val
        else:
            by_id[cid] = dict(row)

    return list(by_id.values())


def merge_testcases_with_upload(
    xlsx_path: Path,
    upload_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    合并 xlsx 默认条目与上传文件解析结果。
    - 始终读取 xlsx 默认条目
    - docx：officecli 解析后与 xlsx 按 case_id 合并（docx 优先补全详情）
    - pdf 或解析失败：仅返回 xlsx 默认条目
    """
    xlsx_rows = _load_default_testcases_xlsx(xlsx_path)
    source: dict[str, Any] = {
        "xlsx": str(xlsx_path) if xlsx_path.is_file() else None,
        "upload": None,
        "engine": "xlsx-only",
    }

    if upload_path is None or not upload_path.is_file():
        return xlsx_rows, source

    source["upload"] = upload_path.name
    suffix = upload_path.suffix.lower()

    if suffix == ".docx":
        try:
            upload_rows = parse_testcases_via_officecli(upload_path)
            source["engine"] = "officecli-merge"
            return _merge_testcases_by_id(xlsx_rows, upload_rows), source
        except Exception:
            source["engine"] = "docx-failed-xlsx-only"
            return xlsx_rows, source

    if suffix == ".pdf":
        source["engine"] = "pdf-fallback-xlsx"
        return xlsx_rows, source

    if suffix in (".xlsx", ".xlsm"):
        try:
            upload_rows = parse_testcases_via_officecli(upload_path)
            source["engine"] = "xlsx-upload-merge"
            return _merge_testcases_by_id(xlsx_rows, upload_rows), source
        except Exception:
            from .proposal_parse import parse_testcases_xlsx

            upload_rows = parse_testcases_xlsx(upload_path)
            source["engine"] = "xlsx-upload-merge"
            return _merge_testcases_by_id(xlsx_rows, upload_rows), source

    return xlsx_rows, source
