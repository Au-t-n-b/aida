from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any


def format_cell_table(cell_table: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Port of EODS risk-rule table formatting: headers + cell_values -> row dicts."""
    if not isinstance(cell_table, dict):
        return []
    headers = cell_table.get("headers") or []
    rows = cell_table.get("cell_values") or cell_table.get("cellValues") or []
    columns = [
        str(item.get("name") or item.get("apiName") or item.get("label") or "").strip()
        for item in headers
        if isinstance(item, dict)
    ]
    columns = [column for column in columns if column]
    if not columns:
        return [dict(row) for row in rows if isinstance(row, dict)]

    formatted: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            formatted.append({column: row.get(column) for column in columns})
        elif isinstance(row, (list, tuple)):
            formatted.append({column: row[index] if index < len(row) else None for index, column in enumerate(columns)})
    return formatted


def filter_repeated_risks(
    risk_data_arr: list[Any] | None,
    *,
    id_key: str = "rule_id",
    min_count: int = 3,
) -> list[dict[str, Any]]:
    """Port of EODS product-solution risk voting: keep risks appearing in >= min_count rounds."""
    risk_count: dict[str, dict[str, Any]] = {}
    for sub_array in risk_data_arr or []:
        if not isinstance(sub_array, list):
            continue
        seen_in_round: set[str] = set()
        for risk in sub_array:
            if not isinstance(risk, dict):
                continue
            rule_id = str(risk.get(id_key) or "").strip()
            if not rule_id or rule_id in seen_in_round:
                continue
            seen_in_round.add(rule_id)
            risk_count.setdefault(rule_id, {"risk": dict(risk), "count": 0})
            risk_count[rule_id]["count"] += 1
    return [
        item["risk"]
        for item in risk_count.values()
        if int(item.get("count") or 0) >= max(1, int(min_count))
    ]


def flatten_risk_arrays(arrays: list[Any] | None) -> list[dict[str, Any]]:
    """Port of EODS risk-result summary node."""
    flattened: list[dict[str, Any]] = []
    for item in arrays or []:
        if not isinstance(item, list):
            continue
        flattened.extend(dict(risk) for risk in item if isinstance(risk, dict))
    return flattened


def parse_llm_risk_output(
    quality_res: str | None,
    *,
    opportunity_code: str | None = None,
    bidding_code: str | None = None,
    create_time: str | None = None,
) -> list[dict[str, Any]]:
    """Port of EODS LLM-result formatting without invoking an LLM."""
    parsed = _extract_first_json_array(str(quality_res or ""))
    if not parsed:
        return []
    generated_at = create_time or (datetime.now() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    risks: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        risk = dict(item)
        risk_sub_type = str(risk.get("risk_sub_type") or "").strip()
        risk_point = str(risk.get("risk_point") or "").strip()
        risk["risk_code"] = f"{opportunity_code or ''}_{risk_sub_type}_{risk_point}"
        risk["opportunity_code"] = opportunity_code or ""
        risk["risk_status"] = "处理中"
        risk["risk_generation_mode"] = "AI工作流"
        risk["create_time"] = generated_at
        risk["risk_phase"] = "疑似"
        risk["risk_resource"] = "售前风险"
        risk["risk_response_measure"] = risk.get("countermeasure", "")
        risk["risk_rule_sub_category"] = risk_sub_type
        risk["bidding_code"] = bidding_code or ""
        risk.pop("risk_sub_type", None)
        risk.pop("countermeasure", None)
        risks.append(risk)
    return risks


def mark_ontology_result(result: dict[str, Any]) -> dict[str, Any]:
    """Annotate an ontology-derived result as the EODS presales-risk adapter output."""
    marked = dict(result)
    marked["engine"] = "eods_presales_risk"
    marked["sourceSummary"] = (
        "EODS deterministic node logic is reused locally; live facts and RiskRule rows are read "
        "through the ontology SDK facade."
    )
    return marked


def _extract_first_json_array(text: str) -> list[Any]:
    tail = text.split("</think>")[-1]
    start = tail.find("[")
    if start < 0:
        return []
    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(tail[start:])
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []
