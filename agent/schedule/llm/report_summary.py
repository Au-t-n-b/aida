from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from agent.schedule.llm.bailian import DEFAULT_BAILIAN_MODEL, ChatMessage, LlmCallError, ReportSummaryClient
from agent.schedule.contracts.report_summary import (
    ReportSummaryRequest,
    ReportSummaryResponse,
    ReportSummarySection,
)


def generate_report_summary_text(
    payload: ReportSummaryRequest,
    client: ReportSummaryClient,
    *,
    model: str = DEFAULT_BAILIAN_MODEL,
) -> ReportSummaryResponse:
    content = client.complete(_messages(payload), model=model)
    parsed = _parse_model_json(content)
    summary_text = parsed.get("summary_text")
    if not isinstance(summary_text, str) or not summary_text.strip():
        raise LlmCallError("模型响应缺少 summary_text。")

    sections = _parse_sections(parsed.get("action_suggestions"))
    return ReportSummaryResponse(
        summary_text=summary_text.strip(),
        action_suggestions=sections,
        is_ai_generated=True,
        model=model,
        generated_at=datetime.now(timezone.utc),
    )


def _messages(payload: ReportSummaryRequest) -> list[ChatMessage]:
    data = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
    return [
        {
            "role": "system",
            "content": (
                "你是算力交付排期风险报告的解释层助手。"
                "你只能引用用户给出的 JSON 中的数字、日期、项目名、清单条目和责任方；"
                "禁止编造新的日期、数量、清单条目或排期结论。"
                "请生成整体结论 summary_text，以及 customer/purchase/supply/sla 四类清单的行动建议。"
                "只输出严格 JSON，格式为："
                '{"summary_text":"...","action_suggestions":[{"category_id":"customer","title":"客户配合","action_suggestion":"..."}]}'
            ),
        },
        {
            "role": "user",
            "content": f"风险报告确定性快照 JSON：{data}",
        },
    ]


def _parse_model_json(content: str) -> dict[str, object]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            text = match.group(0)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmCallError("模型响应不是合法 JSON。") from exc
    if not isinstance(parsed, dict):
        raise LlmCallError("模型响应 JSON 顶层不是对象。")
    return parsed


def _parse_sections(value: object) -> list[ReportSummarySection]:
    if value is None:
        return []
    if isinstance(value, dict):
        value = [
            {"category_id": category_id, "title": "", "action_suggestion": suggestion}
            for category_id, suggestion in value.items()
        ]
    if not isinstance(value, list):
        raise LlmCallError("模型响应 action_suggestions 不是数组。")
    sections: list[ReportSummarySection] = []
    for item in value:
        try:
            sections.append(ReportSummarySection.model_validate(item))
        except Exception as exc:
            raise LlmCallError("模型响应 action_suggestions 条目不符合契约。") from exc
    return sections
