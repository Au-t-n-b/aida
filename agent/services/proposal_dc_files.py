"""交付预案 · 表格读写走数据中心（DC-only）。"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from shared.datacenter import DataCenterClient, DataCenterError, ipo_paths
from shared.datacenter.logging_utils import LOG, mask_token
from shared.datacenter.types import SemanticFileRef

from .proposal_parse import (
    parse_acceptance_from_docx,
    parse_card_scale_from_md,
    parse_plan_xlsx,
    parse_raci_xlsx,
    parse_testcases_xlsx,
    read_saved_version,
    write_xlsx_table,
)

OPTIONAL_OUTPUT_SLOTS = frozenset({"raci_out", "acceptance_out", "testcases_out"})


def _parse_saved_acceptance(path: Path) -> list[dict[str, str]]:
    from .proposal_parse import _resolve_xlsx_data_start

    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()
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


def _parse_file_bytes(path: Path, slot: str, logical_path: str) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        if slot in ("raci_template", "raci_out"):
            rows = parse_raci_xlsx(path)
            kind = "raci"
        elif slot == "plan":
            rows = parse_plan_xlsx(path)
            kind = "plan"
        elif slot in ("testcases_template", "testcases_out"):
            rows = parse_testcases_xlsx(path)
            kind = "testcases"
        elif slot == "acceptance_out":
            rows = _parse_saved_acceptance(path)
            kind = "acceptance"
        else:
            rows = parse_raci_xlsx(path)
            kind = "generic"
        version = read_saved_version(path) if "输出结果" in logical_path else 0
        return {"kind": kind, "rows": rows, "version": version}
    if suffix == ".md":
        return {
            "kind": "markdown",
            "text": path.read_text(encoding="utf-8"),
            "cardScale": parse_card_scale_from_md(path),
        }
    if suffix == ".docx":
        return {"kind": "acceptance", "rows": parse_acceptance_from_docx(path)}
    return {"kind": "raw", "text": path.read_text(encoding="utf-8", errors="replace")}


def _empty_slot_data(slot: str) -> dict[str, Any]:
    empty: dict[str, Any] = {"kind": slot, "rows": [], "version": 0, "path": ""}
    if slot == "card_scale":
        empty = {"kind": "markdown", "cardScale": 384, "path": ""}
    return empty


def _is_slot_data_usable(data: dict[str, Any], slot: str) -> bool:
    if slot == "card_scale":
        return bool(data.get("cardScale"))
    rows = data.get("rows")
    if isinstance(rows, list) and len(rows) > 0:
        return True
    if slot in ("acceptance_input",) and data.get("kind") == "acceptance":
        return bool(rows)
    if data.get("kind") == "markdown" and data.get("text"):
        return True
    return False


async def _download_dc(token: str, ref: SemanticFileRef, slot: str) -> tuple[bytes, str, SemanticFileRef]:
    client = DataCenterClient(token)
    if slot == "acceptance_input":
        resolved, meta = await client.resolve_first_file(ref, extensions=(".docx", ".pdf"))
        content = await client.download_file(resolved)
        logical = str(meta.get("logicalPath") or "")
        return content, logical, resolved
    if not ref.file_name:
        resolved, meta = await client.resolve_first_file(ref)
        content = await client.download_file(resolved)
        logical = str(meta.get("logicalPath") or "")
        return content, logical, resolved
    content = await client.download_file(ref)
    data = await client.list_files(ref)
    items = data.get("list") or []
    logical = str(items[0].get("logicalPath") if items else "")
    return content, logical, ref


def _parse_content_bytes(content: bytes, slot: str, logical: str, suffix: str) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
    try:
        tmp_path.write_bytes(content)
        data = _parse_file_bytes(tmp_path, slot, logical)
        data["path"] = logical
        return data
    finally:
        tmp_path.unlink(missing_ok=True)


async def _fetch_slot_bytes(
    token: str | None,
    slot: str,
    project_id: str,
) -> tuple[bytes, str] | None:
    if not token:
        return None
    ref = ipo_paths.slot_to_ref(slot, project_id)
    if slot in OPTIONAL_OUTPUT_SLOTS:
        try:
            listed = await DataCenterClient(token).list_files(ref)
            if not (listed.get("list") or []):
                return None
        except DataCenterError:
            return None
    try:
        content, logical, _ = await _download_dc(token, ref, slot)
        if not logical:
            return None
        return content, logical
    except DataCenterError as exc:
        LOG.warning("proposal fetch slot DC error slot=%s: %s", slot, exc)
        return None


async def ensure_slot_local(
    token: str | None,
    slot: str,
    project_id: str,
    project_name: str,
    project_code: str | None,
) -> dict[str, Any]:
    """Verify slot readable from datacenter (compat name for proposal_files router)."""
    del project_name, project_code
    hit = await _fetch_slot_bytes(token, slot, project_id)
    if hit:
        content, logical = hit
        return {
            "status": "datacenter",
            "logical": logical,
            "bytes": len(content),
        }
    if slot in OPTIONAL_OUTPUT_SLOTS:
        return {"status": "optional_missing", "error": "数据中心尚无此输出文件"}
    if not token:
        return {"status": "missing", "error": "无 token，无法从数据中心读取"}
    return {"status": "missing", "error": f"数据中心无可用文件: {slot}"}


async def sync_proposal_slots(
    token: str | None,
    project_id: str,
    project_name: str,
    project_code: str | None,
    slots: list[str],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    results: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for slot in slots:
        try:
            result = await ensure_slot_local(
                token, slot, project_id, project_name, project_code,
            )
        except Exception as e:
            LOG.exception("proposal sync slot failed slot=%s", slot)
            result = {"status": "missing", "error": str(e)}
        results[slot] = result
        if result.get("status") == "missing":
            warnings.append(f"{slot}: {result.get('error', '文件不可用')}")
    return results, warnings


async def read_table_slot(
    token: str | None,
    slot: str,
    project_id: str,
    project_name: str,
    project_code: str | None,
) -> tuple[dict[str, Any], str, list[str]]:
    del project_name, project_code
    warnings: list[str] = []
    LOG.info(
        "proposal read_table_slot slot=%s projectId=%s token=%s",
        slot,
        project_id,
        mask_token(token),
    )

    if not token:
        warnings.append("无 token，无法从数据中心读取")
        return _empty_slot_data(slot), "none", warnings

    hit = await _fetch_slot_bytes(token, slot, project_id)
    if not hit:
        if slot in OPTIONAL_OUTPUT_SLOTS:
            return _empty_slot_data(slot), "optional", warnings
        warnings.append(f"数据中心无可用文件: {slot}")
        return _empty_slot_data(slot), "none", warnings

    content, logical = hit
    suffix = Path(logical).suffix or ".xlsx"
    data = await asyncio.to_thread(_parse_content_bytes, content, slot, logical, suffix)
    if not _is_slot_data_usable(data, slot):
        LOG.warning("proposal read_table_slot empty/unusable slot=%s", slot)
        if slot in OPTIONAL_OUTPUT_SLOTS:
            return _empty_slot_data(slot), "optional", warnings
        warnings.append(f"文件内容不可用: {slot}")
        return _empty_slot_data(slot), "none", warnings

    LOG.info(
        "proposal read_table_slot parsed slot=%s kind=%s rows=%s source=datacenter",
        slot,
        data.get("kind"),
        len(data.get("rows") or []),
    )
    return data, "datacenter", warnings


def _build_xlsx(
    kind: str,
    rows: list[dict[str, Any]],
    project_name: str,
    version: int,
) -> tuple[list[str], list[dict[str, str]]]:
    if kind == "raci":
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
            for r in rows
        ]
    elif kind == "acceptance":
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
            for r in rows
        ]
    elif kind == "testcases":
        headers = [
            "勾选", "用例编号", "一级分类", "二级分类", "三级分类",
            "测试目的", "测试组网", "预置条件", "测试步骤", "预期结果", "测试结果", "备注",
        ]
        row_maps = []
        for r in rows:
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
        raise ValueError(f"unsupported kind: {kind}")
    return headers, row_maps


async def write_table_slot(
    token: str | None,
    slot: str,
    project_id: str,
    project_name: str,
    project_code: str | None,
    kind: str,
    rows: list[dict[str, Any]],
    version: int,
) -> tuple[dict[str, Any], str, list[str]]:
    del project_code
    warnings: list[str] = []
    ref = ipo_paths.slot_to_ref(slot, project_id)
    LOG.info(
        "proposal write_table_slot slot=%s projectId=%s kind=%s rows=%s token=%s",
        slot,
        project_id,
        kind,
        len(rows),
        mask_token(token),
    )
    if not token:
        warnings.append("无 token，未写入数据中心")
        return {"path": "", "version": version, "rowCount": len(rows)}, "none", warnings

    headers, row_maps = _build_xlsx(kind, rows, project_name, version)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = Path(tmp.name)
    try:
        write_xlsx_table(tmp_path, headers, row_maps, version, project_name)
        content = tmp_path.read_bytes()
        file_name = ref.file_name or "output.xlsx"
    finally:
        tmp_path.unlink(missing_ok=True)

    try:
        client = DataCenterClient(token)
        result = await client.upload_file(ref, content, file_name)
        logical = str(result.get("logicalPath") or "")
        LOG.info("proposal write_table_slot DC ok slot=%s logicalPath=%s", slot, logical)
        return {"path": logical, "version": version, "rowCount": len(row_maps)}, "datacenter", warnings
    except DataCenterError as e:
        LOG.warning("proposal write_table_slot DC error slot=%s: %s", slot, e)
        warnings.append(f"数据中心写入失败: {e}")
        return {"path": "", "version": version, "rowCount": len(row_maps)}, "none", warnings


async def load_testcases_template_bytes(
    token: str | None,
    project_id: str,
    project_name: str,
    project_code: str | None,
) -> tuple[Path, str, list[str]]:
    del project_name, project_code
    warnings: list[str] = []
    hit = await _fetch_slot_bytes(token, "testcases_template", project_id)
    if not hit:
        msg = "测试用例模板不可用"
        warnings.append(msg)
        raise FileNotFoundError(msg)
    content, logical = hit
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = Path(tmp.name)
    tmp_path.write_bytes(content)
    return tmp_path, "datacenter", warnings
