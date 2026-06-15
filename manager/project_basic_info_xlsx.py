"""项目创建/编辑后同步「项目基础信息表.xlsx」到业务数据目录。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from manager.config import business_root

LOG = logging.getLogger("aida.manager.project_basic")

# 单 sheet 表头（顺序固定）
BASIC_INFO_HEADERS: tuple[str, ...] = (
    "Proposal ID",
    "项目ID",
    "合同类型",
    "项目编码",
    "项目名称",
    "PD",
    "TD",
    "PCM",
    "客户",
    "DC",
    "L1工勘专家",
    "规划设计TL",
    "设备安装TL",
    "部署调测TL",
)

# 每次从数据中心刷新时强制覆盖的列
_ALWAYS_OVERWRITE = frozenset({
    "Proposal ID",
    "项目ID",
    "合同类型",
    "项目编码",
    "项目名称",
    "PD",
    "TD",
    "PCM",
    "客户",
})

_REL_XLSX = Path("早期介入") / "合同" / "输出结果" / "项目基础信息表.xlsx"

_ROLE_MEMBER_PATTERNS: dict[str, tuple[str, ...]] = {
    "DC": ("DC",),
    "L1工勘专家": ("L1工勘", "工勘专家", "L1"),
    "规划设计TL": ("规划设计", "规划设计TL"),
    "设备安装TL": ("设备安装", "设备安装TL"),
    "部署调测TL": ("部署调测", "部署调测TL"),
}


def project_basic_info_xlsx_path(project_id: str) -> Path:
    pid = (project_id or "").strip()
    if not pid:
        raise ValueError("缺少项目 ID")
    return business_root() / "projects" / pid / _REL_XLSX


def infer_contract_type(
    project: dict[str, Any],
    *,
    hint: str | None = None,
) -> str:
    if hint and hint.strip():
        return hint.strip()
    bid = str(project.get("bidCode") or "").strip()
    code = str(project.get("projectCode") or "").strip()
    if bid and not code:
        return "标准合同"
    if code and not bid:
        return "预销售合同"
    if bid:
        return "标准合同"
    return "预销售合同" if code else ""


def infer_contract_type_from_create(
    *,
    project_code: str | None,
    bid_code: str | None,
) -> str:
    code = (project_code or "").strip()
    bid = (bid_code or "").strip()
    if bid and not code:
        return "标准合同"
    if code and not bid:
        return "预销售合同"
    if bid:
        return "标准合同"
    return "预销售合同" if code else ""


def _member_display(member: dict[str, Any]) -> str:
    role_name = str(member.get("roleName") or "").strip()
    username = str(member.get("username") or "").strip()
    if role_name and username:
        return f"{role_name} / {username}"
    return role_name or username


def _find_member_by_patterns(
    members: list[dict[str, Any]] | None,
    patterns: tuple[str, ...],
) -> str:
    for member in members or []:
        role_code = str(member.get("roleCode") or "").upper()
        role_name = str(member.get("roleName") or "")
        for pattern in patterns:
            p = pattern.upper()
            if p in role_code or pattern in role_name:
                return _member_display(member)
    return ""


def _role_person(project: dict[str, Any], role_code: str, name_key: str) -> str:
    direct = str(project.get(name_key) or "").strip()
    if direct:
        return direct
    for member in project.get("members") or []:
        if str(member.get("roleCode") or "").upper() == role_code:
            return _member_display(member)
    return ""


def project_to_basic_info_row(
    project: dict[str, Any],
    *,
    contract_type_hint: str | None = None,
) -> dict[str, str]:
    project_id = str(project.get("projectId") or "").strip()
    members = project.get("members")
    if members is not None and not isinstance(members, list):
        members = None

    row = {
        "Proposal ID": str(project.get("bidCode") or "").strip(),
        "项目ID": project_id,
        "合同类型": infer_contract_type(project, hint=contract_type_hint),
        "项目编码": str(project.get("projectCode") or "").strip(),
        "项目名称": str(project.get("projectName") or "").strip(),
        "PD": _role_person(project, "PD", "pdName"),
        "TD": _role_person(project, "TD", "tdName"),
        "PCM": _role_person(project, "PCM", "pcmName"),
        "客户": str(project.get("customerName") or "").strip(),
        "DC": _find_member_by_patterns(members, _ROLE_MEMBER_PATTERNS["DC"]),
        "L1工勘专家": _find_member_by_patterns(members, _ROLE_MEMBER_PATTERNS["L1工勘专家"]),
        "规划设计TL": _find_member_by_patterns(members, _ROLE_MEMBER_PATTERNS["规划设计TL"]),
        "设备安装TL": _find_member_by_patterns(members, _ROLE_MEMBER_PATTERNS["设备安装TL"]),
        "部署调测TL": _find_member_by_patterns(members, _ROLE_MEMBER_PATTERNS["部署调测TL"]),
    }
    return {h: row.get(h, "") for h in BASIC_INFO_HEADERS}


def _read_existing_row(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        from openpyxl import load_workbook
    except ImportError:
        LOG.warning("openpyxl 未安装，无法读取已有项目基础信息表")
        return {}
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=1, max_row=2, values_only=True))
        wb.close()
    except (OSError, ValueError) as exc:
        LOG.warning("读取项目基础信息表失败 path=%s err=%s", path, exc)
        return {}
    if len(rows) < 2:
        return {}
    headers = [str(h or "").replace("\ufeff", "").strip() for h in rows[0]]
    values = rows[1]
    mapping = {
        h: ("" if v is None else str(v).strip())
        for h, v in zip(headers, values)
        if h
    }
    return {h: mapping.get(h, "") for h in BASIC_INFO_HEADERS}


def _merge_rows(existing: dict[str, str], fresh: dict[str, str]) -> dict[str, str]:
    merged = dict(existing)
    for header in BASIC_INFO_HEADERS:
        value = fresh.get(header, "")
        if header in _ALWAYS_OVERWRITE:
            if value:
                merged[header] = value
            elif header not in merged:
                merged[header] = ""
        elif value:
            merged[header] = value
        elif header not in merged:
            merged[header] = ""
    return {h: merged.get(h, "") for h in BASIC_INFO_HEADERS}


def _write_row(path: Path, row: dict[str, str]) -> None:
    from openpyxl import Workbook

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "项目基础信息"
    ws.append(list(BASIC_INFO_HEADERS))
    ws.append([row.get(h, "") for h in BASIC_INFO_HEADERS])
    wb.save(path)


def sync_project_basic_info_xlsx(
    project: dict[str, Any],
    *,
    contract_type_hint: str | None = None,
) -> Path:
    """将项目信息写入/更新到 早期介入/合同/输出结果/项目基础信息表.xlsx。"""
    project_id = str(project.get("projectId") or "").strip()
    if not project_id:
        raise ValueError("项目数据缺少 projectId")

    path = project_basic_info_xlsx_path(project_id)
    existing = _read_existing_row(path)
    fresh = project_to_basic_info_row(project, contract_type_hint=contract_type_hint)
    merged = _merge_rows(existing, fresh)
    _write_row(path, merged)
    LOG.info("项目基础信息表已同步 path=%s projectId=%s", path, project_id)
    return path
