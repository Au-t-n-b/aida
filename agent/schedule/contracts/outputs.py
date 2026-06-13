"""输出侧契约：排期引擎吐什么（01§30 二、输出 1–7）。

区间交付看板（输出6）是派生视图：前端可从 PlanResult 的里程碑实例直接算，
v1 不单设接口；关键路径影响分析（输出7）并入 Explanation 与方案卡。
"""
from __future__ import annotations

from datetime import date

from pydantic import Field

from agent.schedule.contracts.common import (
    ContractModel,
    MilestoneKind,
    RiskLevel,
    RiskType,
    ScopeRef,
    Strategy,
)


# ── 1. 排期后的活动实例与计划（01§30 二.1）─────────────────────────

class ScheduledActivity(ContractModel):
    instance_id: str = Field(description="实例唯一 id = <作用域对象id>/<activity_id>（如 B2DH401-POD01/3.1；项目级 project/<id>）。来源：引擎")
    activity_id: str = Field(description="模板活动 id。来源：模板")
    activity_name: str
    scope_ref: ScopeRef = Field(description="挂在谁身上（项目/机房/批次/PoD）")
    start_date: date
    end_date: date = Field(description="闭区间：工期 = end − start + 1")
    actual_sla_days: int = Field(ge=0, description="本次采用工期：=标准 | 压缩到[极限,标准) | >标准(buffer)（01§11 §1）。来源：引擎")
    standard_sla_days: int | None = Field(default=None, description="冗余带出便于前端标风险（实际<标准 即压缩）")
    is_critical: bool = Field(default=False, description="是否在关键路径上（每次调整后重算，01§12 §4）")
    is_milestone: bool = Field(default=False)
    milestone_kind: MilestoneKind | None = Field(default=None, description="四默认里程碑之一或移交；非里程碑为 None")
    predecessor_instance_ids: list[str] = Field(default_factory=list, description="前置实例（按 id，01§30 二.1）")
    team_id: str | None = Field(default=None, description="分派队伍（弹性活动）。来源：引擎")
    is_ai_generated: bool = Field(default=False, description="日期是否 AI 建议（倒排建议标 AI 产出，01§20 §2）")


class PlanResult(ContractModel):
    """一版完整计划（含版本，可回滚/对照，01§13 §1）。"""

    plan_id: str = Field(description="计划标识。来源：引擎")
    version: int = Field(ge=1, description="计划版本号（写回时递增）")
    base_version: int | None = Field(default=None, description="基于哪版调整而来；初排为 None")
    activities: list[ScheduledActivity]
    critical_path: list[str] = Field(default_factory=list, description="关键路径上的 instance_id 链")
    project_finish_date: date | None = Field(default=None, description="整体交付日（末批上线/移交）")


# ── 2. 就位建议（倒排产出，01§30 二.2）─────────────────────────────

class ReadinessSuggestion(ContractModel):
    """信息不足批次的倒排建议（不含 A/B/C，用标准 SLA，01§20 §2）。"""

    batch_id: str
    suggested_room_ready: dict[str, date] = Field(default_factory=dict, description="room_id → 建议机房就位日。来源：引擎沿网络倒推（01§12 §1.1）")
    suggested_arrival: dict[str, date] = Field(default_factory=dict, description="pod_id → 建议到货日")


# ── 3. 风险与不可满足（01§14）───────────────────────────────────────

class RiskItem(ContractModel):
    risk_type: RiskType = Field(description="压缩强度 / 活动风险 / 链路聚合（01§14 §2）")
    severity: RiskLevel
    instance_id: str | None = Field(default=None, description="关联活动实例；链路聚合风险可为 None")
    message: str = Field(description="业务语言描述（给交付负责人看，不出算法黑话）")
    mitigation: str | None = Field(default=None, description="保障措施（活动风险来自 02/04《风险应对预案》）")


class UnmetItem(ContractModel):
    """不可满足=硬结论：当前规则下做不到（01§14 §1）。"""

    target_desc: str = Field(description="哪个诉求/锚点做不到")
    reason: str = Field(description="卡在哪个约束（压到极限仍差/前置锁死提不动/资源到顶……）")
    gap_days: int | None = Field(default=None, ge=0, description="差多少天")


# ── 4. 调整说明（可解释，01§14 §4 / 01§30 二.4）─────────────────────

class MovedActivity(ContractModel):
    instance_id: str
    old_start: date | None = None
    old_end: date | None = None
    new_start: date
    new_end: date
    direction: str = Field(description="顺延 | 提前", pattern="^(顺延|提前)$")


class Explanation(ContractModel):
    is_initial: bool = Field(description="初排还是调整")
    anchors_used: list[str] = Field(default_factory=list, description="用了哪些锚点（anchor_id 或业务描述）")
    strategy_used: Strategy | None = Field(default=None, description="用的策略；倒排建议/常规初排为 None")
    critical_path_change: str | None = Field(default=None, description="关键路径如何变化（业务语言）")
    moved_activities: list[MovedActivity] = Field(default_factory=list, description="被顺延/提前的活动（关键路径上需变化的单独展示，01§13 §1）")
    notes: list[str] = Field(default_factory=list, description="可直接拿去与客户沟通的解释要点")


# ── 5. 多策略方案卡（01§13 §3、01§30 二.3、01§20 §3.3）──────────────

class PlanKpis(ContractModel):
    pod_count: int = Field(ge=0)
    total_duration_days: int = Field(ge=0, description="总工期")
    compressed_days: int = Field(default=0, ge=0, description="压缩天数")
    added_crew: int = Field(default=0, ge=0, description="增员人数（A/B 对弹性活动生效，有 18人/队、一PoD一队 天花板，01§11 §3）")


class PulledInput(ContractModel):
    """方案 C 的产出：倒推的理想前置输入时间，交业务跟上游谈（01§13 §3.1）。"""

    target_desc: str = Field(description="到货(pod_id) 或 机房就位(room_id)")
    current_date: date | None
    suggested_date: date


class StrategyPlan(ContractModel):
    option_id: str = Field(description="方案标识（用于 commit 选定）")
    strategy: Strategy
    kpis: PlanKpis
    plan: PlanResult = Field(description="该方案下的完整排期（含关键路径）")
    risk_level: RiskLevel = Field(description="引入风险 高/中/低（01§14 §3）")
    advice: str = Field(description="一句建议（比选依据）")
    risks: list[RiskItem] = Field(default_factory=list)
    pulled_inputs: list[PulledInput] = Field(default_factory=list, description="仅方案 C 非空")
