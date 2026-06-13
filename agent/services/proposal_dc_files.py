"""交付预案 · 表格读写到数据中心（含 mock 降级）。"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from shared.datacenter import DataCenterClient, DataCenterError, ipo_paths
from shared.datacenter.logging_utils import LOG, mask_token
from shared.datacenter.types import SemanticFileRef

from .local_mock_fallback import mock_logical_for_slot, read_bytes as mock_read_bytes, write_bytes as mock_write_bytes
from .proposal_parse import (
    parse_acceptance_from_docx,
    parse_card_scale_from_md,
    parse_plan_xlsx,
    parse_raci_xlsx,
    parse_testcases_xlsx,
    read_saved_version,
    write_xlsx_table,
)


def _parse_saved_acceptance(path: Path) -> list[dict[str, str]]:
    from .proposal_parse import _resolve_xlsx_data_start

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


async def read_table_slot(
    token: str | None,
    slot: str,
    project_id: str,
    project_name: str,
    project_code: str | None,
) -> tuple[dict[str, Any], str, list[str]]:
    """返回 (data, source, warnings)。"""
    warnings: list[str] = []
    ref = ipo_paths.slot_to_ref(slot, project_id)
    LOG.info(
        "proposal read_table_slot slot=%s projectId=%s projectName=%s projectCode=%s token=%s ref=%s",
        slot,
        project_id,
        project_name,
        project_code,
        mask_token(token),
        ref.to_list_body(),
    )

    if token:
        try:
            content, logical, _ = await _download_dc(token, ref, slot)
            LOG.info(
                "proposal read_table_slot DC ok slot=%s logicalPath=%s bytes=%s",
                slot,
                logical,
                len(content),
            )
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(ref.file_name or "bin").suffix or ".bin") as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            try:
                data = _parse_file_bytes(tmp_path, slot, logical)
                data["path"] = logical
                row_count = len(data.get("rows") or [])
                LOG.info(
                    "proposal read_table_slot parsed slot=%s kind=%s rows=%s version=%s source=datacenter",
                    slot,
                    data.get("kind"),
                    row_count,
                    data.get("version"),
                )
                return data, "datacenter", warnings
            finally:
                tmp_path.unlink(missing_ok=True)
        except DataCenterError as e:
            LOG.warning("proposal read_table_slot DC error slot=%s: %s", slot, e)
            warnings.append(f"数据中心不可用({e})，已降级读取本地 mock")
        except Exception as e:
            LOG.exception("proposal read_table_slot DC unexpected slot=%s", slot)
            warnings.append(f"数据中心请求失败({e})，已降级读取本地 mock")
    else:
        LOG.warning("proposal read_table_slot no token, skip DC slot=%s", slot)

    try:
        raw, logical = mock_read_bytes(slot, project_name, project_code)
        LOG.info("proposal read_table_slot mock hit slot=%s logical=%s bytes=%s", slot, logical, len(raw))
    except FileNotFoundError as e:
        LOG.warning("proposal read_table_slot mock missing slot=%s: %s", slot, e)
        warnings.append(f"本地 mock 也不存在: {e}")
        empty: dict[str, Any] = {"kind": slot, "rows": [], "version": 0, "path": ""}
        if slot == "card_scale":
            empty = {"kind": "markdown", "cardScale": 384, "path": ""}
        return empty, "none", warnings

    suffix = Path(logical).suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)
    try:
        data = _parse_file_bytes(tmp_path, slot, logical)
        data["path"] = logical
        LOG.info(
            "proposal read_table_slot parsed slot=%s kind=%s rows=%s source=mock warnings=%s",
            slot,
            data.get("kind"),
            len(data.get("rows") or []),
            warnings,
        )
        return data, "mock", warnings
    finally:
        tmp_path.unlink(missing_ok=True)


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
    warnings: list[str] = []
    ref = ipo_paths.slot_to_ref(slot, project_id)
    LOG.info(
        "proposal write_table_slot slot=%s projectId=%s kind=%s version=%s rows=%s token=%s",
        slot,
        project_id,
        kind,
        version,
        len(rows),
        mask_token(token),
    )
    headers, row_maps = _build_xlsx(kind, rows, project_name, version)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = Path(tmp.name)
    try:
        write_xlsx_table(tmp_path, headers, row_maps, version, project_name)
        content = tmp_path.read_bytes()
        file_name = ref.file_name or "output.xlsx"
    finally:
        tmp_path.unlink(missing_ok=True)

    if token:
        try:
            client = DataCenterClient(token)
            result = await client.upload_file(ref, content, file_name)
            logical = str(result.get("logicalPath") or "")
            LOG.info("proposal write_table_slot DC ok slot=%s logicalPath=%s", slot, logical)
            return {"path": logical, "version": version, "rowCount": len(row_maps)}, "datacenter", warnings
        except DataCenterError as e:
            LOG.warning("proposal write_table_slot DC error slot=%s: %s", slot, e)
            warnings.append(f"数据中心写入失败({e})，已降级写入本地 mock")
        except Exception as e:
            LOG.exception("proposal write_table_slot DC unexpected slot=%s", slot)
            warnings.append(f"数据中心写入失败({e})，已降级写入本地 mock")

    logical = mock_logical_for_slot(slot, project_name, project_code)
    mock_write_bytes(logical, content)
    LOG.info("proposal write_table_slot mock ok slot=%s logical=%s", slot, logical)
    return {"path": logical, "version": version, "rowCount": len(row_maps)}, "mock", warnings


async def load_testcases_template_bytes(
    token: str | None,
    project_id: str,
    project_name: str,
    project_code: str | None,
) -> tuple[Path, str, list[str]]:
    """返回临时 xlsx 路径（调用方须 delete）、source、warnings。"""
    warnings: list[str] = []
    ref = ipo_paths.testcases_template_ref(project_id)
    if token:
        try:
            content, logical, _ = await _download_dc(token, ref, "testcases_template")
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            tmp.write(content)
            tmp.close()
            return Path(tmp.name), "datacenter", warnings
        except (DataCenterError, Exception) as e:
            warnings.append(f"数据中心模板不可用({e})，已降级 mock")

    raw, logical = mock_read_bytes("testcases_template", project_name, project_code)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.write(raw)
    tmp.close()
    return Path(tmp.name), "mock", warnings
