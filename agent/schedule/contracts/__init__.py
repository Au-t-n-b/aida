"""契约包：全仓数据形状与接口的唯一权威（宪法 §1/§3）。

用法（后端，仓根加入 PYTHONPATH）：
    from agent.schedule.contracts.inputs import Activity, InputBundle
    from agent.schedule.contracts.api import GenerateRequest, GENERATE_PATH

前端不直接读本包——用生成的 TS 类型（见 README"待办"）。
"""
from agent.schedule.contracts.common import (  # noqa: F401
    ANCHOR_PRIORITY_DEFAULT,
    CONCENTRATE_TOP_K_DEFAULT,
    EXPERIENCE_EFFICIENCY,
    TEAM_SIZE_DEFAULT,
    TEAM_SIZE_MAX,
    ContractModel,
    DateRange,
    ScopeRef,
    TargetRef,
)
from agent.schedule.contracts.inputs import (  # noqa: F401
    Activity,
    Anchor,
    ArrivalItem,
    Batch,
    DemandRequest,
    Dependency,
    IncidentEvent,
    InputBundle,
    Pod,
    Project,
    ReworkEvent,
    RiskRule,
    Room,
    RuleConfig,
    Team,
    WorkloadRule,
)
from agent.schedule.contracts.outputs import (  # noqa: F401
    Explanation,
    GapSummary,
    MovedActivity,
    PlanKpis,
    PlanResult,
    PulledInput,
    ReadinessSuggestion,
    RiskItem,
    ScheduledActivity,
    StrategyPlan,
    UnmetItem,
)
from agent.schedule.contracts.api import (  # noqa: F401
    ADJUST_PATH,
    API_PREFIX,
    COMMIT_PATH,
    GENERATE_PATH,
    PARSE_CHANGES_PATH,
    REPORT_SUMMARY_PATH,
    AdjustRequest,
    AdjustResponse,
    ChangeSet,
    CommitRequest,
    CommitResponse,
    ConflictDetail,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    ParseChangesResponse,
)
from agent.schedule.contracts.report_summary import (  # noqa: F401
    ReportSummaryCategory,
    ReportSummaryRequest,
    ReportSummaryResponse,
    ReportSummarySection,
    ReportSummaryTodoItem,
)
