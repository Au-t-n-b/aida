"""8.2 service content transform rules (split, filter, unit inference)."""
from __future__ import annotations

import re
from typing import Any

_BAD_SERVICE_TEXT_RE = re.compile(r"服务启动有效时长")
_EACH_SUPERPOD_RE = re.compile(
    r"每个SuperPoD\s*(?:\s*包含|服务内容包含)[：:]?\s*(.+)$",
    re.DOTALL,
)
_NUMBERED_ITEM_RE = re.compile(r"\d+[、.](.+?)(?=\s*\d+[、.]|$)")
_UNIT_SUFFIX_RE = re.compile(
    r"(每节点|每套|每(?:人年|人月|次|年|月)|人年|人月|(?:\d+)?套|次|节点|月|年)$"
)
_SUPERPOD_SCOPE_RE = re.compile(r"[（(]\s*\d+\s*SuperPoD", re.IGNORECASE)
_L1_UNIT_OVERRIDES: dict[str, str] = {
    "专项/单次服务": "次",
    "卓悦服务": "套",
}


def is_bad_service_text(text: str) -> bool:
    """Skip rows polluted by BOQ category naming errors."""
    return bool(_BAD_SERVICE_TEXT_RE.search(text or ""))


def split_service_content(description: str) -> list[str]:
    """Split composite SuperPoD / cluster integration descriptions into line items."""
    text = (description or "").strip()
    if not text:
        return []

    match = _EACH_SUPERPOD_RE.search(text)
    if not match:
        return [text]

    body = match.group(1).replace("\n", " ").strip()
    prefix = text[: match.start()].rstrip(" -，,")

    numbered = [item.strip() for item in _NUMBERED_ITEM_RE.findall(body) if item.strip()]
    if len(numbered) >= 2:
        return [_join_prefix(prefix, item) for item in numbered]

    if "、" in body and not re.search(r"\d+[、.]", body):
        parts = [part.strip() for part in body.split("、") if part.strip()]
        if len(parts) >= 2:
            return [_join_prefix(prefix, part) for part in parts]

    return [text]


def _join_prefix(prefix: str, item: str) -> str:
    if prefix:
        return f"{prefix} - {item}"
    return item


def infer_unit(leaf: dict[str, Any], description: str, *, l1_name: str = "") -> str:
    """Infer display unit when normalized.json leaves unit empty."""
    override = _L1_UNIT_OVERRIDES.get(l1_name)
    if override:
        return override

    explicit = (leaf.get("unit") or "").strip()
    if explicit:
        return explicit

    desc = description or ""
    if "每节点" in desc:
        return "节点"
    if "每套" in desc:
        return "套"
    if "人年" in desc:
        return "人年"
    if "人月" in desc:
        return "人月"
    if re.search(r"\d+（月）", desc):
        return "月"
    if "单次" in desc or re.search(r"专项/单次", desc):
        return "次"
    if _SUPERPOD_SCOPE_RE.search(desc):
        return "套"

    tail = desc.rsplit("-", 1)[-1].strip()
    unit_match = _UNIT_SUFFIX_RE.search(tail)
    if unit_match:
        token = unit_match.group(1)
        if token.startswith("每"):
            return token[1:]
        return token

    return ""


def infer_quantity(leaf: dict[str, Any], description: str) -> float:
    """Resolve quantity from leaf fields with description fallbacks."""
    total_qty = leaf.get("total_qty")
    if total_qty is not None and float(total_qty) > 0:
        return float(total_qty)

    unit_qty = leaf.get("unit_qty")
    if unit_qty is not None and float(unit_qty) > 0:
        return float(unit_qty)

    desc = description or ""
    pack_match = re.search(r"服务包数量[：:]\s*(\d+(?:\.\d+)?)", desc)
    if pack_match:
        return float(pack_match.group(1))

    person_month = re.search(r"(\d+(?:\.\d+)?)\s*人\s*(\d+(?:\.\d+)?)\s*月", desc)
    if person_month:
        return float(person_month.group(1)) * float(person_month.group(2))

    return 0.0


def rollup_l1_quantity_unit(
    children: list[dict[str, Any]],
    *,
    l1_name: str = "",
) -> tuple[float, str]:
    """Derive L1 quantity/unit from assembled L2 children."""
    override_unit = _L1_UNIT_OVERRIDES.get(l1_name, "")
    if not children:
        return 0.0, override_unit

    units = [c.get("unit") or "" for c in children]
    unit = override_unit or (max(set(units), key=units.count) if units else "")

    by_sale: dict[str, float] = {}
    for child in children:
        key = child.get("saleCode") or child.get("rowId") or ""
        qty = float(child.get("quantity") or 0)
        by_sale[key] = max(by_sale.get(key, 0.0), qty)

    if by_sale:
        quantities = list(by_sale.values())
        if len(by_sale) < len(children):
            qty = max(quantities)
        elif len(set(quantities)) == 1:
            qty = quantities[0]
        else:
            qty = sum(quantities)
    else:
        qty = 0.0

    return qty, unit
