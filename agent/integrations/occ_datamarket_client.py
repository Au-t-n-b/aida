"""PBI DataMarket client — §2 lifecycle + §17 catalog for chapter 2 / 8.3."""
from __future__ import annotations

import logging
import os
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

def _debug_log(hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    # region agent log
    try:
        payload = {
            "sessionId": "5609cc",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        Path("debug-5609cc.log").open("a", encoding="utf-8").write(
            json.dumps(payload, ensure_ascii=False) + "\n"
        )
    except Exception:
        pass
    # endregion


# v3 文档写 http，但网关已强制 https；走系统代理常会 504（HIS Proxy）
_DEFAULT_APIGW_BASE = (
    "https://apigw-cn-south02.huawei.com/api/"
    "S00000000000000000000000000003172"
)
APIGW_BASE = os.environ.get("OCC_APIGW_BASE", _DEFAULT_APIGW_BASE).rstrip("/")
CATALOG_ENDPOINT = f"{APIGW_BASE}/occ_pbi_full_sales_catalog_f"
LIFECYCLE_ENDPOINT = f"{APIGW_BASE}/occ_prod_lifecycle_status_info_f"


def _http_client() -> httpx.Client:
    """Direct connect by default — corporate HTTP_PROXY breaks apigw with 504."""
    trust_env = os.environ.get("OCC_TRUST_ENV", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return httpx.Client(timeout=8.0, trust_env=trust_env)


def _credentials_configured() -> bool:
    return bool(os.environ.get("OCC_HW_ID") and os.environ.get("OCC_HW_APPKEY"))


def _headers() -> dict[str, str]:
    return {
        "X-HW-ID": os.environ["OCC_HW_ID"],
        "X-HW-APPKEY": os.environ["OCC_HW_APPKEY"],
        "Content-Type": "application/json",
    }


def _extract_records(data: Any) -> list[dict[str, Any]]:
    """Normalize DataMarket response shapes to a list of row dicts."""
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if not isinstance(data, dict):
        return []

    for key in ("data", "result", "records", "rows", "list"):
        val = data.get(key)
        if isinstance(val, list):
            return [row for row in val if isinstance(row, dict)]
        if isinstance(val, dict):
            nested = _extract_records(val)
            if nested:
                return nested

    status = str(data.get("status") or data.get("code") or "").lower()
    if status in {"success", "0", "200", "ok"}:
        for key in ("data", "result"):
            nested = _extract_records(data.get(key))
            if nested:
                return nested

    if any(
        key in data
        for key in (
            "offering_no",
            "offeringNo",
            "offering_lifecycle_name",
            "offering_ga_actu",
            "offering_eos_actu",
        )
    ):
        return [data]
    return []


def _first_record(data: Any) -> dict[str, Any] | None:
    records = _extract_records(data)
    return records[0] if records else None


def _pick_catalog_record(offering_name: str, data: Any) -> dict[str, Any] | None:
    """Pick one §17 row; prefer exact ``offering_name`` match and GA lifecycle."""
    records = _extract_records(data)
    if not records:
        return None

    needle = offering_name.strip()
    exact = [
        row
        for row in records
        if str(row.get("offering_name") or row.get("offeringName") or "").strip() == needle
    ]
    pool = exact or records

    by_offering: dict[str, dict[str, Any]] = {}
    for row in pool:
        offering_no = str(row.get("offering_no") or row.get("offeringNo") or "").strip()
        if not offering_no:
            continue
        lifecycle = str(row.get("offering_lifecycle") or row.get("offeringLifecycle") or "").upper()
        prev = by_offering.get(offering_no)
        if prev is None or lifecycle == "GA":
            by_offering[offering_no] = row

    if not by_offering:
        return pool[0]

    for row in by_offering.values():
        if str(row.get("offering_lifecycle") or row.get("offeringLifecycle") or "").upper() == "GA":
            return row
    return next(iter(by_offering.values()))


def _post_json(endpoint: str, body: dict[str, Any]) -> dict[str, Any] | None:
    try:
        with _http_client() as client:
            resp = client.post(endpoint, headers=_headers(), json=body)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200]
        _debug_log(
            "H3",
            "agent/integrations/occ_datamarket_client.py:152",
            "occ endpoint http status error",
            {
                "endpoint": endpoint.rsplit("/", 1)[-1],
                "statusCode": exc.response.status_code,
                "detail": detail,
            },
        )
        logger.warning(
            "OCC request failed status=%s endpoint=%s body=%s detail=%s",
            exc.response.status_code,
            endpoint.rsplit("/", 1)[-1],
            body,
            detail,
        )
        return None
    except (httpx.HTTPError, ValueError) as exc:
        _debug_log(
            "H3",
            "agent/integrations/occ_datamarket_client.py:167",
            "occ endpoint request exception",
            {
                "endpoint": endpoint.rsplit("/", 1)[-1],
                "error": str(exc),
            },
        )
        logger.warning(
            "OCC request error endpoint=%s body=%s err=%s",
            endpoint.rsplit("/", 1)[-1],
            body,
            exc,
        )
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("code") == 200 and not _extract_records(payload):
        logger.info(
            "OCC empty result endpoint=%s body=%s errorMsg=%s",
            endpoint.rsplit("/", 1)[-1],
            body,
            payload.get("errorMsg"),
        )
    return payload


def fetch_offering_eos(offering_no: str) -> str | None:
    """Return EOS date (ISO) or None if unavailable."""
    row = fetch_catalog_row(offering_no)
    if not row:
        return None
    actu = row.get("offering_eos_actu") or row.get("offeringEosActu")
    plan = row.get("offering_eos_plan") or row.get("offeringEosPlan")
    chosen = actu or plan
    if not chosen:
        return None
    return str(chosen)[:10]


def fetch_lifecycle_row(data_type: str, offering_no: str) -> dict[str, Any] | None:
    """Return lifecycle row from §2 or None if unavailable."""
    if not offering_no or not _credentials_configured():
        return None
    payload = _post_json(
        LIFECYCLE_ENDPOINT,
        {"data_type": data_type, "offering_no": offering_no},
    )
    if payload is None:
        return None
    return _first_record(payload)


def fetch_catalog_row(offering_no: str) -> dict[str, Any] | None:
    """Return PBI full sales catalog row from §17 or None if unavailable."""
    if not offering_no or not _credentials_configured():
        return None
    payload = _post_json(CATALOG_ENDPOINT, {"offering_no": offering_no})
    if payload is None:
        return None
    return _first_record(payload)


def offering_name_lookup_candidates(offering_name: str) -> list[str]:
    """Build §17 lookup candidates (assembler 已补全 CloudEngine 前缀，此处仅兜底)."""
    name = offering_name.strip()
    if not name:
        return []
    candidates = [name]
    if re.match(r"^XH\d", name, re.IGNORECASE) and not name.lower().startswith("cloudengine"):
        prefixed = f"CloudEngine {name}"
        if prefixed not in candidates:
            candidates.append(prefixed)
    return candidates


def fetch_catalog_by_offering_name(offering_name: str) -> dict[str, Any] | None:
    """Return §17 catalog row by ``offering_name``（产品名称·政企，三选一入参）."""
    if not offering_name or not _credentials_configured():
        return None
    for candidate in offering_name_lookup_candidates(offering_name):
        payload = _post_json(CATALOG_ENDPOINT, {"offering_name": candidate})
        if payload is None:
            continue
        row = _pick_catalog_record(candidate, payload)
        if row:
            return row
    return None


def fetch_catalog_by_product_name(product_name: str) -> dict[str, Any] | None:
    """Alias for ``fetch_catalog_by_offering_name`` (legacy call sites)."""
    return fetch_catalog_by_offering_name(product_name)


def batch_fetch_device_enrichment(
    requests: list[tuple[str, str]],
) -> tuple[dict[str, dict[str, dict[str, Any] | None]], bool]:
    """Return offering_no → {lifecycle, catalog}, plus dependency failure flag."""
    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for data_type, offering_no in requests:
        key = (data_type, offering_no)
        if offering_no and key not in seen:
            unique.append(key)
            seen.add(key)

    if not _credentials_configured():
        return {
            offering_no: {"lifecycle": None, "catalog": None}
            for _data_type, offering_no in unique
        }, bool(unique)

    result: dict[str, dict[str, dict[str, Any] | None]] = {
        offering_no: {"lifecycle": None, "catalog": None}
        for _data_type, offering_no in unique
    }
    had_failure = False

    def _fetch_pair(data_type: str, offering_no: str) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
        return offering_no, fetch_lifecycle_row(data_type, offering_no), fetch_catalog_row(offering_no)

    workers = min(6, max(1, len(unique)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_fetch_pair, data_type, offering_no)
            for data_type, offering_no in unique
        ]
        for future in as_completed(futures):
            offering_no, lifecycle, catalog = future.result()
            result[offering_no] = {"lifecycle": lifecycle, "catalog": catalog}
            if lifecycle is None and catalog is None:
                had_failure = True
    return result, had_failure


def batch_fetch_eos(offering_nos: list[str]) -> tuple[dict[str, str | None], bool]:
    """Return (offering_no → eos_date, had_dependency_failure)."""
    if not _credentials_configured():
        return {no: None for no in offering_nos}, True

    result: dict[str, str | None] = {}
    had_failure = False
    for no in offering_nos:
        if not no:
            continue
        eos = fetch_offering_eos(no)
        result[no] = eos
        if eos is None:
            had_failure = True
    return result, had_failure
