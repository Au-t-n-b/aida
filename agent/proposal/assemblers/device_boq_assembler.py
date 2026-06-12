"""Chapter 2 device BOQ assembler.

Consumes clone-boq stage-1 ``*.normalized.json`` outputs already present on disk.
Device model names come from ``categories[sort_no=1].name`` (split by ``&``).
§17 enrichment uses ``product_name`` → ``offering_no`` + GA/EOM/EOS (see device_info).
"""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from agent.proposal.draft_store import device_boq_parse_dir
from agent.proposal.models import DataSource, HardwareSubtype, ProductPartCategory

SERVICE_FILE_MARKERS = ("Service", "SBOQ", "CCAE", "年费", "集成", "布线")
SERVICE_CATEGORY_MARKERS = ("服务", "集成", "布线", "年费", "SBOQ")
_CATEGORY_SUFFIXES = (
    "核心交换机",
    "TOR 交换机",
    "交换机",
    "核心路由器",
    "路由器",
    "服务器",
    "存储",
)
DEFAULT_SUPERPOD_PACKAGING = {
    "A9US-33-HCZSC2A0L06": {
        "servers_per_container": 48,
        "device_model": "Atlas 900 A3",
    },
    "A99G-33-HEZSC1A0L05": {
        "servers_per_container": 12,
        "device_model": "Atlas 900 A3",
    },
    "A8GN-33-HDKSC2ACA6": {
        "servers_per_container": 6,
        "device_model": "Atlas 800T A3",
    },
}


def normalized_json_paths(project_id: str) -> list[Path]:
    parse_dir = device_boq_parse_dir(project_id)
    if not parse_dir.exists():
        return []
    return sorted(
        p
        for p in parse_dir.glob("*.normalized.json")
        if not p.name.endswith(".normalized.consistency.json")
        and not _is_service_file(p.name)
    )


def _is_service_file(name: str) -> bool:
    lowered = name.lower()
    return any(marker.lower() in lowered for marker in SERVICE_FILE_MARKERS)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _stage2_rules_path() -> Path | None:
    env_path = os.environ.get("CLONE_BOQ_STAGE2_RULES")
    if env_path:
        path = Path(env_path)
        return path if path.exists() else None
    candidates = [
        Path("D:/AIDA项目/skill/uniEx-bench/boQ-bench/SKILL/clone-boq/tools/demos/stage2-device-rows.rules.yaml"),
        Path("d:/AIDA项目/skill/uniEx-bench/boQ-bench/SKILL/clone-boq/tools/demos/stage2-device-rows.rules.yaml"),
    ]
    return next((p for p in candidates if p.exists()), None)


def _load_superpod_packaging_rules() -> dict[str, dict[str, Any]]:
    path = _stage2_rules_path()
    if path is None:
        return dict(DEFAULT_SUPERPOD_PACKAGING)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return dict(DEFAULT_SUPERPOD_PACKAGING)

    rules: dict[str, dict[str, Any]] = {}
    in_block = False
    current_code: str | None = None
    current_indent = 0
    for raw in lines:
        if raw.strip().startswith("packaging_by_sales_code:"):
            in_block = True
            current_code = None
            continue
        if not in_block:
            continue
        if raw and not raw.startswith(" "):
            break
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        code_match = re.match(r"([A-Za-z0-9_-]+):\s*$", stripped)
        indent = len(raw) - len(raw.lstrip(" "))
        if code_match and indent <= 4:
            current_code = code_match.group(1)
            current_indent = indent
            rules.setdefault(current_code, {})
            continue
        if current_code and indent > current_indent:
            kv = re.match(r"([A-Za-z0-9_]+):\s*(.+)$", stripped)
            if not kv:
                continue
            key, value = kv.group(1), kv.group(2).strip().strip('"')
            if value.isdigit():
                rules[current_code][key] = int(value)
            else:
                rules[current_code][key] = value

    return rules or dict(DEFAULT_SUPERPOD_PACKAGING)


def _text(*values: Any) -> str:
    return " ".join(str(v or "") for v in values)


def _is_service_leaf(leaf: dict[str, Any]) -> bool:
    if leaf.get("is_software") is True:
        return True
    text = _text(
        leaf.get("sales_code"),
        leaf.get("description"),
        leaf.get("parent_category"),
        leaf.get("remark"),
    ).lower()
    service_markers = (
        "服务", "软件", "license", "lic-", "lic_", "lic", "sns",
        "维保", "支持", "安装", "调测", "咨询",
    )
    return any(marker in text for marker in service_markers)


def _is_service_category_name(name: str) -> bool:
    return any(marker in name for marker in SERVICE_CATEGORY_MARKERS)


def _strip_category_suffix(segment: str) -> str:
    text = segment.strip()
    for suffix in _CATEGORY_SUFFIXES:
        if text.endswith(suffix):
            return text[: -len(suffix)].strip()
    return text


def category_level1_name(product: dict[str, Any]) -> str:
    """Return categories entry with sort_no=1 name, or empty string."""
    for cat in product.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        if str(cat.get("sort_no") or "").strip() == "1":
            return str(cat.get("name") or "").strip()
    return ""


def normalize_device_model_name(device_model: str) -> str:
    """Normalize extracted model name for display and §17 ``offering_name`` lookup.

    XH 系列在 BOQ 分类中写作 ``XH16800``，目录登记为 ``CloudEngine XH16800``。
    """
    model = device_model.strip()
    if re.match(r"^XH\d", model, re.IGNORECASE) and not model.lower().startswith("cloudengine"):
        return f"CloudEngine {model}"
    return model


def pbi_offering_name(device_model: str) -> str:
    """Alias kept for tests/call sites; same as ``normalize_device_model_name``."""
    return normalize_device_model_name(device_model)


def device_models_from_category_name(category_name: str) -> list[str]:
    """Split sort_no=1 category name into device model rows (XH 补全 CloudEngine 前缀).

    Example: ``CloudEngine 16800 & XH16800 核心交换机``
    → ``["CloudEngine 16800", "CloudEngine XH16800"]``
    """
    name = category_name.strip()
    if not name or _is_service_category_name(name):
        return []

    parts = [p.strip() for p in name.split("&") if p.strip()] if "&" in name else [name]
    models: list[str] = []
    for part in parts:
        cleaned = _strip_category_suffix(part)
        if cleaned and not _is_service_category_name(cleaned):
            models.append(normalize_device_model_name(cleaned))
    return models


def _superpod_packaging(
    sales_code: str,
    packaging_rules: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    for suffix, rule in packaging_rules.items():
        if suffix in sales_code:
            return rule
    return None


def _hardware_subtype(leaf: dict[str, Any]) -> HardwareSubtype:
    main_markers = ("主设备", "交换机", "SuperPoD", "超节点", "OceanStor", "服务器")
    text = _text(leaf.get("sales_code"), leaf.get("description"), leaf.get("parent_category"))
    if any(marker.lower() in text.lower() for marker in main_markers):
        return HardwareSubtype.MAIN_DEVICE
    return HardwareSubtype.COMPONENT


def _main_device_category_prefixes(product: dict[str, Any]) -> list[str]:
    prefixes: list[str] = []
    for cat in product.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        name = str(cat.get("name") or "")
        if "主设备" in name or "SuperPoD" in name:
            sort = str(cat.get("sort_no") or "").strip()
            if sort:
                prefixes.append(sort)
    return prefixes


def _leaf_sort_prefix(leaf: dict[str, Any]) -> str:
    parent = str(leaf.get("parent_category") or "").strip()
    return parent.split()[0] if parent else ""


def _leaf_under_category_prefix(leaf: dict[str, Any], prefix: str) -> bool:
    sort = _leaf_sort_prefix(leaf)
    return sort == prefix or sort.startswith(f"{prefix}.")


def _counts_toward_device_quantity(leaf: dict[str, Any], product: dict[str, Any]) -> bool:
    """Whether leaf qty contributes to chapter-2 device row quantity."""
    if _is_service_leaf(leaf):
        return False
    if _hardware_subtype(leaf) == HardwareSubtype.MAIN_DEVICE:
        return True
    parent = str(leaf.get("parent_category") or "")
    for prefix in _main_device_category_prefixes(product):
        if not _leaf_under_category_prefix(leaf, prefix):
            continue
        if "基本配置" in parent or leaf.get("cluster_expansion"):
            return True
    return False


def _device_role(path: Path, product: dict[str, Any]) -> str:
    name = path.name
    sheet = str(product.get("sheet") or product.get("product_head") or "")
    text = f"{name} {sheet}"
    if "网络" in text or "CE" in text or "CloudEngine" in text or "XH" in text:
        return "交换机"
    if "Atlas" in text or "SuperPoD" in text or "昇腾" in text:
        return "智算服务器"
    if "OceanStor" in text or "存储" in text:
        return "存储"
    return "主设备"


def _primary_part_code(product: dict[str, Any]) -> str:
    for leaf in product.get("leaves") or []:
        if not isinstance(leaf, dict) or not _counts_toward_device_quantity(leaf, product):
            continue
        part = str(leaf.get("part_number") or "").strip()
        if part:
            return part
    return ""


def _product_block_quantity(
    product: dict[str, Any],
    packaging_rules: dict[str, dict[str, Any]],
) -> float:
    total = 0.0
    for leaf in product.get("leaves") or []:
        if not isinstance(leaf, dict) or not _counts_toward_device_quantity(leaf, product):
            continue
        qty = float(leaf.get("total_qty") or 0)
        sales_code = str(leaf.get("sales_code") or "")
        packaging = _superpod_packaging(sales_code, packaging_rules)
        if packaging and packaging.get("servers_per_container"):
            qty *= float(packaging["servers_per_container"])
        total += qty
    return total


def _date_part(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)[:10]


def assemble_device_info(project_id: str) -> list[dict[str, Any]]:
    """Build device rows from sort_no=1 category names; productCode filled by §17 enrich."""
    aggregated: dict[tuple[str, str], dict[str, Any]] = {}
    packaging_rules = _load_superpod_packaging_rules()

    for path in normalized_json_paths(project_id):
        data = _load_json(path)
        if not data:
            continue
        for product in data.get("products") or []:
            if not isinstance(product, dict):
                continue

            category_name = category_level1_name(product)
            device_models = device_models_from_category_name(category_name)
            if not device_models:
                continue

            qty = _product_block_quantity(product, packaging_rules)
            role = _device_role(path, product)
            part_code = _primary_part_code(product)

            for device_model in device_models:
                key = (device_model, role)
                if key not in aggregated:
                    row_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "|".join(key)))
                    aggregated[key] = {
                        "rowId": row_id,
                        "deviceModel": device_model,
                        "productCode": "",
                        "quantity": 0.0,
                        "version": "",
                        "lifecycleStatus": "",
                        "gaActualDate": None,
                        "gaPlanDate": None,
                        "eomActualDate": None,
                        "eomPlanDate": None,
                        "eosActualDate": None,
                        "eosPlanDate": None,
                        "deviceUHeight": None,
                        "dataSource": DataSource.AUTO.value,
                        "proposalVersion": None,
                        "productPartCategory": ProductPartCategory.PRODUCT.value,
                        "partCode": part_code,
                        "hardwareSubtype": HardwareSubtype.MAIN_DEVICE.value,
                        "deviceRole": role,
                        "sourceFile": path.name,
                        "categoryName": category_name,
                        "pbiProductName": device_model,
                    }
                else:
                    source = aggregated[key].get("sourceFile") or ""
                    if path.name not in source.split(";"):
                        aggregated[key]["sourceFile"] = (
                            f"{source};{path.name}" if source else path.name
                        )
                    if not aggregated[key].get("partCode") and part_code:
                        aggregated[key]["partCode"] = part_code
                aggregated[key]["quantity"] += qty

    def _sort_key(row: dict[str, Any]) -> tuple[str, str]:
        return str(row.get("deviceRole") or ""), str(row.get("deviceModel") or "")

    return sorted(aggregated.values(), key=_sort_key)


def patch_enrichment(row: dict[str, Any], enrichment: dict[str, Any]) -> dict[str, Any]:
    """Apply §17 catalog (+ optional §2 lifecycle) fields in-place."""
    lifecycle = enrichment.get("lifecycle") or {}
    catalog = enrichment.get("catalog") or {}

    offering_no = str(
        catalog.get("offering_no") or catalog.get("offeringNo") or ""
    ).strip()
    if offering_no:
        row["productCode"] = offering_no

    row["version"] = str(
        lifecycle.get("edition_name")
        or lifecycle.get("editionName")
        or lifecycle.get("edition_code")
        or lifecycle.get("editionCode")
        or lifecycle.get("edition_no")
        or lifecycle.get("editionNo")
        or row.get("version")
        or ""
    )
    row["lifecycleStatus"] = str(
        lifecycle.get("offering_lifecycle_name")
        or lifecycle.get("offeringLifecycleName")
        or lifecycle.get("edition_lifecycle_name")
        or lifecycle.get("editionLifecycleName")
        or catalog.get("offering_lifecycle")
        or catalog.get("offeringLifecycle")
        or row.get("lifecycleStatus")
        or ""
    )
    row["gaActualDate"] = _date_part(catalog.get("offering_ga_actu") or catalog.get("offeringGaActu"))
    row["gaPlanDate"] = _date_part(catalog.get("offering_ga_plan") or catalog.get("offeringGaPlan"))
    row["eomActualDate"] = _date_part(catalog.get("offering_eom_actu") or catalog.get("offeringEomActu"))
    row["eomPlanDate"] = _date_part(catalog.get("offering_eom_plan") or catalog.get("offeringEomPlan"))
    row["eosActualDate"] = _date_part(catalog.get("offering_eos_actu") or catalog.get("offeringEosActu"))
    row["eosPlanDate"] = _date_part(catalog.get("offering_eos_plan") or catalog.get("offeringEosPlan"))
    return row
