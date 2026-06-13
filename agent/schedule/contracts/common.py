"""契约基础类型：枚举、常量、公共小模型。

唯一权威（宪法 §1/§3）。枚举值用业务中文——与 01 业务语义、前端展示一致，
不再做一层"英文枚举 ↔ 中文展示"的翻译映射（少一处漂移源）。
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    """所有契约模型的基类：禁止未声明字段（打字错误当场报错）。"""

    model_config = ConfigDict(extra="forbid")


# ── 作用域与约束（01§10）─────────────────────────────────────────────

Scope = Literal["项目级", "机房级", "批次级", "PoD级"]
"""活动作用域：决定实例化几次、被谁共享（01§10 §3）。
来源：02/04 J 列（表头行 2；该表头单元格文本即取值清单"机房级\\项目级\\PoD级\\批次级"，导入按列位识别）。"""

ConstraintSource = Literal["站", "货", "人"]
"""约束来源：机房就位 / 设备到货 / 施工队伍（01§10；来源：配置 + 前端沉淀）。"""

ActivityType = Literal["普通", "里程碑", "到货", "机房准备", "返工"]
"""活动类型（01§10 §2）。"""

DurationMode = Literal["固定", "规模分档", "弹性"]
"""工期模式（01§11 §2；来源：02/04《SLA形态》M 列）：
固定 / 规模分档 都是刚性（加人无用），规模分档按 project_scale 跳档取 SLA；
弹性 = 工作量 ÷（人数 × 人均日产能），增员可压缩。
源表中 "—" = 机房准备/到货类活动（工期不由 SLA 决定，被机房就位/到货日锚定），见 contracts/README 导入规则。"""

DependencyType = Literal["FS", "SS", "FF", "SF"]
"""依赖类型（来源：02/04《SS/SF/FS/FF》四列）。v1 引擎只解析 FS，其余先收录、引擎报"暂不支持"。"""

MilestoneKind = Literal["机房就位", "到货", "上电", "上线", "移交"]
"""默认里程碑四类 + 项目移交（01§10 §5）。"""

ArrivalStatus = Literal["已到货", "在途", "未明"]
"""到货三态（01§30）。导入推导规则：到货日期≤今天→已到货；>今天→在途；空→未明。"""

Experience = Literal["丰富", "一般", "缺乏"]
"""队伍经验三档（01§11 §3）。"""

EXPERIENCE_EFFICIENCY: dict[str, float] = {"丰富": 1.0, "一般": 0.8, "缺乏": 0.7}
"""经验档 → 常驻产能系数（同时作用于标准与极限 SLA：工期 = SLA ÷ efficiency）。"""

TEAM_SIZE_DEFAULT = 12
TEAM_SIZE_MAX = 18
"""每队默认 12 人、上限 18（2026-06-10 拍板，与 02/08《人数》一致；语义层已同步）。"""

Strategy = Literal["均匀压缩", "集中压缩", "站货提拉", "buffer延长"]
"""调整策略（01§13 §3/§4）：A 均匀 / B 集中 / C 站货提拉 / 反向 buffer。"""

CONCENTRATE_TOP_K_DEFAULT = 5
"""集中压缩默认压可压空间最大的前 K 个活动（01§13 §3，可配）。"""

RiskLevel = Literal["高", "中", "低"]

RiskType = Literal["压缩强度", "活动风险", "链路聚合", "依赖未纳入"]
"""风险来源（01§14 §2 三类 + 「依赖未纳入」：v1 引擎对非 FS 依赖降级跳过时逐条报此类风险，2026-06-10 拍板）。"""

IncidentType = Literal["效率打折", "假期停工"]
"""意外事件两类（01§13 §6）：统一为"时间窗口产能系数"。"""

AnchorSource = Literal["移交里程碑", "上线", "上电", "到货", "机房就位", "指定活动", "客户诉求"]
"""锚点来源（01§30 §6）。"""

ANCHOR_PRIORITY_DEFAULT: dict[str, int] = {
    "上线": 1, "上电": 1, "移交里程碑": 1,  # 交付里程碑 = 硬目标，最高优先
    "到货": 2,                                # 硬输入，未锁定前可提拉（方案C）
    "机房就位": 3,                            # 同上
    "指定活动": 4,
    "客户诉求": 5,                            # 软（明确"必须某日前"可转硬）
}
"""多锚点冲突时的默认优先级（01§12 §3；数字小者优先）。"""


# ── 公共小模型 ───────────────────────────────────────────────────────

class DateRange(ContractModel):
    """闭区间日期段（工期 = end − start + 1，01§00 §6.4）。"""

    start: date
    end: date


class ScopeRef(ContractModel):
    """作用域定位：这个活动实例/对象挂在谁身上。"""

    scope: Scope
    ref_id: str | None = Field(
        default=None,
        description="机房→room_id；批次→batch_id；PoD→pod_id；项目级→None",
    )


class TargetRef(ContractModel):
    """锚点 / 诉求的作用对象。"""

    kind: Literal["活动实例", "批次上电", "批次上线", "项目移交", "到货", "机房就位"]
    ref_id: str | None = Field(
        default=None,
        description="活动实例→instance_id；批次→batch_id；到货→pod_id；机房→room_id；项目移交→None",
    )
