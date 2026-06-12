"""8.3 L2 disassembler: normalized maintenance BOQ → 维保策略 rows."""
from __future__ import annotations

import re
import uuid
from typing import Any

from agent.proposal.assemblers.maint_date_calculator import (
    DEFAULT_WARRANTY_POLICY,
    compute_over_eos,
    default_start_date,
    end_date_from_start,
    format_iso_date,
)
from agent.proposal.assemblers.maint_device_bridge import (
    eos_date_from_device_row,
    match_product_model_to_device,
)
from agent.proposal.assemblers.service_boq_reader import load_normalized_boq
from agent.proposal.models import DataSource

_SLA_TIER_RE = re.compile(r"(金牌\+|银牌|白金)")
_MONTHS_IN_PART_RE = re.compile(r"(\d+)\(M\)")
_SERVICE_SEGMENT_RE = re.compile(
    r"(Hi-Care高级服务|服务器介质保留服务|[\u4e00-\u9fffA-Za-z0-9+]+服务)"
)


def _extract_maint_years(leaf: dict[str, Any]) -> int:
    part = leaf.get("part_number") or ""
    m = _MONTHS_IN_PART_RE.search(part)
    if m:
        months = int(m.group(1))
        return max(1, round(months / 12)) if months >= 12 else 1

    unit_qty = leaf.get("unit_qty")
    if unit_qty and int(unit_qty) > 0:
        months = int(unit_qty)
        return max(1, round(months / 12)) if months >= 12 else 1

    unit = (leaf.get("unit") or "").strip()
    total_qty = float(leaf.get("total_qty") or 0)
    if unit in ("年", "PCS/年") and total_qty > 0:
        return int(total_qty)
    if unit == "月" and total_qty > 0:
        return max(1, round(total_qty / 12))
    return max(1, int(total_qty)) if total_qty >= 1 else 1


def _extract_service_name(description: str) -> str:
    for m in _SERVICE_SEGMENT_RE.finditer(description):
        name = m.group(1)
        if _SLA_TIER_RE.search(name):
            continue
        return name
    parts = [p for p in description.split("-") if p.strip()]
    for part in parts:
        if "服务" in part and not _SLA_TIER_RE.search(part):
            return part.strip()
    return parts[-2].strip() if len(parts) >= 2 else description


def _extract_product_model(leaf: dict[str, Any], offering_name: str | None) -> str:
    if offering_name:
        return offering_name
    desc = leaf.get("description") or ""
    head = desc.split("-", 1)[0].strip()
    if head:
        return head
    return desc


def _offering_name_for_leaf(product: dict[str, Any], leaf: dict[str, Any]) -> str | None:
    parent_sort = (leaf.get("parent_category") or "").split(" ", 1)[0].strip()
    for offering in product.get("leaves") or []:
        if offering.get("row_type") != "offering":
            continue
        sort_no = offering.get("sort_no") or ""
        if parent_sort and sort_no.startswith(parent_sort):
            desc = (offering.get("description") or "").strip()
            if desc:
                return desc
    for cat in product.get("categories") or []:
        if cat.get("level") == 2:
            return cat.get("name")
    return None


def _is_maintenance_component(leaf: dict[str, Any]) -> bool:
    return leaf.get("row_type") == "component" and not leaf.get("is_logistics")


def disassemble_maintenance_strategy(
    project_id: str,
    *,
    allowed_device_models: set[str] | None = None,
    device_rows_by_model: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    boq = load_normalized_boq(project_id)
    if not boq:
        return []

    start = default_start_date()
    rows: list[dict[str, Any]] = []
    seq = 0

    for product in boq.get("products") or []:
        if product.get("boq_product_type") != "maintenance":
            continue

        for leaf in product.get("leaves") or []:
            if not _is_maintenance_component(leaf):
                continue

            offering_name = _offering_name_for_leaf(product, leaf)
            product_model_raw = _extract_product_model(leaf, offering_name)
            if allowed_device_models is not None:
                matched = match_product_model_to_device(
                    product_model_raw,
                    allowed_device_models,
                )
                if matched is None:
                    continue
                product_model = matched
            else:
                product_model = product_model_raw

            seq += 1
            years = _extract_maint_years(leaf)
            service_name = _extract_service_name(leaf.get("description") or "")
            maint_end = end_date_from_start(start, years)

            eos_str: str | None = None
            if device_rows_by_model:
                device_row = device_rows_by_model.get(product_model)
                if device_row:
                    eos_str = eos_date_from_device_row(device_row)

            eos_date = None
            if eos_str:
                try:
                    from datetime import date
                    eos_date = date.fromisoformat(eos_str[:10])
                except ValueError:
                    eos_date = None

            rows.append({
                "rowId": str(uuid.uuid4()),
                "seq": seq,
                "productModel": product_model,
                "warrantyPolicy": DEFAULT_WARRANTY_POLICY,
                "maintenancePolicy": f"{years} 年 {service_name}",
                "maintYears": years,
                "maintTypeCode": None,
                "maintStartDate": format_iso_date(start),
                "maintEndDate": format_iso_date(maint_end),
                "productEosDate": eos_str,
                "overEos": compute_over_eos(eos_date, maint_end).value,
                "overEosApproval": "—",
                "dataSource": DataSource.AUTO.value,
                "proposalVersion": None,
            })

    return rows
