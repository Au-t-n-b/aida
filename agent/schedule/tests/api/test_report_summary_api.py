from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

SCHEDULE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SCHEDULE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from agent.schedule.llm import LlmConfigurationError, LlmTimeoutError  # noqa: E402
from agent.schedule.app_main import create_app  # noqa: E402
from agent.schedule.contracts.api import REPORT_SUMMARY_PATH, ErrorResponse  # noqa: E402
from agent.schedule.contracts.report_summary import ReportSummaryRequest, ReportSummaryResponse  # noqa: E402


def test_report_summary_returns_ai_text_and_uses_guarded_prompt():
    fake_client = FakeReportSummaryClient(_success_payload())
    client = TestClient(create_app(report_summary_client=fake_client))

    response = client.post(REPORT_SUMMARY_PATH, json=_summary_request().model_dump(mode="json"))

    assert response.status_code == 200
    parsed = ReportSummaryResponse.model_validate(response.json())
    assert parsed.summary_text == "当前版本有 2 项待办，其中 1 项为高优先级，应先锁定客户 ready 与供应 ETA。"
    assert parsed.is_ai_generated is True
    assert parsed.model == "qwen3.7-max"
    assert [item.category_id for item in parsed.action_suggestions] == ["customer", "purchase", "supply", "sla"]
    assert fake_client.model == "qwen3.7-max"
    assert "禁止编造新的日期、数量、清单条目" in fake_client.messages[0]["content"]
    assert '"todo_count":2' in fake_client.messages[1]["content"]


def test_report_summary_missing_key_returns_explicit_error():
    fake_client = FakeReportSummaryClient(exc=LlmConfigurationError("BAILIAN_API_KEY 未配置。"))
    client = TestClient(create_app(report_summary_client=fake_client))

    response = client.post(REPORT_SUMMARY_PATH, json=_summary_request().model_dump(mode="json"))

    assert response.status_code == 503
    error = ErrorResponse.model_validate(response.json())
    assert error.code == "LLM_CONFIG_MISSING"
    assert "BAILIAN_API_KEY" in error.message


def test_report_summary_timeout_returns_explicit_error():
    fake_client = FakeReportSummaryClient(exc=LlmTimeoutError("模型调用超时。"))
    client = TestClient(create_app(report_summary_client=fake_client))

    response = client.post(REPORT_SUMMARY_PATH, json=_summary_request().model_dump(mode="json"))

    assert response.status_code == 504
    error = ErrorResponse.model_validate(response.json())
    assert error.code == "LLM_TIMEOUT"
    assert "超时" in error.message


class FakeReportSummaryClient:
    def __init__(self, content: str = "", exc: Exception | None = None):
        self.content = content
        self.exc = exc
        self.messages = []
        self.model = ""

    def complete(self, messages, *, model: str = "qwen3.7-max") -> str:
        self.messages = messages
        self.model = model
        if self.exc:
            raise self.exc
        return self.content


def _success_payload() -> str:
    return json.dumps(
        {
            "summary_text": "当前版本有 2 项待办，其中 1 项为高优先级，应先锁定客户 ready 与供应 ETA。",
            "action_suggestions": [
                {"category_id": "customer", "title": "客户配合", "action_suggestion": "先确认 B1 机房 ready 日期。"},
                {"category_id": "purchase", "title": "采购配合", "action_suggestion": "当前无采购待办，保持模板巡检。"},
                {"category_id": "supply", "title": "供应配合", "action_suggestion": "补齐 P1 ETA 并跟踪在途状态。"},
                {"category_id": "sla", "title": "超 SLA 基线", "action_suggestion": "优先盯防关键路径上的超 SLA 活动。"},
            ],
        },
        ensure_ascii=False,
    )


def _summary_request() -> ReportSummaryRequest:
    return ReportSummaryRequest(
        project_name="API demo",
        project_id="api-demo",
        project_scale="标准项目",
        total_card_count=3456,
        scene="集群集成",
        product_form="A3 / liquid_cooling",
        baseline_version="v2",
        report_generated_at=date(2026, 6, 13),
        committed_at=datetime(2026, 6, 13, 10, 30, tzinfo=timezone.utc),
        project_finish_date=date(2026, 7, 1),
        activity_count=12,
        critical_activity_count=4,
        todo_count=2,
        high_count=1,
        categories=[
            {
                "category_id": "customer",
                "title": "客户配合",
                "recognition": "milestone_kind / 机房 ready 状态",
                "description": "机房 ready 未确认、上线目标待确认的批次。",
                "item_count": 1,
                "items": [
                    {
                        "id": "customer-ready-B1",
                        "matter": "批次1 机房 ready 待确认",
                        "owner": "客户配合",
                        "suggested_date": date(2026, 6, 20),
                        "related_activity": "R1",
                        "status": "待确认",
                        "severity": "高",
                        "reason": "批次内机房缺少 ready 日期。",
                    }
                ],
            },
            {
                "category_id": "purchase",
                "title": "采购配合",
                "recognition": "活动类别 / 活动名称通用规则",
                "description": "采购、下单、订货、备货类活动的基线时间要求。",
                "item_count": 0,
                "items": [],
            },
            {
                "category_id": "supply",
                "title": "供应配合",
                "recognition": "ArrivalItem.arrival_status / ETA",
                "description": "到货 ETA 待补、在途未到的 PoD 与建议到货日。",
                "item_count": 1,
                "items": [
                    {
                        "id": "supply-P1",
                        "matter": "P1 ETA 待补",
                        "owner": "供应配合",
                        "suggested_date": None,
                        "related_activity": "批次1 / 到货里程碑",
                        "status": "ETA 待补",
                        "severity": "中",
                        "reason": "PoD 缺少可执行 ETA。",
                    }
                ],
            },
            {
                "category_id": "sla",
                "title": "超 SLA 基线",
                "recognition": "actual_sla_days > standard_sla_days",
                "description": "排期实际工期超过标准 SLA 的活动清单。",
                "item_count": 0,
                "items": [],
            },
        ],
    )
