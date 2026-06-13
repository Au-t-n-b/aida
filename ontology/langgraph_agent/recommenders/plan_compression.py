from __future__ import annotations

import json
import logging
import re
from typing import Any

from langgraph_agent.config import get_model_config
from langgraph_agent.llm import get_chat_llm


logger = logging.getLogger(__name__)


ALLOWED_PLAN_IDS = {
    "supply_frontload",
    "duration_top3_slack",
    "duration_global_proportional",
}


SYSTEM_PROMPT = """你是交付排期计划压缩决策顾问。
只允许从用户提供的三个 plan-compression tools 方案中选择一个 recommendedPlanId。
不要编造日期或变更；所有判断必须基于工具返回的量化依据、关键路径、风险和 mutation 预览。
必须只返回严格 JSON，不要 Markdown，不要解释前后缀。"""


def try_llm_recommend_plan_compression(
    *,
    project_id: str,
    strategies: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any] | None:
    """Ask the configured chat model to select one of the three plan tools."""

    cfg = get_model_config()
    logger.warning(
        "[plan_compression_llm] configured model=%s base_url=%s api_key_present=%s",
        cfg.model_name,
        cfg.base_url or "<default>",
        bool(cfg.api_key),
    )
    model = get_chat_llm()
    if model is None:
        logger.warning("[plan_compression_llm] model unavailable, fallback will be used")
        return None
    payload = {
        "projectId": project_id,
        "allowedRecommendedPlanIds": sorted(ALLOWED_PLAN_IDS),
        "warnings": warnings[:5],
        "strategies": [_compact_strategy(strategy) for strategy in strategies],
        "requiredOutput": {
            "recommendedPlanId": "one allowed id",
            "decisionAdvice": "short Chinese decision summary",
            "strategies": [
                {
                    "strategy_id": "matching id",
                    "recommendation_summary": "short Chinese summary",
                    "keyInformation": ["short facts"],
                    "cascading_risks": ["short risks"],
                }
            ],
        },
    }
    try:
        response = model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ]
        )
        response_metadata = getattr(response, "response_metadata", {}) or {}
        parsed = _parse_json_response(_message_content(response))
        validated = _validate_decision(parsed)
        logger.warning(
            "[plan_compression_llm] success configured_model=%s response_model=%s recommendedPlanId=%s",
            cfg.model_name,
            response_metadata.get("model_name") or response_metadata.get("model") or "<unknown>",
            validated.get("recommendedPlanId"),
        )
        return validated
    except Exception as exc:
        logger.exception(
            "[plan_compression_llm] failed model=%s base_url=%s error=%s",
            cfg.model_name,
            cfg.base_url or "<default>",
            exc,
        )
        return None


def _compact_strategy(strategy: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": strategy.get("strategy_id"),
        "title": strategy.get("title"),
        "toolName": strategy.get("toolName"),
        "toolInput": strategy.get("toolInput"),
        "toolStatus": strategy.get("toolStatus"),
        "recommendation_summary": strategy.get("recommendation_summary"),
        "keyInformation": list(strategy.get("keyInformation") or [])[:4],
        "quantitative_evidence": list(strategy.get("quantitative_evidence") or [])[:4],
        "cascading_risks": list(strategy.get("cascading_risks") or [])[:3],
        "parameter_overrides": dict(strategy.get("parameter_overrides") or {}),
        "phaseDetails": list(strategy.get("phaseDetails") or [])[:4],
        "actionable_mutations": list(strategy.get("actionable_mutations") or [])[:4],
        "proposedMutationCount": strategy.get("proposedMutationCount", 0),
    }


def _message_content(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        values: list[str] = []
        for item in content:
            if isinstance(item, dict):
                values.append(str(item.get("text") or item.get("content") or ""))
            else:
                values.append(str(item))
        return "\n".join(value for value in values if value)
    return str(content or "")


def _parse_json_response(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        raise ValueError("empty LLM response")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be an object")
    return parsed


def _validate_decision(value: dict[str, Any]) -> dict[str, Any]:
    recommended = str(value.get("recommendedPlanId") or "").strip()
    if recommended not in ALLOWED_PLAN_IDS:
        raise ValueError(f"invalid recommendedPlanId: {recommended}")
    decision_advice = str(value.get("decisionAdvice") or "").strip()
    strategies = value.get("strategies")
    if not isinstance(strategies, list):
        strategies = []
    clean_strategies: list[dict[str, Any]] = []
    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue
        strategy_id = str(strategy.get("strategy_id") or "").strip()
        if strategy_id not in ALLOWED_PLAN_IDS:
            continue
        clean_strategies.append(
            {
                "strategy_id": strategy_id,
                "recommendation_summary": str(strategy.get("recommendation_summary") or "").strip(),
                "keyInformation": _string_list(strategy.get("keyInformation")),
                "cascading_risks": _string_list(strategy.get("cascading_risks")),
            }
        )
    return {
        "recommendedPlanId": recommended,
        "decisionAdvice": decision_advice,
        "strategies": clean_strategies,
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:4]
