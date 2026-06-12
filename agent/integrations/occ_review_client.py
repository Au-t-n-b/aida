"""DataMarket client for DTRB/DRB review info used by proposal version tagging."""
from __future__ import annotations

import os
from typing import Any

import httpx

APIGW_BASE = os.environ.get(
    "OCC_APIGW_BASE",
    "https://apigw-cn-south02.huawei.com/api/"
    "S00000000000000000000000000003172",
).rstrip("/")
DTRB_ENDPOINT = f"{APIGW_BASE}/occ_bid_dtrb_review_info_f"
DRB_ENDPOINT = f"{APIGW_BASE}/occ_bid_drb_review_info_f"

_DONE_STATUS = {"完成", "已完成", "通过", "不通过", "驳回", "closed", "done", "complete"}


def _credentials_configured() -> bool:
    return bool(os.environ.get("OCC_HW_ID") and os.environ.get("OCC_HW_APPKEY"))


def _headers() -> dict[str, str]:
    return {
        "X-HW-ID": os.environ["OCC_HW_ID"],
        "X-HW-APPKEY": os.environ["OCC_HW_APPKEY"],
        "Content-Type": "application/json",
    }


def _extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("data") or payload.get("result") or payload.get("list") or []
    if isinstance(rows, dict):
        return [rows]
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def _fetch_records(endpoint: str, project_code: str) -> list[dict[str, Any]]:
    if not project_code or not _credentials_configured():
        return []
    try:
        trust_env = os.environ.get("OCC_TRUST_ENV", "").strip().lower() in {"1", "true", "yes"}
        with httpx.Client(timeout=10.0, trust_env=trust_env) as client:
            resp = client.post(
                endpoint,
                headers=_headers(),
                json={"project_code": project_code},
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
    except (httpx.HTTPError, ValueError):
        return []
    return _extract_records(data)


def _is_pre_review(record: dict[str, Any], order_key: str) -> bool:
    order_no = str(record.get(order_key) or "").strip()
    if not order_no:
        return False

    status = str(record.get("review_status") or "").strip().lower()
    conclusion = str(record.get("review_conclusion") or "").strip()
    if conclusion:
        return False
    if status and status in _DONE_STATUS:
        return False
    return True


def _latest(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    return max(records, key=lambda row: str(row.get("start_time") or ""))


def resolve_review_tag(project_code: str) -> str | None:
    """
    Return review tag suffix without underscore.

    Priority: DRB first, then DTRB (closer to final release gate).
    """
    drb = _latest(_fetch_records(DRB_ENDPOINT, project_code))
    if drb and _is_pre_review(drb, "drx_number"):
        return "DRB"

    dtrb = _latest(_fetch_records(DTRB_ENDPOINT, project_code))
    if dtrb and _is_pre_review(dtrb, "dtr_no"):
        return "DTRB"

    return None

