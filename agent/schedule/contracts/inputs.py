"""输入侧契约：排期引擎吃什么（01§30 一、输入 1–11）。

每个字段的 description 标注来源：
  02/<目录>《列名》= 真实数据表头；01§x = 业务语义节；配置 = 源表没有、人工补充维护；前端 = 用户操作产生。
"""
from __future__ import annotations

from datetime import date

from pydantic import Field

from agent.schedule.contracts.common import (
    ActivityType,
    AnchorSource,
    ArrivalStatus,
    ConstraintSource,
    ContractModel,
    DateRange,
    DependencyType,
    DurationMode,
    Experience,
    IncidentType,
    Scope,
    TargetRef,
    TEAM_SIZE_MAX,
)


# ── 1. 项目（01§30 一.1）────────────────────────────────────────────

class Project(ContractModel):
    project_id: str = Field(description="项目唯一标识。来源：02/02《项目编号》(PROJECT_ID)")
    project_name: str = Field(description="项目名称。来源：配置")
    start_date: date | None = Field(default=None, description="项目开始日。来源：配置/合同")
    handover_date: date | None = Field(default=None, description="移交时间=合同交付目标（项目级硬锚点）。来源：合同")
    scene: str | None = Field(default=None, description="项目场景，如 集群集成。来源：02/02《项目场景》")
    product_form: str | None = Field(default=None, description="产品形态，如 A3。来源：02/02《产品形态》")
    cooling_method: str | None = Field(default=None, description="散热方式，如 liquid_cooling。来源：02/02《散热方式》")
    project_scale: str | None = Field(default=None, description="项目规模标签（如 标准项目）。仅作 total_card_count 缺失时的取档回退。来源：02/02《项目规模》")
    total_card_count: int | None = Field(default=None, ge=1, description="集群总卡数——规模分档的第一依据：<1000 千卡以下；1000~10000 千卡至万卡；>10000 万卡以上（2026-06-10 拍板：数字泛化取代标签判断）。来源：合同/前端录入（02 源表暂无此列）")
    note: str | None = Field(default=None, description="整体约束说明。来源：配置")


# ── 2. 站：机房（01§30 一.2）────────────────────────────────────────

class Room(ContractModel):
    room_id: str = Field(description="机房唯一标识（即机房名称，如 B2DH401）。来源：02/05《机房名称》")
    cabling_ready_date: date | None = Field(default=None, description="可布线日（机房 ready 三段之一）。来源：前端/客户")
    install_ready_date: date | None = Field(default=None, description="可装设备日（三段之二）。来源：前端/客户")
    liquid_ready_date: date | None = Field(default=None, description="可通液日（三段之三）。任一段非空=可进场，三段全空=待定（01§30）。来源：前端/客户")
    power_off_windows: list[DateRange] = Field(default_factory=list, description="断电窗口（上电类活动须落在窗口内）。来源：前端/客户")
    note: str | None = Field(default=None, description="其它现场条件（洁净度/供电/承重等，v1 不建模只记录）。来源：前端")


# ── 3. 货：PoD 与到货（01§30 一.3）──────────────────────────────────

class Pod(ContractModel):
    pod_id: str = Field(description="PoD 唯一标识=管理单元全称（如 B2DH401-POD01）。来源：02/05《PoD名称》=02/06《管理单元》")
    room_id: str = Field(description="所属机房。来源：02/05《机房名称》")
    compute_cabinet_count: int | None = Field(default=None, ge=0, description="计算柜数量（弹性活动工作量输入，如液冷计算柜安装）。来源：02/05《计算柜》按编号计数")
    other_cabinet_count: int | None = Field(default=None, ge=0, description="其它柜数量（总线/Leaf/管理面合计）。来源：02/05 各柜列计数")
    note: str | None = Field(default=None)


class ArrivalItem(ContractModel):
    """到货行（BOQ 与到货表都是「数量输入」，喂工作量换算，01§30 一.3）。"""

    arrival_id: str = Field(description="到货记录标识。来源：02/06《ID》")
    pod_id: str = Field(description="归属 PoD（管理单元）。来源：02/06《管理单元》")
    device_type: str = Field(description="设备/物料类型，如 灵衢线缆、计算柜。来源：02/06《设备类型》")
    device_model: str | None = Field(default=None, description="型号。来源：02/06《型号》")
    unit: str | None = Field(default=None, description="计量单位（根/柜/台）。来源：02/06《单位》")
    quantity: float = Field(ge=0, description="数量（弹性活动工作量来源）。来源：02/06《数量》")
    arrival_date: date | None = Field(default=None, description="实际或预计到货日（对依赖到货的活动是锚点）。来源：02/06《到货日期》")
    arrival_status: ArrivalStatus = Field(description="三态（导入按到货日期推导，规则见 common.ArrivalStatus）。来源：02/06《到货日期》推导")
    note: str | None = Field(default=None, description="来源：02/06《备注》")


# ── 4. 人：队伍（01§30 一.4、01§11 §3）──────────────────────────────

class Team(ContractModel):
    team_id: str = Field(description="队伍唯一标识。来源：02/08《队伍编号》")
    size: int = Field(default=12, ge=1, le=TEAM_SIZE_MAX, description="人数：默认 12、可调、上限 18（2026-06-10 拍板，与 02/08 一致）。来源：02/08《人数》")
    experience: Experience = Field(default="一般", description="经验档→常驻产能系数 1.0/0.8/0.7（同时作用于标准与极限 SLA）。来源：02/08《经验等级》")
    on_site: bool = Field(default=True, description="在场/待命。来源：02/08《在场状态》（在场/待分配）")
    available_from: date | None = Field(default=None, description="可用起始日。来源：前端/配置")


# ── 5. 活动模板（01§30 一.5、01§10 §2-3、01§11）─────────────────────

class WorkloadRule(ContractModel):
    """弹性活动的工作量换算（01§11 §2）。统一折算成「日速率」：
    工期 = 匹配到的数量 ÷ daily_rate；增员缩放以 assumed_crew 为基准（缩放律属引擎）。
    源文本四种格式与折算规则见 contracts/README「导入规则」。"""

    workload_source: str = Field(description="按 device_type 匹配 ArrivalItem.quantity 汇总，如 灵衢线缆、计算柜、盒式网络设备。来源：02/04《标准工时》单元格文本")
    unit: str | None = Field(default=None, description="根/柜/台。来源：同上")
    standard_daily_rate: float = Field(gt=0, description="标准日速率（数量/天）：'2688根/12天'→224、'48柜/天'→48。来源：02/04《标准工时》")
    limit_daily_rate: float | None = Field(default=None, description="极限日速率（压缩后的上限速率）：'2688根/7天'→384。来源：02/04《极限工时》")
    assumed_crew: int | None = Field(default=None, description="速率隐含的班组人数（备注'资源投入：硬件安装4人'），增员缩放基准。来源：02/04 备注")


class RiskRule(ContractModel):
    """活动风险表行（01§14 §2 第二来源；v1 先立形状，内容随基线表灌入）。"""

    trigger_logic: str | None = Field(default=None, description="风险判断逻辑。来源：02/04《风险判断逻辑》")
    risk_name: str | None = Field(default=None, description="来源：02/04《风险名称》")
    description: str | None = Field(default=None, description="来源：02/04《风险描述》")
    impact: str | None = Field(default=None, description="对排期/交付的影响。来源：02/04《风险影响》")
    mitigation: str | None = Field(default=None, description="应对预案=保障措施。来源：02/04《风险应对预案》")
    mitigation_owner: str | None = Field(default=None, description="预案责任人。来源：02/04《预案对应的责任人》")


class Activity(ContractModel):
    """活动模板项（每项目一套模板；按 scope 实例化到 项目/机房/批次/PoD，01§10 §3）。"""

    activity_id: str = Field(description="模板内唯一编号，如 3.1（实例化后 instance_id=<作用域id>/<activity_id>，根治撞号）。来源：02/01《活动ID》=02/04《序号》")
    activity_name: str = Field(description="活动名称。来源：02/01《活动名称》=02/04《二级活动》")
    phase: str | None = Field(default=None, description="所属阶段。来源：02/04《所属阶段》/《一级活动》")
    scope: Scope = Field(description="作用域：项目级/机房级/批次级/PoD级——决定复制几遍、在哪汇合（01§10 §3）。来源：02/04 J 列（表头行2）")
    activity_type: ActivityType = Field(default="普通", description="普通/里程碑/到货/机房准备/返工（01§10 §2）。来源：按名称判读（*到货*→到货、机房改造*→机房准备）+配置")
    constraint_source: ConstraintSource | None = Field(default=None, description="站/货/人（01§10）。可空：不参与日期计算（靠依赖网络传导），用于解释材料与方案C指向。来源：引擎按活动推断（机房改造*→站、*到货*→货、其余施工→人），后续要精确可在基线表加列")
    duration_mode: DurationMode = Field(default="固定", description="固定/规模分档/弹性（01§11 §2；'—'=机房准备/到货类，被外部日期锚定）。来源：02/04《SLA形态》（M列）")
    standard_sla_days: int | None = Field(default=None, ge=0, description="标准 SLA（天）。规模分档活动按 project_scale 取档后的值。来源：02/04《标准工时》或 02/01《SLA》（'3天'→3）")
    minimum_sla_days: int | None = Field(default=None, ge=0, description="极限 SLA（天）=压缩下限（01§11 §1）。来源：02/04《极限工时》")
    workload_rules: list[WorkloadRule] = Field(default_factory=list, description="弹性活动 ≥1 条（如 网络设备安装 拆 盒式/框式 两条）；固定/规模分档/锚定类为空。来源：02/04 工时单元格解析")
    is_default_milestone: bool = Field(default=False, description="是否四默认里程碑之一（机房就位/到货/上电/上线，01§10 §5）。来源：配置")
    responsibility: str | None = Field(default=None, description="分工/责任角色。来源：02/04《分工》")
    note: str | None = Field(default=None, description="备注（风险识别/保障措施/解释素材，01§30 一.5）。来源：02/04《备注》")
    risk_rule: RiskRule | None = Field(default=None, description="活动自带风险规则（命中即报，01§14 §2）。来源：02/04 风险五列")


# ── 6. 依赖（01§30 一.5；按 id 引用）────────────────────────────────

class Dependency(ContractModel):
    from_activity_id: str = Field(description="前置活动（模板 id）。来源：02/02《前置活动ID》；02/04 SS/SF/FS/FF 列按《序号》解析")
    to_activity_id: str = Field(description="后继活动（模板 id）。来源：02/02《后继活动ID》")
    dep_type: DependencyType = Field(default="FS", description="v1 引擎只解析 FS；SS/FF/SF 收录但报暂不支持（01§00 §6.3）。来源：02/04 四列/02/02")


# ── 7. 批次（01§10 §4、02/09）───────────────────────────────────────

class Batch(ContractModel):
    batch_id: str = Field(description="批次唯一标识。来源：前端生成")
    batch_name: str = Field(description="展示名，如 批次1。来源：02/09《批次名》")
    pod_ids: list[str] = Field(description="该批包含的 PoD（拖 PoD 入批，批=一组一起上电/上线的 PoD）。来源：02/09《该批包含的PoD》")
    power_on_target_date: date | None = Field(default=None, description="上电目标（批次级、同批统一；硬目标锚点）。来源：02/09《上电目标日期》")
    online_target_date: date | None = Field(default=None, description="上线目标（=该批排期终点）。来源：02/09《上线目标日期》/合同")


# ── 8. 锚点（01§30 一.6、01§12 §3）──────────────────────────────────

class Anchor(ContractModel):
    anchor_id: str = Field(description="锚点标识。来源：前端生成")
    target: TargetRef = Field(description="作用对象（活动实例/批次上电/批次上线/项目移交/到货/机房就位）")
    anchor_date: date = Field(description="时间值")
    anchor_source: AnchorSource = Field(description="来源类型（决定默认优先级，见 common.ANCHOR_PRIORITY_DEFAULT）")
    priority: int | None = Field(default=None, ge=1, description="不填则按 anchor_source 取默认（01§12 §3，数字小者优先）")
    is_hard: bool = Field(default=True, description="硬/软（客户偏好类默认软，'必须某日前'可转硬）")


# ── 9-11. 诉求 / 返工 / 意外事件（01§30 一.8-10、01§13）─────────────

class DemandRequest(ContractModel):
    """用户调整诉求（可多条并存）。"""

    demand_id: str = Field(description="来源：前端生成")
    target: TargetRef
    direction: str = Field(description="提前 | 延后 | 某日期前完成。来源：前端", pattern="^(提前|延后|某日期前完成)$")
    amount_days: int | None = Field(default=None, ge=1, description="调整量（天）；direction=某日期前完成 时不填")
    deadline: date | None = Field(default=None, description="direction=某日期前完成 时必填")
    reason: str | None = Field(default=None, description="触发原因（解释材料素材）")


class ReworkEvent(ContractModel):
    """返工：插入独立返工活动，不改原活动（01§13 §5）。"""

    rework_id: str = Field(description="来源：前端生成")
    rework_name: str = Field(description="返工活动名称")
    insert_after_instance_id: str = Field(description="插入位置：哪个活动实例之后")
    duration_days: int = Field(ge=1, description="持续时间（天）")
    reason: str | None = Field(default=None, description="触发原因")
    blocks_downstream: bool = Field(default=True, description="是否阻断后续")


class IncidentEvent(ContractModel):
    """意外事件=时间窗口产能系数（01§11 §4、01§13 §6）。"""

    incident_id: str = Field(description="来源：前端生成")
    incident_type: IncidentType
    window: DateRange = Field(description="影响时间窗口；作用于窗口内当天在施工的活动（动态判定）")
    efficiency: float = Field(ge=0, le=1, description="效率打折=档位或自定义(0,1)；假期停工=0。同日多事件取最小，再乘队伍常驻系数")
    reason: str | None = Field(default=None)


# ── 规则配置（01§30 一.11；不写死在代码里）─────────────────────────

class RuleConfig(ContractModel):
    concentrate_top_k: int = Field(default=5, ge=1, description="集中压缩压前 K 个可压活动（01§13 §3）")
    skip_weekends: bool = Field(default=False, description="跳周末开关（01§11 §5）")
    anchor_priority_override: dict[str, int] | None = Field(default=None, description="锚点优先级覆盖（默认见 common.ANCHOR_PRIORITY_DEFAULT）")


# ── 输入总包（generate 全量；adjust 以实体覆盖增量给）───────────────

class InputBundle(ContractModel):
    project: Project
    rooms: list[Room]
    pods: list[Pod]
    arrivals: list[ArrivalItem] = Field(default_factory=list)
    teams: list[Team] = Field(default_factory=list, description="不给则默认 机房数=队伍数、每队12人、经验一般（01§11 §3）")
    activities: list[Activity] = Field(description="活动模板（每项目一套）")
    dependencies: list[Dependency]
    batches: list[Batch]
    anchors: list[Anchor] = Field(default_factory=list)
    rule_config: RuleConfig = Field(default_factory=RuleConfig)
