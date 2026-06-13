"""交付预案 · 表格读写到数据中心（含 mock 降级）。"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from shared.datacenter import DataCenterClient, DataCenterError, ipo_paths
from shared.datacenter.logging_utils import LOG, mask_token
from shared.datacenter.types import SemanticFileRef

from .local_mock_fallback import (
    OPTIONAL_OUTPUT_SLOTS,
    local_logical_candidates,
    mock_logical_for_slot,
    resolve_mock_path,
    save_dc_download,
    try_resolve_local_slot,
    try_resolve_mock_project_slot,
    write_bytes as mock_write_bytes,
)
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


def _empty_slot_data(slot: str) -> dict[str, Any]:
    empty: dict[str, Any] = {"kind": slot, "rows": [], "version": 0, "path": ""}
    if slot == "card_scale":
        empty = {"kind": "markdown", "cardScale": 384, "path": ""}
    return empty


def _is_slot_data_usable(data: dict[str, Any], slot: str) -> bool:
    """解析结果是否可用于页面展示。"""
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


def _read_and_parse_slot(path: Path, slot: str, logical: str) -> dict[str, Any]:
    data = _parse_file_bytes(path, slot, logical)
    data["path"] = logical
    data["localPath"] = str(path)
    return data


async def _try_mock_project_fallback(
    slot: str,
    warnings: list[str],
) -> tuple[dict[str, Any], str] | None:
    """正常链路失败时，从 mock_project 对应目录读取并解析。"""
    mock_hit = try_resolve_mock_project_slot(slot)
    if not mock_hit:
        return None
    path, logical = mock_hit
    try:
        data = _read_and_parse_slot(path, slot, logical)
    except Exception as e:
        LOG.warning("proposal mock_project fallback parse failed slot=%s: %s", slot, e)
        return None
    if not _is_slot_data_usable(data, slot):
        return None
    warnings.append(f"已从 mock_project 降级加载: {logical}")
    LOG.info(
        "proposal mock_project fallback ok slot=%s logical=%s rows=%s",
        slot,
        logical,
        len(data.get("rows") or []),
    )
    return data, "mock_fallback"


async def ensure_slot_local(
    token: str | None,
    slot: str,
    project_id: str,
    project_name: str,
    project_code: str | None,
) -> dict[str, Any]:
    """确保 slot 对应文件在本地 mock 目录；缺失且有 token 时从数据中心下载落盘。"""
    ref = ipo_paths.slot_to_ref(slot, project_id)
    local_hit = try_resolve_local_slot(slot, project_name, project_code)
    if local_hit:
        path, logical = local_hit
        LOG.info(
            "proposal ensure_slot_local hit slot=%s status=local logical=%s localPath=%s",
            slot,
            logical,
            path,
        )
        return {
            "status": "local",
            "localPath": str(path),
            "logical": logical,
            "bytes": path.stat().st_size,
        }

    if not token:
        if slot in OPTIONAL_OUTPUT_SLOTS:
            return {"status": "optional_missing", "error": "输出文件尚未保存"}
        mock_hit = try_resolve_mock_project_slot(slot)
        if mock_hit:
            path, logical = mock_hit
            return {
                "status": "mock_fallback",
                "localPath": str(path),
                "logical": logical,
                "bytes": path.stat().st_size,
            }
        return {
            "status": "missing",
            "error": "本地无文件且无 token，无法从数据中心下载",
            "candidates": local_logical_candidates(slot, project_name, project_code),
        }

    # 输出表草稿期可能尚未上传数据中心，先 list 避免无意义 download 404
    if slot in OPTIONAL_OUTPUT_SLOTS:
        try:
            client = DataCenterClient(token)
            listed = await client.list_files(ref)
            if not (listed.get("list") or []):
                LOG.info("proposal ensure_slot_local optional empty slot=%s (no output saved yet)", slot)
                return {"status": "optional_missing", "error": "数据中心尚无此输出文件"}
        except DataCenterError as e:
            LOG.info("proposal ensure_slot_local optional unavailable slot=%s: %s", slot, e)
            return {"status": "optional_missing", "error": str(e)}

    try:
        content, logical, _ = await _download_dc(token, ref, slot)
        if not logical:
            raise DataCenterError("数据中心未返回 logicalPath")
        local_path = save_dc_download(logical, content, project_name, project_code)
        LOG.info(
            "proposal ensure_slot_local downloaded slot=%s logical=%s localPath=%s bytes=%s",
            slot,
            logical,
            local_path,
            len(content),
        )
        return {
            "status": "downloaded",
            "localPath": str(local_path),
            "logical": logical,
            "bytes": len(content),
        }
    except DataCenterError as e:
        LOG.warning("proposal ensure_slot_local DC error slot=%s: %s", slot, e)
        mock_hit = try_resolve_mock_project_slot(slot)
        if mock_hit:
            path, logical = mock_hit
            return {
                "status": "mock_fallback",
                "localPath": str(path),
                "logical": logical,
                "bytes": path.stat().st_size,
            }
        return {"status": "missing", "error": str(e)}
    except Exception as e:
        LOG.exception("proposal ensure_slot_local unexpected slot=%s", slot)
        mock_hit = try_resolve_mock_project_slot(slot)
        if mock_hit:
            path, logical = mock_hit
            return {
                "status": "mock_fallback",
                "localPath": str(path),
                "logical": logical,
                "bytes": path.stat().st_size,
            }
        return {"status": "missing", "error": str(e)}


async def sync_proposal_slots(
    token: str | None,
    project_id: str,
    project_name: str,
    project_code: str | None,
    slots: list[str],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """进入交付预案时批量确保本地文件就绪（本地优先，缺失再下载）。"""
    results: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for slot in slots:
        result = await ensure_slot_local(
            token, slot, project_id, project_name, project_code,
        )
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
    """本地优先：有则直接解析；无则从数据中心下载到 mock 后再解析。"""
    warnings: list[str] = []
    LOG.info(
        "proposal read_table_slot slot=%s projectId=%s projectName=%s projectCode=%s token=%s",
        slot,
        project_id,
        project_name,
        project_code,
        mask_token(token),
    )

    ensured = await ensure_slot_local(
        token, slot, project_id, project_name, project_code,
    )
    status = str(ensured.get("status") or "missing")
    if status == "optional_missing":
        LOG.info("proposal read_table_slot optional empty slot=%s", slot)
        return _empty_slot_data(slot), "optional", warnings
    if status == "missing":
        warnings.append(f"文件不可用: {ensured.get('error', slot)}")
        LOG.warning("proposal read_table_slot missing slot=%s error=%s", slot, ensured.get("error"))
        fallback = await _try_mock_project_fallback(slot, warnings)
        if fallback:
            return fallback[0], fallback[1], warnings
        return _empty_slot_data(slot), "none", warnings

    local_path = Path(str(ensured["localPath"]))
    logical = str(ensured.get("logical") or "")
    LOG.info(
        "proposal read_table_slot ready slot=%s status=%s localPath=%s bytes=%s",
        slot,
        status,
        local_path,
        ensured.get("bytes"),
    )

    data = _read_and_parse_slot(local_path, slot, logical)
    if not _is_slot_data_usable(data, slot):
        LOG.warning("proposal read_table_slot empty/unusable slot=%s status=%s", slot, status)
        fallback = await _try_mock_project_fallback(slot, warnings)
        if fallback:
            return fallback[0], fallback[1], warnings

    row_count = len(data.get("rows") or [])
    LOG.info(
        "proposal read_table_slot parsed slot=%s kind=%s rows=%s version=%s source=%s",
        slot,
        data.get("kind"),
        row_count,
        data.get("version"),
        status,
    )
    return data, status, warnings


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

    logical_local = local_logical_candidates(slot, project_name, project_code)[0]
    try:
        mock_write_bytes(logical_local, content)
        LOG.info("proposal write_table_slot local ok slot=%s logical=%s", slot, logical_local)
    except Exception as e:
        LOG.warning("proposal write_table_slot local write failed slot=%s: %s", slot, e)

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
    """返回 mock 目录下的 xlsx 路径、source、warnings（本地优先）。"""
    warnings: list[str] = []
    ensured = await ensure_slot_local(
        token, "testcases_template", project_id, project_name, project_code,
    )
    status = str(ensured.get("status") or "missing")
    if status == "missing":
        warnings.append(f"测试用例模板不可用: {ensured.get('error', '')}")
        raise FileNotFoundError(ensured.get("error") or "testcases_template missing")
    return Path(str(ensured["localPath"])), status, warnings
