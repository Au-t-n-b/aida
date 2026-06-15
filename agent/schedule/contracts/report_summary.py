"""风险报告 AI 总结契约。

模型只消费本请求体里的确定性报告快照，返回解释层文本；不得参与排期计算。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from agent.schedule.contracts.common import ContractModel, RiskLevel

ReportSummaryCategoryId = Literal["customer", "purchase", "supply", "sla"]


class ReportSummaryTodoItem(ContractModel):
    """四清单条目快照；数字、日期、责任方均由前端确定性派生。"""

    id: str
    matter: str
    owner: str
    suggested_date: date | None = None
    related_activity: str
    status: str
    severity: RiskLevel
    reason: str


class ReportSummaryCategory(ContractModel):
    """一类业务待办清单，供模型生成行动建议。"""

    category_id: ReportSummaryCategoryId
    title: str
    recognition: str
    description: str
    item_count: int = Field(ge=0)
    items: list[ReportSummaryTodoItem] = Field(default_factory=list)


class ReportSummaryRequest(ContractModel):
    """风险报告 AI 总结输入：报告抬头、统计与四清单条目纯数据快照。"""

    project_name: str
    project_id: str
    project_scale: str
    total_card_count: int | None = Field(default=None, ge=1)
    scene: str
    product_form: str
    baseline_version: str
    report_generated_at: date
    committed_at: datetime
    project_finish_date: date | None = None
    activity_count: int = Field(ge=0)
    critical_activity_count: int = Field(ge=0)
    todo_count: int = Field(ge=0)
    high_count: int = Field(ge=0)
    categories: list[ReportSummaryCategory] = Field(default_factory=list)


class ReportSummarySection(ContractModel):
    """某一清单的 AI 行动建议文本。"""

    category_id: ReportSummaryCategoryId
    title: str
    action_suggestion: str


class ReportSummaryResponse(ContractModel):
    """风险报告 AI 总结输出；解释层文本，不写回任何排期数字。"""

    summary_text: str
    action_suggestions: list[ReportSummarySection] = Field(default_factory=list)
    is_ai_generated: Literal[True] = True
    model: str
    generated_at: datetime
