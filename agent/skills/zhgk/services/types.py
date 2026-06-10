"""
智慧工勘 v4 — 公共数据类型定义

所有模块共享的枚举、TypedDict、dataclass。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypedDict


# ──────────────────────────────────────────────
# 枚举类型
# ──────────────────────────────────────────────

class Intent(Enum):
    """用户意图"""
    SCENE_SUGGEST = "scene_suggest"
    SURVEY_WORK = "survey_work"
    SUPPLEMENT = "supplement"
    REPORT_GEN = "report_gen"


class AssessmentValue(Enum):
    """五值评估结果"""
    SATISFIED = "满足"
    UNSATISFIED = "不满足"
    NOT_APPLICABLE = "不涉及"
    NOT_SURVEYED = "未勘测"
    UNRECOGNIZABLE = "无法识别"

    @classmethod
    def from_str(cls, s: str) -> "AssessmentValue":
        for member in cls:
            if member.value == s:
                return member
        raise ValueError(f"无效的评估值: {s}")


class IssueStatus(Enum):
    """问题状态"""
    OPEN = "open"
    CLOSED = "closed"


class SurveyMethod(Enum):
    """勘测方法"""
    ON_SITE = "现场勘测"
    CUSTOMER_FEEDBACK = "客户反馈"


class Category(Enum):
    """分类"""
    STANDARD = "标准"
    DATA = "数据"


class LogLevel(Enum):
    """日志级别"""
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


# ──────────────────────────────────────────────
# LLM 调用类型
# ──────────────────────────────────────────────

# llm_call(system_prompt, user_prompt) -> str
LLMCallable = Callable[[str, str], str]


# ──────────────────────────────────────────────
# 底表数据结构（入场评估标准表）
# ──────────────────────────────────────────────

class SurveyItem(TypedDict):
    """入场评估标准表单行数据"""
    序号: int
    代际_制冷: str
    分类: str
    细分场景: str
    勘测要素: str
    项目: str
    检查内容: str
    是否支持视频勘测: str
    勘测方法: str
    检查结果: str
    备注: str
    语音助手背景知识: str
    视频勘测背景知识: str


# ──────────────────────────────────────────────
# 全量勘测结果表行结构
# ──────────────────────────────────────────────

class SurveyResultRow(TypedDict):
    """全量勘测结果表单行"""
    序号: int
    细分场景: str
    勘测要素: str
    项目: str
    检查内容: str
    勘测方法: str
    最新检查结果: str
    AI评估结果: str
    图片1: Optional[Any]
    图片2: Optional[Any]
    备注: str


# ──────────────────────────────────────────────
# 问题清单行结构
# ──────────────────────────────────────────────

class IssueItem(TypedDict):
    """问题清单表单行"""
    序号: int
    问题描述: str
    状态: str
    整改建议: str
    责任人: str
    计划关闭时间: str
    备注: str


# ──────────────────────────────────────────────
# 风险结果行结构
# ──────────────────────────────────────────────

class RiskItem(TypedDict):
    """风险识别结果表单行"""
    序号: int
    风险类型描述: str
    风险细项描述: str
    风险影响: str
    建议措施: str
    备注: str


# ──────────────────────────────────────────────
# LLM 评估返回结构
# ──────────────────────────────────────────────

@dataclass
class AssessmentResult:
    """LLM 评估引擎单条返回"""
    conclusion: AssessmentValue
    defect_description: str = ""
    confidence: float = 0.0


@dataclass
class IssueGenResult:
    """LLM 问题清单生成单条返回"""
    problem_description: str
    remediation_suggestion: str


@dataclass
class RiskJudgment:
    """LLM 风险判断单条返回"""
    triggered: bool
    risk_impact: str = ""
    suggestion: str = ""


# ──────────────────────────────────────────────
# 项目元数据
# ──────────────────────────────────────────────

@dataclass
class ProjectMeta:
    """项目元数据"""
    project_name: str = ""
    activity_id: str = ""
    room_name: str = ""
    survey_date: str = ""
    surveyor: str = ""
    generation_cooling: str = ""
    delivery_tags: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# 日志记录结构
# ──────────────────────────────────────────────

@dataclass
class LogEntry:
    """日志记录"""
    timestamp: str
    level: LogLevel
    module: str
    step: str
    message: str
    activity_id: str = ""
    project_name: str = ""
    error_code: Optional[str] = None
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: Optional[int] = None
    stack_trace: Optional[str] = None
