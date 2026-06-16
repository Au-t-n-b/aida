"""OCC assumption info client used to resolve project code by Proposal ID."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

LOG = logging.getLogger(__name__)

APIGW_BASE = os.environ.get(
    "OCC_APIGW_BASE",
    "https://apigw-cn-south02.huawei.com/api/"
    "S00000000000000000000000000003172",
).rstrip("/")
ASSUMPTION_ENDPOINT = f"{APIGW_BASE}/occ_bid_assumption_info_f"


def _headers() -> dict[str, str]:
    return {
        "X-HW-ID": 'S007628',
        "X-HW-APPKEY": 'zGkt8E+49wjiz3EYCHVtcA==',
        "Content-Type": "application/json",
    }


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("list", "data", "result", "records", "rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            nested = _extract_records(value)
            if nested:
                return nested
    return []


def fetch_project_number_by_bid_code(bid_code: str) -> str | None:
    """Return OCC project_number for a Proposal ID, or None when unavailable."""
    proposal_id = (bid_code or "").strip()
    if not proposal_id:
        return None

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                ASSUMPTION_ENDPOINT,
                headers=_headers(),
                json={"bid_code": proposal_id},
            )
            resp.raise_for_status()
            payload = resp.json()
            LOG.info(payload)
    except (httpx.HTTPError, ValueError) as exc:
        LOG.warning("OCC assumption lookup failed bid_code=%s err=%s", proposal_id, exc)
        return None

    for record in _extract_records(payload):
        project_number = str(record.get("project_number") or "").strip()
        if project_number:
            return project_number
    return None