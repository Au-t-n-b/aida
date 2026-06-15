/* AUTO-GENERATED from /contracts (Pydantic, 唯一权威) — DO NOT EDIT.
 * 重新生成：仓根执行 `python contracts/generate_ts.py`；校验：`--check`。
 * 字段为 snake_case（线上格式）；前端如需 camelCase 在入口处映射（宪法 §2）。
 */

export const API_PREFIX = "/api/v1/schedule" as const;
export const GENERATE_PATH = "/api/v1/schedule/generate" as const;
export const ADJUST_PATH = "/api/v1/schedule/adjust" as const;
export const COMMIT_PATH = "/api/v1/schedule/commit" as const;
export const PARSE_CHANGES_PATH = "/api/v1/schedule/parse-changes" as const;
export const PROJECT_DATA_PATH = "/api/v1/schedule/project-data" as const;
export const EXPORT_PLAN_PATH = "/api/v1/schedule/export-plan" as const;

/** 活动模板项（每项目一套模板；按 scope 实例化到 项目/机房/批次/PoD，01§10 §3）。 */
export interface Activity {
  /** 模板内唯一编号，如 3.1（实例化后 instance_id=<作用域id>/<activity_id>，根治撞号）。来源：02/01《活动ID》=02/04《序号》 */
  activity_id: string;
  /** 活动名称。来源：02/01《活动名称》=02/04《二级活动》 */
  activity_name: string;
  /** 所属阶段。来源：02/04《所属阶段》/《一级活动》 */
  phase?: string | null;
  /** 作用域：项目级/机房级/批次级/PoD级——决定复制几遍、在哪汇合（01§10 §3）。来源：02/04 J 列（表头行2） */
  scope: "项目级" | "机房级" | "批次级" | "PoD级";
  /** 普通/里程碑/到货/机房准备/返工（01§10 §2）。来源：按名称判读（*到货*→到货、机房改造*→机房准备）+配置 */
  activity_type?: "普通" | "里程碑" | "到货" | "机房准备" | "返工";
  /** 站/货/人（01§10）。可空：不参与日期计算（靠依赖网络传导），用于解释材料与方案C指向。来源：引擎按活动推断（机房改造*→站、*到货*→货、其余施工→人），后续要精确可在基线表加列 */
  constraint_source?: "站" | "货" | "人" | null;
  /** 固定/规模分档/弹性（01§11 §2；'—'=机房准备/到货类，被外部日期锚定）。来源：02/04《SLA形态》（M列） */
  duration_mode?: "固定" | "规模分档" | "弹性";
  /** 标准 SLA（天）。规模分档活动按 project_scale 取档后的值。来源：02/04《标准工时》或 02/01《SLA》（'3天'→3） */
  standard_sla_days?: number | null;
  /** 极限 SLA（天）=压缩下限（01§11 §1）。来源：02/04《极限工时》 */
  minimum_sla_days?: number | null;
  /** 弹性活动 ≥1 条（如 网络设备安装 拆 盒式/框式 两条）；固定/规模分档/锚定类为空。来源：02/04 工时单元格解析 */
  workload_rules?: WorkloadRule[];
  /** 是否四默认里程碑之一（机房就位/到货/上电/上线，01§10 §5）。来源：配置 */
  is_default_milestone?: boolean;
  /** 分工/责任角色。来源：02/04《分工》 */
  responsibility?: string | null;
  /** 备注（风险识别/保障措施/解释素材，01§30 一.5）。来源：02/04《备注》 */
  note?: string | null;
  /** 活动自带风险规则（命中即报，01§14 §2）。来源：02/04 风险五列 */
  risk_rule?: RiskRule | null;
}

/** 沙箱推演：在基线版本上应用变更，出多方案比选；不写回（01§13 §1）。 */
export interface AdjustRequest {
  plan_id: string;
  /** 基于哪版计划推演 */
  base_version: number;
  changes: ChangeSet;
}

export interface AdjustResponse {
  /** A 均匀 / B 集中 / C 站货提拉（时间富余时含 buffer延长）；每卡含 KPI+完整排期+风险+一句建议 */
  options: StrategyPlan[];
  /** 所有策略都到顶仍做不到的诉求 */
  unmet?: UnmetItem[];
  explanation: Explanation;
}

export interface Anchor {
  /** 锚点标识。来源：前端生成 */
  anchor_id: string;
  /** 作用对象（活动实例/批次上电/批次上线/项目移交/到货/机房就位） */
  target: TargetRef;
  /** 时间值 */
  anchor_date: string;
  /** 来源类型（决定默认优先级，见 common.ANCHOR_PRIORITY_DEFAULT） */
  anchor_source: "移交里程碑" | "上线" | "上电" | "到货" | "机房就位" | "指定活动" | "客户诉求";
  /** 不填则按 anchor_source 取默认（01§12 §3，数字小者优先） */
  priority?: number | null;
  /** 硬/软（客户偏好类默认软，'必须某日前'可转硬） */
  is_hard?: boolean;
}

/** 到货行（BOQ 与到货表都是「数量输入」，喂工作量换算，01§30 一.3）。 */
export interface ArrivalItem {
  /** 到货记录标识。来源：02/06《ID》 */
  arrival_id: string;
  /** 归属 PoD（管理单元）。来源：02/06《管理单元》 */
  pod_id: string;
  /** 设备/物料类型，如 灵衢线缆、计算柜。来源：02/06《设备类型》 */
  device_type: string;
  /** 型号。来源：02/06《型号》 */
  device_model?: string | null;
  /** 计量单位（根/柜/台）。来源：02/06《单位》 */
  unit?: string | null;
  /** 数量（弹性活动工作量来源）。来源：02/06《数量》 */
  quantity: number;
  /** 实际或预计到货日（对依赖到货的活动是锚点）。来源：02/06《到货日期》 */
  arrival_date?: string | null;
  /** 三态（导入按到货日期推导，规则见 common.ArrivalStatus）。来源：02/06《到货日期》推导 */
  arrival_status: "已到货" | "在途" | "未明";
  /** 来源：02/06《备注》 */
  note?: string | null;
}

export interface Batch {
  /** 批次唯一标识。来源：前端生成 */
  batch_id: string;
  /** 展示名，如 批次1。来源：02/09《批次名》 */
  batch_name: string;
  /** 该批包含的 PoD（拖 PoD 入批，批=一组一起上电/上线的 PoD）。来源：02/09《该批包含的PoD》 */
  pod_ids: string[];
  /** 上电目标（批次级、同批统一；硬目标锚点）。来源：02/09《上电目标日期》 */
  power_on_target_date?: string | null;
  /** 上线目标（=该批排期终点）。来源：02/09《上线目标日期》/合同 */
  online_target_date?: string | null;
}

/** 攒好的变更（按实体去重，殊途同归的四个入口都落到这，01§20 §3.1）。 给到的实体按 id 整体覆盖基线里的同 id 对象；没给的不动。 */
export interface ChangeSet {
  /** 机房 ready/窗口变更 */
  rooms?: Room[];
  /** 到货回填/变更 */
  arrivals?: ArrivalItem[];
  /** 队伍增减/经验调整 */
  teams?: Team[];
  /** 拖上电/上线目标旗、改分批（只动旗，冻结其它，01§20 §3.2） */
  batches?: Batch[];
  anchors?: Anchor[];
  /** 提前/延后/某日期前完成 诉求 */
  demands?: DemandRequest[];
  reworks?: ReworkEvent[];
  incidents?: IncidentEvent[];
  rule_config?: RuleConfig | null;
}

/** 人选中某方案「确认 & 下发」→ 写回正式计划，产生新版本（可回滚，01§13 §1）。 */
export interface CommitRequest {
  plan_id: string;
  base_version: number;
  /** AdjustResponse.options 里被选中的方案 */
  option_id: string;
  /** 选后微调：活动实例 id → 微调后工期天数；后端只采信工期，日期由引擎重算 */
  duration_overrides?: Record<string, number> | null;
}

export interface CommitResponse {
  plan_id: string;
  new_version: number;
  plan: PlanResult;
}

export interface ConflictDetail {
  /** 冲突的约束（业务语言） */
  constraint: string;
  detail?: string | null;
}

/** 闭区间日期段（工期 = end − start + 1，01§00 §6.4）。 */
export interface DateRange {
  start: string;
  end: string;
}

/** 用户调整诉求（可多条并存）。 */
export interface DemandRequest {
  /** 来源：前端生成 */
  demand_id: string;
  target: TargetRef;
  /** 提前 | 延后 | 某日期前完成。来源：前端 */
  direction: string;
  /** 调整量（天）；direction=某日期前完成 时不填 */
  amount_days?: number | null;
  /** direction=某日期前完成 时必填 */
  deadline?: string | null;
  /** 触发原因（解释材料素材） */
  reason?: string | null;
}

export interface Dependency {
  /** 前置活动（模板 id）。来源：02/02《前置活动ID》；02/04 SS/SF/FS/FF 列按《序号》解析 */
  from_activity_id: string;
  /** 后继活动（模板 id）。来源：02/02《后继活动ID》 */
  to_activity_id: string;
  /** v1 引擎只解析 FS；SS/FF/SF 收录但报暂不支持（01§00 §6.3）。来源：02/04 四列/02/02 */
  dep_type?: "FS" | "SS" | "FF" | "SF";
}

/** 422 业务不可行；400 字段校验错（FastAPI/Pydantic 默认格式）；500 内部错误。 */
export interface ErrorResponse {
  /** 如 INFEASIBLE（窗口交集为空/压到极限仍差，01§12 §1 步骤④）、IMPORT_ERROR（名字→id 解析失败）。注：非 FS 依赖自 T-008 起不再整体报错，降级为逐条「依赖未纳入」风险 */
  code: string;
  /** 业务语言的原因 */
  message: string;
  conflicts?: ConflictDetail[];
}

export interface Explanation {
  /** 初排还是调整 */
  is_initial: boolean;
  /** 用了哪些锚点（anchor_id 或业务描述） */
  anchors_used?: string[];
  /** 用的策略；倒排建议/常规初排为 None */
  strategy_used?: "均匀压缩" | "集中压缩" | "站货提拉" | "buffer延长" | null;
  /** 关键路径如何变化（业务语言） */
  critical_path_change?: string | null;
  /** 被顺延/提前的活动（关键路径上需变化的单独展示，01§13 §1） */
  moved_activities?: MovedActivity[];
  /** 可直接拿去与客户沟通的解释要点 */
  notes?: string[];
}

/** 初排：给全量输入，引擎按批次完备度自动分流（01§20 §1 两轴）。 */
export interface GenerateRequest {
  inputs: InputBundle;
}

export interface GenerateResponse {
  /** 可执行部分的计划（信息不足批的活动日期标 is_ai_generated） */
  plan: PlanResult;
  /** 到货/机房未定的批 → 倒排建议（01§20 §2） */
  readiness_suggestions?: ReadinessSuggestion[];
  risks?: RiskItem[];
  unmet?: UnmetItem[];
  explanation: Explanation;
}

/** 意外事件=时间窗口产能系数（01§11 §4、01§13 §6）。 */
export interface IncidentEvent {
  /** 来源：前端生成 */
  incident_id: string;
  incident_type: "效率打折" | "假期停工";
  /** 影响时间窗口；作用于窗口内当天在施工的活动（动态判定） */
  window: DateRange;
  /** 效率打折=档位或自定义(0,1)；假期停工=0。同日多事件取最小，再乘队伍常驻系数 */
  efficiency: number;
  reason?: string | null;
}

export interface InputBundle {
  project: Project;
  rooms: Room[];
  pods: Pod[];
  arrivals?: ArrivalItem[];
  /** 不给则默认 机房数=队伍数、每队12人、经验一般（01§11 §3） */
  teams?: Team[];
  /** 活动模板（每项目一套） */
  activities: Activity[];
  dependencies: Dependency[];
  batches: Batch[];
  anchors?: Anchor[];
  rule_config?: RuleConfig;
}

export interface MovedActivity {
  instance_id: string;
  old_start?: string | null;
  old_end?: string | null;
  new_start: string;
  new_end: string;
  /** 顺延 | 提前 */
  direction: string;
}

/** 固定模板变更表解析结果：确定性转为 ChangeSet，非致命问题放 warnings。 */
export interface ParseChangesResponse {
  changes: ChangeSet;
  warnings?: string[];
}

export interface PlanKpis {
  pod_count: number;
  /** 总工期 */
  total_duration_days: number;
  /** 压缩天数 */
  compressed_days?: number;
  /** 增员人数（A/B 对弹性活动生效，有 18人/队、一PoD一队 天花板，01§11 §3） */
  added_crew?: number;
}

/** 一版完整计划（含版本，可回滚/对照，01§13 §1）。 */
export interface PlanResult {
  /** 计划标识。来源：引擎 */
  plan_id: string;
  /** 计划版本号（写回时递增） */
  version: number;
  /** 基于哪版调整而来；初排为 None */
  base_version?: number | null;
  activities: ScheduledActivity[];
  /** 关键路径上的 instance_id 链 */
  critical_path?: string[];
  /** 整体交付日（末批上线/移交） */
  project_finish_date?: string | null;
}

export interface Pod {
  /** PoD 唯一标识=管理单元全称（如 B2DH401-POD01）。来源：02/05《PoD名称》=02/06《管理单元》 */
  pod_id: string;
  /** 所属机房。来源：02/05《机房名称》 */
  room_id: string;
  /** 计算柜数量（弹性活动工作量输入，如液冷计算柜安装）。来源：02/05《计算柜》按编号计数 */
  compute_cabinet_count?: number | null;
  /** 其它柜数量（总线/Leaf/管理面合计）。来源：02/05 各柜列计数 */
  other_cabinet_count?: number | null;
  note?: string | null;
}

export interface Project {
  /** 项目唯一标识。来源：02/02《项目编号》(PROJECT_ID) */
  project_id: string;
  /** 项目名称。来源：配置 */
  project_name: string;
  /** 项目开始日。来源：配置/合同 */
  start_date?: string | null;
  /** 移交时间=合同交付目标（项目级硬锚点）。来源：合同 */
  handover_date?: string | null;
  /** 项目场景，如 集群集成。来源：02/02《项目场景》 */
  scene?: string | null;
  /** 产品形态，如 A3。来源：02/02《产品形态》 */
  product_form?: string | null;
  /** 散热方式，如 liquid_cooling。来源：02/02《散热方式》 */
  cooling_method?: string | null;
  /** 项目规模标签（如 标准项目）。仅作 total_card_count 缺失时的取档回退。来源：02/02《项目规模》 */
  project_scale?: string | null;
  /** 集群总卡数——规模分档的第一依据：<1000 千卡以下；1000~10000 千卡至万卡；>10000 万卡以上（2026-06-10 拍板：数字泛化取代标签判断）。来源：合同/前端录入（02 源表暂无此列） */
  total_card_count?: number | null;
  /** 整体约束说明。来源：配置 */
  note?: string | null;
}

/** 方案 C 的产出：倒推的理想前置输入时间，交业务跟上游谈（01§13 §3.1）。 */
export interface PulledInput {
  /** 到货(pod_id) 或 机房就位(room_id) */
  target_desc: string;
  current_date: string | null;
  suggested_date: string;
}

/** 信息不足批次的倒排建议（不含 A/B/C，用标准 SLA，01§20 §2）。 */
export interface ReadinessSuggestion {
  batch_id: string;
  /** room_id → 建议机房就位日。来源：引擎沿网络倒推（01§12 §1.1） */
  suggested_room_ready?: Record<string, string>;
  /** pod_id → 建议到货日 */
  suggested_arrival?: Record<string, string>;
}

/** 返工：插入独立返工活动，不改原活动（01§13 §5）。 */
export interface ReworkEvent {
  /** 来源：前端生成 */
  rework_id: string;
  /** 返工活动名称 */
  rework_name: string;
  /** 插入位置：哪个活动实例之后 */
  insert_after_instance_id: string;
  /** 持续时间（天） */
  duration_days: number;
  /** 触发原因 */
  reason?: string | null;
  /** 是否阻断后续 */
  blocks_downstream?: boolean;
}

export interface RiskItem {
  /** 压缩强度 / 活动风险 / 链路聚合（01§14 §2） */
  risk_type: "压缩强度" | "活动风险" | "链路聚合" | "依赖未纳入";
  severity: "高" | "中" | "低";
  /** 关联活动实例；链路聚合风险可为 None */
  instance_id?: string | null;
  /** 业务语言描述（给交付负责人看，不出算法黑话） */
  message: string;
  /** 保障措施（活动风险来自 02/04《风险应对预案》） */
  mitigation?: string | null;
}

/** 活动风险表行（01§14 §2 第二来源；v1 先立形状，内容随基线表灌入）。 */
export interface RiskRule {
  /** 风险判断逻辑。来源：02/04《风险判断逻辑》 */
  trigger_logic?: string | null;
  /** 来源：02/04《风险名称》 */
  risk_name?: string | null;
  /** 来源：02/04《风险描述》 */
  description?: string | null;
  /** 对排期/交付的影响。来源：02/04《风险影响》 */
  impact?: string | null;
  /** 应对预案=保障措施。来源：02/04《风险应对预案》 */
  mitigation?: string | null;
  /** 预案责任人。来源：02/04《预案对应的责任人》 */
  mitigation_owner?: string | null;
}

export interface Room {
  /** 机房唯一标识（即机房名称，如 B2DH401）。来源：02/05《机房名称》 */
  room_id: string;
  /** 可布线日（机房 ready 三段之一）。来源：前端/客户 */
  cabling_ready_date?: string | null;
  /** 可装设备日（三段之二）。来源：前端/客户 */
  install_ready_date?: string | null;
  /** 可通液日（三段之三）。任一段非空=可进场，三段全空=待定（01§30）。来源：前端/客户 */
  liquid_ready_date?: string | null;
  /** 断电窗口（上电类活动须落在窗口内）。来源：前端/客户 */
  power_off_windows?: DateRange[];
  /** 其它现场条件（洁净度/供电/承重等，v1 不建模只记录）。来源：前端 */
  note?: string | null;
}

export interface RuleConfig {
  /** 集中压缩压前 K 个可压活动（01§13 §3） */
  concentrate_top_k?: number;
  /** 跳周末开关（01§11 §5） */
  skip_weekends?: boolean;
  /** 锚点优先级覆盖（默认见 common.ANCHOR_PRIORITY_DEFAULT） */
  anchor_priority_override?: Record<string, number> | null;
}

export interface ScheduledActivity {
  /** 实例唯一 id = <作用域对象id>/<activity_id>（如 B2DH401-POD01/3.1；项目级 project/<id>）。来源：引擎 */
  instance_id: string;
  /** 模板活动 id。来源：模板 */
  activity_id: string;
  activity_name: string;
  /** 挂在谁身上（项目/机房/批次/PoD） */
  scope_ref: ScopeRef;
  start_date: string;
  /** 闭区间：工期 = end − start + 1 */
  end_date: string;
  /** 本次采用工期：=标准 | 压缩到[极限,标准) | >标准(buffer)（01§11 §1）。来源：引擎 */
  actual_sla_days: number;
  /** 冗余带出便于前端标风险（实际<标准 即压缩） */
  standard_sla_days?: number | null;
  /** 是否在关键路径上（每次调整后重算，01§12 §4） */
  is_critical?: boolean;
  is_milestone?: boolean;
  /** 四默认里程碑之一或移交；非里程碑为 None */
  milestone_kind?: "机房就位" | "到货" | "上电" | "上线" | "移交" | null;
  /** 前置实例（按 id，01§30 二.1） */
  predecessor_instance_ids?: string[];
  /** 分派队伍（弹性活动）。来源：引擎 */
  team_id?: string | null;
  /** 日期是否 AI 建议（倒排建议标 AI 产出，01§20 §2） */
  is_ai_generated?: boolean;
}

/** 作用域定位：这个活动实例/对象挂在谁身上。 */
export interface ScopeRef {
  scope: "项目级" | "机房级" | "批次级" | "PoD级";
  /** 机房→room_id；批次→batch_id；PoD→pod_id；项目级→None */
  ref_id?: string | null;
}

export interface StrategyPlan {
  /** 方案标识（用于 commit 选定） */
  option_id: string;
  strategy: "均匀压缩" | "集中压缩" | "站货提拉" | "buffer延长";
  kpis: PlanKpis;
  /** 该方案下的完整排期（含关键路径） */
  plan: PlanResult;
  /** 引入风险 高/中/低（01§14 §3） */
  risk_level: "高" | "中" | "低";
  /** 一句建议（比选依据） */
  advice: string;
  risks?: RiskItem[];
  /** 仅方案 C 非空 */
  pulled_inputs?: PulledInput[];
}

/** 锚点 / 诉求的作用对象。 */
export interface TargetRef {
  kind: "活动实例" | "批次上电" | "批次上线" | "项目移交" | "到货" | "机房就位";
  /** 活动实例→instance_id；批次→batch_id；到货→pod_id；机房→room_id；项目移交→None */
  ref_id?: string | null;
}

export interface Team {
  /** 队伍唯一标识。来源：02/08《队伍编号》 */
  team_id: string;
  /** 人数：默认 12、可调、上限 18（2026-06-10 拍板，与 02/08 一致）。来源：02/08《人数》 */
  size?: number;
  /** 经验档→常驻产能系数 1.0/0.8/0.7（同时作用于标准与极限 SLA）。来源：02/08《经验等级》 */
  experience?: "丰富" | "一般" | "缺乏";
  /** 在场/待命。来源：02/08《在场状态》（在场/待分配） */
  on_site?: boolean;
  /** 可用起始日。来源：前端/配置 */
  available_from?: string | null;
}

/** 不可满足=硬结论：当前规则下做不到（01§14 §1）。 */
export interface UnmetItem {
  /** 哪个诉求/锚点做不到 */
  target_desc: string;
  /** 卡在哪个约束（压到极限仍差/前置锁死提不动/资源到顶……） */
  reason: string;
  /** 差多少天 */
  gap_days?: number | null;
}

/** 弹性活动的工作量换算（01§11 §2）。统一折算成「日速率」： 工期 = 匹配到的数量 ÷ daily_rate；增员缩放以 assumed_crew 为基准（缩放律属引擎）。 源文本四种格式与折算规则见 contracts/README「导入规则」。 */
export interface WorkloadRule {
  /** 按 device_type 匹配 ArrivalItem.quantity 汇总，如 灵衢线缆、计算柜、盒式网络设备。来源：02/04《标准工时》单元格文本 */
  workload_source: string;
  /** 根/柜/台。来源：同上 */
  unit?: string | null;
  /** 标准日速率（数量/天）：'2688根/12天'→224、'48柜/天'→48。来源：02/04《标准工时》 */
  standard_daily_rate: number;
  /** 极限日速率（压缩后的上限速率）：'2688根/7天'→384。来源：02/04《极限工时》 */
  limit_daily_rate?: number | null;
  /** 速率隐含的班组人数（备注'资源投入：硬件安装4人'），增员缩放基准。来源：02/04 备注 */
  assumed_crew?: number | null;
}
