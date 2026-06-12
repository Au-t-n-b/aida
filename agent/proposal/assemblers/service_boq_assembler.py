"""8.2 L2 assembler: normalized service BOQ → 服务内容 rows."""
from __future__ import annotations

import uuid
from typing import Any

from agent.proposal.assemblers.service_boq_reader import load_normalized_boq
from agent.proposal.assemblers.service_content_rules import (
    infer_quantity,
    infer_unit,
    is_bad_service_text,
    rollup_l1_quantity_unit,
    split_service_content,
)
from agent.proposal.models import DataSource, RowLevel


def _is_service_component(leaf: dict[str, Any]) -> bool:
    return (
        leaf.get("row_type") == "component"
        and not leaf.get("is_logistics")
    )


def _l1_categories(product: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in product.get("categories") or [] if c.get("level") == 2]


def _parent_l1_sort_for_leaf(leaf: dict[str, Any]) -> str | None:
    parent = leaf.get("parent_category") or ""
    if not parent:
        return None
    child_sort = parent.split(" ", 1)[0].strip()
    if "." in child_sort:
        return child_sort.split(".", 1)[0]
    return child_sort


def _category_name_for_sort(product: dict[str, Any], sort_no: str) -> str | None:
    for cat in _l1_categories(product):
        if (cat.get("sort_no") or "") == sort_no:
            name = (cat.get("name") or "").strip()
            return name or None
    return None


def _leaf_l1_name(product: dict[str, Any], leaf: dict[str, Any]) -> str:
    parent_sort = _parent_l1_sort_for_leaf(leaf)
    if parent_sort:
        name = _category_name_for_sort(product, parent_sort)
        if name:
            return name
    parent_category = leaf.get("parent_category") or ""
    if parent_category:
        return parent_category.split(" ", 1)[-1].strip()
    for cat in _l1_categories(product):
        name = (cat.get("name") or "").strip()
        if name:
            return name
    return ""


def _make_l1_row(name: str, *, internal_seq: str) -> dict[str, Any]:
    return {
        "rowId": str(uuid.uuid4()),
        "serviceName": name,
        "serviceContent": name,
        "quantity": 0.0,
        "unit": "",
        "rowLevel": RowLevel.L1.value,
        "parentRowId": None,
        "saleCode": None,
        "internalSeq": internal_seq,
        "dataSource": DataSource.AUTO.value,
        "proposalVersion": None,
    }


def _make_l2_row(
    *,
    l1_name: str,
    content: str,
    parent_id: str,
    leaf: dict[str, Any],
) -> dict[str, Any]:
    quantity = infer_quantity(leaf, content)
    unit = infer_unit(leaf, content, l1_name=l1_name)
    return {
        "rowId": str(uuid.uuid4()),
        "serviceName": l1_name,
        "serviceContent": content,
        "quantity": quantity,
        "unit": unit,
        "rowLevel": RowLevel.L2.value,
        "parentRowId": parent_id,
        "saleCode": leaf.get("sales_code") or None,
        "internalSeq": leaf.get("internal_seq"),
        "dataSource": DataSource.AUTO.value,
        "proposalVersion": None,
    }


def assemble_service_content(project_id: str) -> list[dict[str, Any]]:
    boq = load_normalized_boq(project_id)
    if not boq:
        return []

    l1_by_name: dict[str, dict[str, Any]] = {}
    l2_rows: list[dict[str, Any]] = []

    for product in boq.get("products") or []:
        if product.get("boq_product_type") != "service":
            continue

        product_l1: dict[str, str] = {}
        for cat in _l1_categories(product):
            name = (cat.get("name") or "").strip()
            if not name or is_bad_service_text(name):
                continue

            sort_no = cat.get("sort_no") or ""
            if name not in l1_by_name:
                l1_by_name[name] = _make_l1_row(name, internal_seq=sort_no)
            product_l1[sort_no] = l1_by_name[name]["rowId"]

        for leaf in product.get("leaves") or []:
            if not _is_service_component(leaf):
                continue

            description = (leaf.get("description") or "").strip()
            if not description or is_bad_service_text(description):
                continue

            l1_name = _leaf_l1_name(product, leaf)
            if not l1_name or is_bad_service_text(l1_name):
                continue

            if l1_name not in l1_by_name:
                parent_sort = _parent_l1_sort_for_leaf(leaf) or ""
                l1_by_name[l1_name] = _make_l1_row(l1_name, internal_seq=parent_sort)

            parent_id = l1_by_name[l1_name]["rowId"]
            parent_sort = _parent_l1_sort_for_leaf(leaf)
            if parent_sort and parent_sort in product_l1:
                parent_id = product_l1[parent_sort]

            for content in split_service_content(description):
                l2_rows.append(
                    _make_l2_row(
                        l1_name=l1_name,
                        content=content,
                        parent_id=parent_id,
                        leaf=leaf,
                    )
                )

    rows: list[dict[str, Any]] = list(l1_by_name.values())
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for row in l2_rows:
        parent_id = row.get("parentRowId")
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(row)

    for l1 in rows:
        children = children_by_parent.get(l1["rowId"], [])
        qty, unit = rollup_l1_quantity_unit(children, l1_name=l1.get("serviceName") or "")
        if qty > 0:
            l1["quantity"] = qty
        if unit:
            l1["unit"] = unit

    rows.extend(l2_rows)
    return rows
