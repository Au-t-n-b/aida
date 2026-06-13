"""API 契约：前后端怎么对话（v1 三个端点 + 错误格式）。

模式（正排/倒排/混合）由引擎按批次完备度自动识别（01§12 §1、01§20 §1），
请求里不传模式、响应里不出黑话——倒排批给 readiness_suggestions、
信息全的批给可执行计划/方案。
"""
from __future__ import annotations

from pydantic import Field

from agent.schedule.contracts.common import ContractModel
from agent.schedule.contracts.inputs import (
    Anchor,
    ArrivalItem,
    Batch,
    DemandRequest,
    IncidentEvent,
    InputBundle,
    ReworkEvent,
    Room,
    RuleConfig,
    Team,
)
from agent.schedule.contracts.outputs import (
    Explanation,
    PlanResult,
    ReadinessSuggestion,
    RiskItem,
    StrategyPlan,
    UnmetItem,
)

API_PREFIX = "/api/v1/schedule"

GENERATE_PATH = f"{API_PREFIX}/generate"   # POST 初排（无基线）
ADJUST_PATH = f"{API_PREFIX}/adjust"       # POST 沙箱推演（有基线，不写回）
COMMIT_PATH = f"{API_PREFIX}/commit"       # POST 确认下发（写回出新版本）
PARSE_CHANGES_PATH = f"{API_PREFIX}/parse-changes"  # POST 固定模板变更表（multipart 上传）
PROJECT_DATA_PATH = f"{API_PREFIX}/project-data"    # GET 真实项目盘子（02_项目数据 → InputBundle）
EXPORT_PLAN_PATH = f"{API_PREFIX}/export-plan"      # GET 正式计划版本导出为交付计划表 xlsx


# ── POST /api/v1/schedule/generate ──────────────────────────────────

class GenerateRequest(ContractModel):
    """初排：给全量输入，引擎按批次完备度自动分流（01§20 §1 两轴）。"""

    inputs: InputBundle


class GenerateResponse(ContractModel):
    plan: PlanResult = Field(description="可执行部分的计划（信息不足批的活动日期标 is_ai_generated）")
    readiness_suggestions: list[ReadinessSuggestion] = Field(default_factory=list, description="到货/机房未定的批 → 倒排建议（01§20 §2）")
    risks: list[RiskItem] = Field(default_factory=list)
    unmet: list[UnmetItem] = Field(default_factory=list)
    explanation: Explanation


# ── POST /api/v1/schedule/adjust ────────────────────────────────────

class ChangeSet(ContractModel):
    """攒好的变更（按实体去重，殊途同归的四个入口都落到这，01§20 §3.1）。
    给到的实体按 id 整体覆盖基线里的同 id 对象；没给的不动。"""

    rooms: list[Room] = Field(default_factory=list, description="机房 ready/窗口变更")
    arrivals: list[ArrivalItem] = Field(default_factory=list, description="到货回填/变更")
    teams: list[Team] = Field(default_factory=list, description="队伍增减/经验调整")
    batches: list[Batch] = Field(default_factory=list, description="拖上电/上线目标旗、改分批（只动旗，冻结其它，01§20 §3.2）")
    anchors: list[Anchor] = Field(default_factory=list)
    demands: list[DemandRequest] = Field(default_factory=list, description="提前/延后/某日期前完成 诉求")
    reworks: list[ReworkEvent] = Field(default_factory=list)
    incidents: list[IncidentEvent] = Field(default_factory=list)
    rule_config: RuleConfig | None = Field(default=None)


class ParseChangesResponse(ContractModel):
    """固定模板变更表解析结果：确定性转为 ChangeSet，非致命问题放 warnings。"""

    changes: ChangeSet
    warnings: list[str] = Field(default_factory=list)


class AdjustRequest(ContractModel):
    """沙箱推演：在基线版本上应用变更，出多方案比选；不写回（01§13 §1）。"""

    plan_id: str
    base_version: int = Field(ge=1, description="基于哪版计划推演")
    changes: ChangeSet


class AdjustResponse(ContractModel):
    options: list[StrategyPlan] = Field(description="A 均匀 / B 集中 / C 站货提拉（时间富余时含 buffer延长）；每卡含 KPI+完整排期+风险+一句建议")
    unmet: list[UnmetItem] = Field(default_factory=list, description="所有策略都到顶仍做不到的诉求")
    explanation: Explanation


# ── POST /api/v1/schedule/commit ────────────────────────────────────

class CommitRequest(ContractModel):
    """人选中某方案「确认 & 下发」→ 写回正式计划，产生新版本（可回滚，01§13 §1）。"""

    plan_id: str
    base_version: int = Field(ge=1)
    option_id: str = Field(description="AdjustResponse.options 里被选中的方案")
    duration_overrides: dict[str, int] | None = Field(
        default=None,
        description="选后微调：活动实例 id → 微调后工期天数；后端只采信工期，日期由引擎重算",
    )


class CommitResponse(ContractModel):
    plan_id: str
    new_version: int = Field(ge=1)
    plan: PlanResult


# ── 错误契约 ─────────────────────────────────────────────────────────

class ConflictDetail(ContractModel):
    constraint: str = Field(description="冲突的约束（业务语言）")
    detail: str | None = None


class ErrorResponse(ContractModel):
    """422 业务不可行；400 字段校验错（FastAPI/Pydantic 默认格式）；500 内部错误。"""

    code: str = Field(description="如 INFEASIBLE（窗口交集为空/压到极限仍差，01§12 §1 步骤④）、IMPORT_ERROR（名字→id 解析失败）。注：非 FS 依赖自 T-008 起不再整体报错，降级为逐条「依赖未纳入」风险")
    message: str = Field(description="业务语言的原因")
    conflicts: list[ConflictDetail] = Field(default_factory=list)
