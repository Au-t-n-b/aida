/* Shared domain types for claw-delivery-ui mock data & components */

import type { ReactNode } from 'react';

/* ── App / cockpit ── */
export type Severity = 'red' | 'amber' | 'blue';
export type ProjectStatus = 'red' | 'amber' | 'green' | 'idle';
export type PodState = 'ready' | 'at-risk' | 'blocked';
export type ChainSeg = 'g' | 'a' | 'r' | 'idle';
export type ActionKind = 'primary' | 'ghost' | 'danger';
export type RiskCategory = 'unmeet' | 'atrisk';
export type RiskSeverity = 'red' | 'amber';
export type RiskSourceKey = 'customer' | 'logistic' | 'field' | 'design' | 'compliance' | 'erp' | 'doc';
export type MilestoneStatus = 'risk' | 'ok' | 'late';
export type ChatRole = 'ai' | 'user';

export interface Pod {
  id: string;
  room: string;
  stage: string;
  chain: ChainSeg[];
  state: PodState;
}

export interface Project {
  id: string;
  name: string;
  customer: string;
  deadline: string;
  progress: number;
  status: ProjectStatus;
  rooms: number;
  podCount: number;
  pd: string;
  td: string;
  pods: Pod[];
}

export interface Evidence {
  src: string;
  ref: string;
}

export interface InsightAction {
  label: string;
  kind: ActionKind;
  icon?: string;
}

export interface AIInsight {
  id: string;
  severity: Severity;
  ts: string;
  title: string;
  evidence: Evidence[];
  impact: { route: string; delay: string };
  actions: InsightAction[];
}

export interface Risk {
  cat: RiskCategory;
  sev: RiskSeverity;
  source?: RiskSourceKey;
  title: string;
  project: string;
  pod: string;
  owner: string;
  delay: string;
  sla: string;
  age: string;
}

export interface RiskSourceMeta {
  label: string;
  tone: string;
}

export type RiskSources = Record<RiskSourceKey, RiskSourceMeta>;

export interface Milestone {
  date: string;
  days: string;
  title: string;
  project: string;
  status: MilestoneStatus;
  label: string;
}

export interface Summary {
  contractPace: { value: number; total: number; unit: string; on: number; risk: number; late: number };
  activeProjects: { value: number; group: string };
  pods: { total: number; ready: number; partial: number; blocked: number };
  rooms: { total: number; ready: number; prep: number; blocked: number };
  teams: { total: number; dispatched: number; headcount: number; short: number };
  risks: { red: number; amber: number };
  nearestMilestone: { name: string; days: number; date: string; status: string };
}

export interface ReasoningStep {
  ix: string;
  text: string;
}

export interface ChatMessage {
  role: ChatRole;
  body: string;
  ts: string;
  reasoning?: ReasoningStep[];
  chips?: string[];
  actions?: InsightAction[];
}

/* ── Journey ── */
export type JourneyRole = 'TD' | 'PD' | 'TL' | 'OCC' | 'System';
export type ModuleStatusState = 'live' | 'ok' | 'warn' | 'alert' | 'idle';
export type PlanStream = 'site' | 'goods' | 'people';
export type PlanBarStatus = 'ok' | 'risk';
export type SiteState = 'ready' | 'prep' | 'blocked';
export type TwinRoomStatus = 'ok' | 'risk' | 'blocked';
export type ChapterState = 'ok' | 'partial' | 'gap';
export type LldFieldState = 'ok' | 'pending';

export interface JourneyDecision {
  label: string;
  kind: ActionKind | string;
}

export interface JourneyStage {
  key: string;
  ord: number;
  name: string;
  role: JourneyRole;
  title: string;
  subtitle: string;
  storyTag: string;
  summary: string;
  aiPrompt: string | null;
  productPath?: string;
  productLabel?: string;
  productPathExtra?: { path: string; label: string }[];
  durationDay?: number;
  sysSnapshot?: { overall: string; highlight: string };
  keyData?: { k: string; v: string }[];
  decisions: JourneyDecision[];
  fields?: { key: string; label: string; value: string; auto: boolean; hint?: string }[];
  approvalTimeline?: { t: string; who: string; act: string; state: string }[];
  documents?: { name: string; size: string; parsed: boolean | string; items: number; note?: string }[];
  extractedElements?: { cat: string; total: number; ready: number; blocker?: boolean }[];
  snapshot?: {
    version: string;
    ts: string;
    completeness: number;
    chapters?: { name: string; state: ChapterState; note?: string }[];
    diff?: { ch: string; change: string }[];
  };
  contractEvent?: { id: string; signTs: string; bindTs: string; amount: string; milestones: number };
  lldFields?: { k: string; v: string; state: LldFieldState }[];
  workstreams?: {
    key: string;
    name: string;
    icon: string;
    total: number;
    done: number;
    atRisk: number;
    blocked: number;
    kpi: string;
  }[];
  closeMetrics?: { k: string; v: string }[];
  handover?: { item: string; state: string; note?: string }[];
  [key: string]: unknown;
}

export interface PlanGanttRow {
  id: string;
  name: string;
  start: number;
  dur: number;
  stream: PlanStream;
  status: PlanBarStatus;
}

export interface PlanPerson {
  team: string;
  members: number;
  allocPct: number;
  status: 'ok' | 'risk';
  current: string;
  warn?: string;
}

export interface PlanGood {
  sku: string;
  total: number;
  arrived: number;
  eta: string;
  status: PlanBarStatus;
}

export interface PlanSite {
  room: string;
  state: SiteState;
  pods: number;
  blocker: string | null;
}

export interface TwinRoom {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  status: TwinRoomStatus;
  pods: number;
  ready: number;
  label: string;
  project?: string;
  customer?: string;
  env?: { temp: number; humidity: number; pue: number | null; power: number; util: number };
  issue?: string | null;
  podLayout?: string[][];
  podIds?: string[];
  [key: string]: unknown;
}

/* ── Modules ── */
export interface ModuleHitlOption {
  label: string;
  value: string;
  desc?: string;
  badge?: string;
}

export interface ModuleMetric {
  label: string;
  value: number;
  unit: string;
  tone?: string;
  decimals?: number;
}

export interface ModuleSchema {
  key: string;
  name: string;
  iconName: string;
  subtitle: string;
  steps: string[];
  embed: string | null;
  welcome: string;
  decideAsk: string;
  uploadAsk: string;
  executeAsk: string;
  finishAsk: string;
  hitl: {
    title: string;
    hint: string;
    multi: boolean;
    options: ModuleHitlOption[];
  };
  scenarioTable: { scenario: string; score: number; risk: string; notes: string; tone: string }[];
  files: { name: string; size: number }[];
  outputs: { name: string; size: number }[];
  skillNames: string[];
  finalOutput: string;
  metricsByStage: Record<string, ModuleMetric[]>;
  tracks: { id: string; label: string; skill: string }[];
  synthesisParagraphs: { title: string; text: string }[];
  [key: string]: unknown;
}

export type ModuleSchemas = Record<string, ModuleSchema>;

/* ── Tweaks ── */
export type TweakDensity = 'compact' | 'regular' | 'relaxed' | 'comfy';

export interface TweakState {
  density: TweakDensity;
  brand: string;
  clawCollapsed: boolean;
  clawWidth: number;
  stage: string;
  /** Dev Tweaks · 演示用：切到不同 module 路由 */
  module?: string;
  /** Dev Tweaks · 演示用：accent 强调色 hex */
  accent?: string;
}

/* ── Landing ── */
export type Stage4Key = 'survey' | 'modeling' | 'install' | 'deploy';

export interface LandingProject {
  id: string;
  name: string;
  code: string;
  roles: string[];
  stage4: Stage4Key;
  stage4Label: string;
  todoCount: number;
  overdueCount: number;
  canEdit: boolean;
}

/* ── Primitives helpers ── */
export type WithChildren = { children?: ReactNode };

/* ── Dispatch tracking（项目孪生 · 下发追踪）──
 * 可交付性研判产生的风险与任务，下发到人后在项目孪生里追踪闭环。
 * 与 Risk（档案库）区别：DispatchItem 是「本次研判下发项」的作战态势 + 闭环状态机。
 */
export type DispatchKind = 'risk' | 'task';

/* 下发项闭环状态机：
 *   待接收 → 已接收 → 处理中 → 已完成
 *                    ↘ 逾期 / 已升级（抽到「需要你处理」专区）
 */
export type DispatchStatus =
  | 'pending-ack'   // 待接收（已推送 WeLink，owner 未响应）
  | 'acked'         // 已接收（owner 已确认收到）
  | 'in-progress'   // 处理中
  | 'done'          // 已完成（可回流降级父风险）
  | 'overdue'       // 逾期（超 SLA 未闭环）
  | 'escalated';    // 已升级（上抛 PD / 上级）

export type DispatchOwnerRole = 'TD' | 'PD' | 'TL' | '供应链' | '客户侧' | 'OCC';

export interface DispatchOwner {
  name: string;
  role: DispatchOwnerRole;
  avatar: string;   // 2 字头像缩写
}

export interface DispatchAck {
  ts: string;       // 回执/动作时间
  actor: string;    // 谁触发
  note: string;     // 动作说明（已接收 / 已催办 / 已升级 …）
}

/* 溯源链：把孪生里的下发项一路钩回研判 → 风险 → 预案章节，落地「AI 可见即可信」 */
export interface DispatchSource {
  deliverability: string;   // 研判批次 id，如 DLV-01
  risk?: string;            // 关联风险 id
  proposalRef?: string;     // 预案章节 / BOQ 行
}

export interface DispatchImpact {
  route: string;            // 影响链路
  drift: string;            // 对 as-is vs should-be 偏差的影响
  room?: string;            // 锚定机房（驱动孪生空间叠加）
  pod?: string;
}

export interface DispatchItem {
  id: string;
  kind: DispatchKind;
  title: string;
  status: DispatchStatus;
  parentRiskId?: string;        // 任务 → 父风险，画 lineage
  owner: DispatchOwner;
  dispatchedAt: string;
  channel: 'WeLink';
  sla: string;                  // SLA 口径，如 "LLD 出图前"
  due: string;                  // 倒计时/口径，如 "T-2"
  overdueBy?: string;           // 逾期时长，仅 status==='overdue'
  source: DispatchSource;
  impact: DispatchImpact;
  acks?: DispatchAck[];
}

export interface DispatchRun {
  id: string;
  title: string;
  proposalVersion: string;
  dispatchedAt: string;
}

/* ── 交付预案 · 第 9–12 章 ── */
export interface RaciRow {
  stack: string;
  cat: string;
  act: string;
  gts: string;
  hw: string;
  partner: string;
  customer: string;
}

export interface PlanActivity {
  name: string;
  start: string;
  end: string;
  actualStart: string;
  actualEnd: string;
  owner: string;
  unit: string;
  status: string;
  progress: number;
  progressTone: 'blue' | 'green';
}

export interface AcceptanceItem {
  cat: string;
  scheme: string;
  standard: string;
  milestone: string;
  doc: string;
  payment: string;
  paymentMilestone: string;
}

export interface AcceptanceTestCase {
  id: string;
  l1: string;
  l2: string;
  l3: string;
  purpose: string;
  topology: string;
  pre: string;
  steps: string[];
  expects: string[];
  result: string;
  remark: string;
}

export interface ProposalTableVersions {
  raci: number;
  acceptance: number;
  testCases: number;
}

export interface SavedTestCaseRow extends AcceptanceTestCase {
  selected: boolean;
}

/* ── 预案本体生成（delivery-contingency-plan · deriveContingencyRisks）──
 * 数字孪生「预案本体生成」页消费 ontology 服务(:8011)派生的预案风险（建议值）。
 * 四条生命周期通道映射到脑图四槽位，详见 src/lib/contingency-view.ts。
 */
export type ContingencyLaneKey = 'network' | 'device' | 'service' | 'acceptance';
export type OntologyDecision = 'risk' | 'success';
export type OntNodeResult = 'warning' | 'success';
export type SeverityClass = 'high' | 'mid' | 'low';

/** 溯源证据：引擎对一行事实所做的那次比较（字段 / 值 / 比较符 / 比较对象） */
export interface ContingencyProvenanceEvidence {
  field: string;
  value: string;
  comparator: string;
  threshold: string;
  thresholdLabel: string;
}

/** 溯源触发主体：规则在哪行本体事实上命中、为什么命中 */
export interface ContingencyProvenanceSubject {
  label: string;
  /** 事实底座 ObjectType apiName，如 EquipmentConfig */
  objectType: string;
  /** ObjectType 中文显示名（取自 schema displayMetadata） */
  objectTypeLabel: string;
  /** 源数据行主键值（如 equipmentId），缺省空串 */
  keyValue: string;
  /** 人读的命中原因，复现引擎所做的比较 */
  reason: string;
  evidence: ContingencyProvenanceEvidence;
}

/** 一条派生风险的推导溯源链：RiskRule 规则行 × 触发主体（事实行 + 证据）× 基准日 */
export interface ContingencyRiskProvenance {
  engine: string;
  referenceDate: string;
  horizonDate: string;
  rule: {
    ruleId: string;
    ruleName: string;
    riskPoint: string;
    riskCategory: string;
    riskSubCategory: string;
    riskLevel: string;
    owner: string;
    source: string;
  };
  subjects: ContingencyProvenanceSubject[];
}

/** 后端 deriveContingencyRisks 派生的单条风险（RiskItem 形态的建议记录） */
export interface ContingencyRisk {
  riskId: string;
  riskName: string;
  riskPoint: string;
  riskType: string;
  severity: string; // 高 / 中 / 低
  owner: string;
  mitigationPlan: string;
  impact: string;
  description: string;
  subjects: string[];
  /** 推导溯源（规则 × 触发主体 × 字段级证据）；旧服务可能缺省 */
  provenance?: ContingencyRiskProvenance;
  planId?: string;
  projectKey?: string;
  assessmentId?: string;
  state?: string;
  status?: string;
  source?: string;
  identifiedAt?: string;
}

/** deriveContingencyRisks Function 的 result 体 */
export interface ContingencyGeneration {
  planId: string;
  projectKey: string;
  assessmentId: string;
  riskCount: number;
  risks: ContingencyRisk[];
  /** 后端按本体章节目录生成的交付预案 12 章（每章绑定 riskIds/state）；旧服务可能缺省 */
  chapters?: ContingencyChapter[];
  /** 后端生成的决策点：核心 方案可交付性 + 4 子决策点（聚合章节/风险）；旧服务可能缺省 */
  decisionPoints?: ContingencyDecisionPoint[];
}

/** 脑图节点视图模型（key 沿用 digital-ontology 内部槽位，保证粒子/动画键不变） */
export interface OntologyNodeView {
  key: ContingencyLaneKey;
  title: string;
  en: string;
  tag: string;
  resultTag: string;
  result: OntNodeResult;
  pos: { x: number; y: number };
  desc: string;
  count: number;
  /** 点击该节点跳转的章节锚点（= 该子决策点首章 id）；缺省回退 doc-<key> */
  anchor?: string;
}

/** 后端生成的子决策点（复用本体 DecisionPoint 类型：核心 方案可交付性 + 4 子决策）。
 * 每个子决策聚合自身章节（chapter.decisionPoint == domain）+ 这些章节绑定的风险 → 结论/可交付指数。 */
export interface ContingencyDecisionPoint {
  decisionId: string;
  decisionLevel: 'core' | 'sub';
  parentDecisionId: string;
  domain: ContingencyLaneKey | 'core';
  decisionName: string;
  decisionQuestion: string;
  chapterIds?: readonly string[];
  anchorChapterId?: string;
  riskIds?: readonly string[];
  riskCount?: number;
  deliverabilityIndex?: number;
  conclusion?: string;
}

/** mapGenerationToView 的输出：驱动 DigitalTwinOntology 渲染真实预案 */
export interface OntologyView {
  nodes: OntologyNodeView[];
  decision: OntologyDecision;
  risks: ContingencyRisk[];
  /** 后端生成的交付预案章节（透传自 ContingencyGeneration.chapters） */
  chapters: ContingencyChapter[];
  /** 后端生成的决策点（透传自 ContingencyGeneration.decisionPoints）：核心 + 4 子决策 */
  decisionPoints: ContingencyDecisionPoint[];
  /** 核心决策点（方案可交付性，decisionLevel==='core'）；驱动脑图中心结论/可交付指数。缺省 null */
  coreDecision: ContingencyDecisionPoint | null;
  summary: {
    riskCount: number;
    high: number;
    mid: number;
    low: number;
    byLane: Record<ContingencyLaneKey, number>;
  };
}

/* ── 预案章节（12 章目录 + 真实风险绑定）──
 * 章节由本体服务 deriveContingencyRisks 生成（result.chapters）。目录本体驻留：绑定 ObjectType 的章
 * 来自 ontology/schema/object-types.json 各类型的 contingencyChapter 标记块（标记即成章），
 * 仅剩的无 ObjectType 占位章（计划）留在 ontology/data/contingency/contingency_chapters.json。
 * 后端把派生风险按 lane 绑定到对应可交付主章（riskIds/state）；元数据/风险&假设章已从目录删除。
 * 前端只渲染 result.chapters，不再持有章节骨架。
 */
/** 子决策点归属；global = 四个子决策点的共同输入（元数据/项目/风险假设/计划） */
export type DecisionPointKey = ContingencyLaneKey | 'global';

export interface ContingencyChapterField {
  name: string;
  note?: string;
}

export interface ContingencyChapter {
  /** DOM 锚点 id。4 个可交付主章用 doc-<lane> 承接脑图节点跳转；其余 doc-ch-*（风险清单区块沿用锚点 doc-risks） */
  id: string;
  /** 章号标签，如 '2' / '7' / '元数据' */
  no: string;
  title: string;
  decisionPoint: DecisionPointKey;
  /** 子决策点中文标签，如 '设备配置的可交付性' / '全局输入' */
  decisionLabel: string;
  /** 章节说明 */
  desc: string;
  /** 数据来源 */
  source?: string;
  /** 本章关注字段（取自预案目录字段表） */
  fields: readonly ContingencyChapterField[];
  /** 设置后，laneForRiskPoint 命中该 lane 的派生风险绑定到本章 */
  lane?: ContingencyLaneKey;
  /** 标记本章为风险&假设汇总章（§9，渲染全部风险清单） */
  consolidatesRisks?: boolean;
  /** 后端绑定到本章的派生风险 id（lane 章按 lane 绑定；§9 汇总全部）。前端按 id 取 risks 渲染 */
  riskIds?: readonly string[];
  /** 后端计算的章节状态：gap=命中风险 / ok=可交付 */
  state?: ChapterState;
  /** 本章投影的事实底座 ObjectType（如 EquipmentConfig）；缺省表示该章无后端实体可投影 */
  objectType?: string;
  /** 数据表列：key=属性 apiName（取行值用），label=中文字段名（表头），note=说明。与 rows 配对 */
  columns?: readonly ContingencyChapterColumn[];
  /** 本章事实底座行（原始 Dolt 行，按属性 apiName 取值）；空/缺省表示该章暂无落库数据 */
  rows?: readonly Record<string, unknown>[];
  /** 风险命中单元格索引（默认精简+命中追加）：标记 rows 中被规则引擎比较过的格子；无风险时缺省 */
  riskCells?: readonly ContingencyChapterRiskCell[];
  /** rows 行主键的属性 apiName（riskCells.rowKey 与 row[rowKeyField] 配对定位行）；与 riskCells 同生 */
  rowKeyField?: string;
  /** AI 生成 + 人工可改的章节正文（displayText = 人工稿优先，否则 AI 稿）；缺省回退静态 desc。 */
  narrative?: string;
  /** 正文状态：ai_draft / human_edited / merged / regen_pending（来自 ChapterNarrative.status）。 */
  narrativeStatus?: string;
  /** 生成模型名（审计展示）。 */
  narrativeModel?: string;
  /** 最近人工修改时间。 */
  narrativeEditedAt?: string;
  /** AI 原始生成稿（对比抽屉「AI 新稿」用）。 */
  narrativeGenerated?: string;
  /** 人工修改稿（对比抽屉「我的」用）。 */
  narrativeEdited?: string;
  /** 人工改后又重生成、待合并的新 AI 稿（触发「有新版本待合并」徽章）。 */
  pendingGenerated?: string;
  /** 智能融合候选稿（待人确认采纳）。 */
  mergeCandidate?: string;
  /** 章节版本历史（每次生成/编辑/采纳/里程碑追加）。 */
  versions?: readonly ContingencyNarrativeVersion[];
  /** 融合组章（doc-grp-*）：多个本体要素融合成一章——顶部 AI 概述 + 各成员保留原始数据表。 */
  isGroup?: boolean;
  /** 组章成员的源 chapterId（含临时章 doc-ot-*）；用于徽章计数。 */
  memberIds?: readonly string[];
  /** 组章成员标题（与 memberIds 同序），供徽章/说明展示。 */
  memberTitles?: readonly string[];
  /** 组章成员的完整章 dict（含各自 rows/columns/detailRows/fields/objectType）；报告按此渲染每个成员子区块的原始表单。 */
  members?: readonly ContingencyChapter[];
}

/** 章节数据表的一列：把中文字段名（label）映射到行里的属性 apiName（key）。 */
export interface ContingencyChapterColumn {
  key: string;
  label: string;
  note?: string;
  /** true = 命中追加列：非 curated 静态列，由本章绑定风险的溯源证据字段派生（表头加标识） */
  derived?: boolean;
}

/** 章节数据表的一个风险命中格：绑定风险的溯源证据落在 rows 的哪一行哪一列（及为什么）。 */
export interface ContingencyChapterRiskCell {
  /** 命中行主键值（与 row[chapter.rowKeyField] 比对） */
  rowKey: string;
  /** 命中列属性 apiName（与 column.key 比对） */
  field: string;
  /** 产生该命中的派生风险 id（单元格点击回跳风险卡） */
  riskId: string;
  /** 人读的命中原因（溯源 evidence.reason，作单元格 tooltip） */
  reason?: string;
}

/** 章节正文的一条版本历史项（ChapterNarrative.versions[]）。 */
export interface ContingencyNarrativeVersion {
  seq: number;
  /** ai | human | merge | restore | milestone */
  source: string;
  text: string;
  savedAt?: string;
  by?: string;
  note?: string;
  versionLabel?: string | null;
}

/* =========================================================
   交付计划甘特图（计划章 doc-ch-12 投影 DeliveryPlanRow → 一级活动甘特）
   ========================================================= */

/** delivery_plan_row 投影行（按 apiName 取值）；甘特只用其中几列，其余字段忽略。 */
export interface DeliveryPlanActivityRow {
  /** 活动 ID：不含小数点 = 一级活动（如 '7'）；'7.1' 为二级。 */
  activityId?: string;
  activityName?: string;
  /** 管理单元（PoD）：同一活动跨多 PoD 多行，聚合时按此去重计数。 */
  managementUnit?: string;
  /** 开始/结束日期（YYYY-MM-DD）。 */
  startDate?: string;
  endDate?: string;
  owner?: string;
  /** 低于标准工期的风险（非空 → 该活动 bar 标记风险）。 */
  riskBelowStandard?: string;
  [key: string]: unknown;
}

/** 一条一级活动甘特条（跨 PoD 实例聚合后的呈现单元）。 */
export interface GanttActivity {
  activityId: string;
  name: string;
  /** 聚合起止（跨实例 min start / max end，YYYY-MM-DD）。 */
  start: string;
  end: string;
  owner: string;
  /** 覆盖的 PoD（管理单元）数。 */
  podCount: number;
  /** 工期天数（含端点，end-start+1）。 */
  durationDays: number;
  /** 任一实例命中「低于标准工期的风险」。 */
  hasRisk: boolean;
  /** bar 在时间轴上的定位（百分比，0–100）。 */
  leftPct: number;
  widthPct: number;
}

/** 甘特时间轴的一个月份列。 */
export interface GanttMonth {
  /** 'YYYY-MM' */
  key: string;
  /** 轴显示标签，如 '2026-01' / '1月'。 */
  label: string;
  /** 该月落在 [minDate,maxDate] 区间内的天数占总跨度的百分比（列宽）。 */
  widthPct: number;
}

/** buildFirstLevelGantt 的返回模型；activities 为空表示无一级活动可画。 */
export interface GanttModel {
  activities: readonly GanttActivity[];
  /** 全局跨度（YYYY-MM-DD）；activities 为空时为 ''。 */
  minDate: string;
  maxDate: string;
  /** 月份轴列（widthPct 合计 ≈ 100）。 */
  months: readonly GanttMonth[];
  /** 总跨度天数（含端点）；activities 为空时为 0。 */
  totalDays: number;
}
