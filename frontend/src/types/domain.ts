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
