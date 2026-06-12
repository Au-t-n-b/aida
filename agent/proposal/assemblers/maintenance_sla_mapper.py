"""8.4 L2 mapper: sla-extract JSON → maintenance SLA draft rows."""
from __future__ import annotations

import uuid
from typing import Any

from agent.proposal.models import DataSource

HEADER_KEYWORDS = {
    "问题级别", "问题等级", "服务时段", "响应时间", "响应时长",
    "恢复时间", "恢复时长", "2恢复时间", "解决时间", "解决时长",
}

EMPTY_MARKERS = {"", "-", "—", "N/A", "n/a", "NA", "na", "－"}

SERVICE_LEVEL_PATTERNS = [
    ("白金+", "白金+"),
    ("金牌+", "金牌+"),
    ("标准+", "标准+"),
    ("白金", "白金"),
    ("金牌", "金牌"),
    ("银牌", "银牌"),
    ("标准", "标准"),
]

DEFAULT_SERVICE_LEVEL = "金牌"


def _is_empty(value: str | None) -> bool:
    return (value or "").strip() in EMPTY_MARKERS


def normalize_coverage_period(value: str | None) -> str:
    """运营商格式常见「7×24×365提供服务」→ 展示「7×24×365」。"""
    text = (value or "").strip()
    if text.endswith("提供服务"):
        text = text[: -len("提供服务")].strip()
    return text


def extract_service_level_from_title(title: str) -> str:
    for needle, label in SERVICE_LEVEL_PATTERNS:
        if needle in title:
            return label
    return ""


def select_sla_table(
    tables: list[dict[str, Any]],
    *,
    service_level: str | None = None,
) -> dict[str, Any] | None:
    if not tables:
        return None
    if len(tables) == 1:
        return tables[0]

    preferred = (service_level or DEFAULT_SERVICE_LEVEL).strip()
    if preferred:
        for table in tables:
            title = table.get("title") or ""
            level = extract_service_level_from_title(title)
            if level == preferred or preferred in title:
                return table

    for table in tables:
        title = table.get("title") or ""
        if DEFAULT_SERVICE_LEVEL in title:
            return table

    return tables[0]


def _extract_hardware_support(records: list[dict[str, Any]]) -> str:
    for rec in records:
        service = (rec.get("service") or "").strip()
        if "硬件支持" in service:
            period = normalize_coverage_period(rec.get("service_period"))
            if not _is_empty(period):
                return period
    return ""


def _should_skip_record(rec: dict[str, Any]) -> bool:
    level = (rec.get("problem_level") or "").strip()
    if level in HEADER_KEYWORDS:
        return True
    service = (rec.get("service") or "").strip()
    if "硬件支持" in service:
        return True
    # §8.4：仅跳过 problem_level=NA 且各时限均为空的占位行
    if level == "NA" and all(
        _is_empty(rec.get(key))
        for key in ("service_period", "response_time", "recovery_time", "resolution_time")
    ):
        return True
    if _is_empty(level) and _is_empty(rec.get("service_period")):
        return True
    return False


def map_sla_parse_to_draft(
    parse_json: dict[str, Any],
    *,
    service_level: str | None = None,
) -> dict[str, Any]:
    tables = list(parse_json.get("tables") or [])
    table = select_sla_table(tables, service_level=service_level)
    if table is None:
        return {"hardwareSupport": "", "serviceLevel": "", "rows": []}

    records = list(table.get("records") or [])
    title = table.get("title") or ""
    resolved_level = extract_service_level_from_title(title) or (service_level or "")
    hardware = _extract_hardware_support(records)

    rows: list[dict[str, Any]] = []
    for rec in records:
        if _should_skip_record(rec):
            continue
        service_item = (rec.get("service") or "").strip()
        rows.append({
            "rowId": str(uuid.uuid4()),
            "seq": (rec.get("no") or "1").strip(),
            "severityLevel": (rec.get("problem_level") or "").strip() or "NA",
            "coveragePeriod": normalize_coverage_period(rec.get("service_period")),
            "responseTime": (rec.get("response_time") or "").strip(),
            "restoreTime": (rec.get("recovery_time") or "").strip(),
            "resolveTime": (rec.get("resolution_time") or "").strip(),
            "serviceItem": service_item or None,
            "dataSource": DataSource.AUTO.value,
            "proposalVersion": None,
        })

    return {
        "hardwareSupport": hardware,
        "serviceLevel": resolved_level,
        "rows": rows,
    }
