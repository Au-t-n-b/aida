import type { ContingencyGeneration, ContingencyRisk } from '@/types/domain';

/* ontology 服务(:8011)地址：默认本地直连；服务器部署经 VITE_ONTOLOGY_BASE 注入（编译期）。
 * 与 useSduiStream 的 VITE_AGENT_BASE 同范式。后端已对 5173 放行 CORS。 */
const ONTOLOGY_BASE = import.meta.env.VITE_ONTOLOGY_BASE || 'http://127.0.0.1:8011';
const ONTOLOGY_ID = 'default';

export interface DeriveContingencyParams {
  planId?: string;
  projectKey?: string;
  assessmentId?: string;
  referenceDate?: string;
}

interface FunctionExecuteResponse {
  success?: boolean;
  functionName?: string;
  result?: ContingencyGeneration;
}

/** 调 deriveContingencyRisks Function，真实派生预案风险（建议值，无写回）。 */
export async function deriveContingencyRisks(
  params: DeriveContingencyParams = {},
  signal?: AbortSignal,
): Promise<ContingencyGeneration> {
  const payload: Record<string, string> = {};
  if (params.planId) payload.plan_id = params.planId;
  if (params.projectKey) payload.project_key = params.projectKey;
  if (params.assessmentId) payload.assessment_id = params.assessmentId;
  if (params.referenceDate) payload.reference_date = params.referenceDate;

  const url = `${ONTOLOGY_BASE}/api/v2/ontologies/${ONTOLOGY_ID}/functions/deriveContingencyRisks/execute`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`本体服务返回 ${res.status}${detail ? ` · ${detail.slice(0, 200)}` : ''}`);
  }
  const data = (await res.json()) as FunctionExecuteResponse;
  const result = data.result;
  if (!result || !Array.isArray(result.risks)) {
    throw new Error('本体服务响应缺少 result.risks');
  }
  return result;
}

/* deriveContingencyRisks 目前不带 plan/assessment/project 标识（hook 不传参 → 后端按全部数据派生、
 * 把这三个字段盖戳为空）。而采纳/派发类 Action 的 planId/projectKey/assessmentId 是必填，故用此
 * 稳定锚点兜底：同一会话内主键稳定，重复下发同一风险即按主键 upsert（不会重复入库）。
 * 单项目（京东 / JD 三期）演示语境下取固定值；若后续 hook 传入真实标识，风险自带值优先（见 riskAnchor）。 */
export const CONTINGENCY_ANCHOR = {
  projectKey: '京东',
  planId: 'JD_A3_CONTINGENCY',
  assessmentId: 'JD_A3_DELIVERABILITY',
} as const;

export interface ActionApplyResponse {
  success?: boolean;
  actionName?: string;
  objectType?: string;
  [key: string]: unknown;
}

const OBJECT_FIELD_UPDATE_CONFIG = {
  EquipmentConfig: {
    action: 'modifyEquipmentConfigChapterFields',
    keyField: 'equipmentId',
    targetParameter: 'targetEquipment',
    fields: ['model', 'productCode', 'version', 'lifecycleStatus', 'quantity', 'unitSpace', 'totalSpace', 'unitPower', 'totalPower'],
  },
  ComponentConfig: {
    action: 'modifyComponentConfigChapterFields',
    keyField: 'componentId',
    targetParameter: 'targetComponent',
    fields: ['componentType', 'componentCode', 'vendor', 'componentName'],
  },
  SoftwareConfig: {
    action: 'modifySoftwareConfigChapterFields',
    keyField: 'softwareId',
    targetParameter: 'targetSoftware',
    fields: ['softwareType', 'isHuaweiSoftware', 'softwareModel', 'softwareVersion', 'remark'],
  },
  NetworkConfig: {
    action: 'modifyNetworkConfigChapterFields',
    keyField: 'networkId',
    targetParameter: 'targetNetwork',
    fields: ['networkType', 'deviceVendor', 'model', 'version', 'quantity', 'remark'],
  },
  MachineRoomConfig: {
    action: 'modifyMachineRoomConfigChapterFields',
    keyField: 'machineRoomId',
    targetParameter: 'targetMachineRoom',
    fields: ['machineRoomName', 'location', 'cabinetType', 'quantity', 'remark'],
  },
  MaintenancePolicy: {
    action: 'modifyMaintenancePolicyChapterFields',
    keyField: 'maintenancePolicyId',
    targetParameter: 'targetMaintenancePolicy',
    fields: ['productModel', 'warrantyPolicy', 'maintenancePolicy', 'startDate', 'endDate', 'eosDate', 'isOverEos', 'overEosApprovalConclusion'],
  },
  AcceptanceStrategy: {
    action: 'modifyAcceptanceStrategyChapterFields',
    keyField: 'acceptanceStrategyId',
    targetParameter: 'targetAcceptanceStrategy',
    fields: ['category', 'acceptancePlan', 'acceptanceCriteria', 'acceptanceMilestone', 'acceptanceDocument', 'paymentTerms', 'paymentMilestone'],
  },
  TestCase: {
    action: 'modifyTestCaseChapterFields',
    keyField: 'testCaseId',
    targetParameter: 'targetTestCase',
    fields: ['level3Category', 'testCaseName', 'caseCode', 'testPurpose'],
  },
} as const satisfies Record<string, { action: string; keyField: string; targetParameter: string; fields: readonly string[] }>;

export type OntologyEditableObjectType = keyof typeof OBJECT_FIELD_UPDATE_CONFIG;
const objectFieldUpdateConfig: Record<string, { action: string; keyField: string; targetParameter: string; fields: readonly string[] }> =
  OBJECT_FIELD_UPDATE_CONFIG;

export interface UpdateOntologyObjectFieldParams {
  objectType: string;
  objectKey: string;
  field: string;
  value: string;
}

export function isOntologyObjectFieldEditable(objectType?: string, field?: string): boolean {
  if (!objectType || !field) return false;
  const config = objectFieldUpdateConfig[objectType];
  return Boolean(config && config.fields.includes(field));
}

export function getOntologyObjectEditableKeyField(objectType?: string): string | null {
  if (!objectType) return null;
  return objectFieldUpdateConfig[objectType]?.keyField ?? null;
}

/** 单字段事实对象写回：只支持章节表中显式 allowlist 的 Dolt-backed ObjectType 字段。 */
export async function updateOntologyObjectField(
  params: UpdateOntologyObjectFieldParams,
  signal?: AbortSignal,
): Promise<ActionApplyResponse> {
  const config = objectFieldUpdateConfig[params.objectType];
  if (!config) {
    throw new Error(`暂不支持编辑 ${params.objectType}`);
  }
  if (!config.fields.includes(params.field)) {
    throw new Error(`字段不可编辑：${params.objectType}.${params.field}`);
  }
  if (!params.objectKey) {
    throw new Error(`缺少对象主键：${config.keyField}`);
  }
  return applyOntologyAction(
    config.action,
    {
      [config.keyField]: params.objectKey,
      [config.targetParameter]: { [config.keyField]: params.objectKey },
      [params.field]: params.value,
      changes: { [params.field]: params.value },
    },
    signal,
  );
}

/** 通用 Action 执行入口：POST /actions/{action}/apply（写回 run-record overlay / Dolt / CSV）。 */
export async function applyOntologyAction(
  action: string,
  payload: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<ActionApplyResponse> {
  const url = `${ONTOLOGY_BASE}/api/v2/ontologies/${ONTOLOGY_ID}/actions/${action}/apply`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`本体服务返回 ${res.status}${detail ? ` · ${detail.slice(0, 200)}` : ''}`);
  }
  return (await res.json()) as ActionApplyResponse;
}

export interface PublishContingencyFindingsParams extends DeriveContingencyParams {}

export interface PublishContingencyFindingsResult extends ActionApplyResponse {
  riskCount?: number;
  riskRowsWritten?: number;
  taskRowsWritten?: number;
  issueRowsWritten?: number;
  updatedFiles?: string[];
  dryRun?: boolean;
}

/** 发布派生结果到项目管理 Excel：风险全量、非硬阻塞进任务、硬阻塞进问题。 */
export async function publishContingencyFindings(
  params: PublishContingencyFindingsParams = {},
  signal?: AbortSignal,
): Promise<PublishContingencyFindingsResult> {
  const payload = {
    planId: params.planId || CONTINGENCY_ANCHOR.planId,
    projectKey: params.projectKey || CONTINGENCY_ANCHOR.projectKey,
    assessmentId: params.assessmentId || CONTINGENCY_ANCHOR.assessmentId,
    ...(params.referenceDate ? { referenceDate: params.referenceDate } : {}),
  };
  return (await applyOntologyAction(
    'PublishContingencyFindings',
    payload,
    signal,
  )) as PublishContingencyFindingsResult;
}

export interface ContingencyAnchorContext {
  planName?: string;
  /** 核心决策点 id（取自 derive 的 decisionPoints，真实指向 DecisionPoint，如 DP-CORE）。 */
  decisionId?: string;
  decisionName?: string;
  /** 核心决策结论（DecisionConclusion：可交付 / 存在风险），下方映射成评估结论。 */
  conclusion?: string;
  deliverabilityIndex?: number;
}

/* 会话级幂等：第一次下发前把锚点 ContingencyPlan + DeliverabilityAssessment 真正建出来
 * （run-record 按主键 upsert），之后复用同一 Promise 不重复 POST。这样采纳的 RiskItem 指向的
 * planId / assessmentId 对应真实对象，而非悬空字符串。失败则清缓存以便下次重试。 */
let anchorPromise: Promise<{ planId: string; projectKey: string; assessmentId: string }> | null = null;

/** 重置锚点缓存（如需在切换项目后强制重建）。 */
export function resetContingencyAnchor(): void {
  anchorPromise = null;
}

/** 决策结论枚举映射：DecisionConclusion(可交付/存在风险) → DeliverabilityConclusion(可交付/存在差异/不可交付)。 */
function toDeliverabilityConclusion(conclusion?: string): string | undefined {
  if (!conclusion) return undefined;
  return conclusion === '可交付' ? '可交付' : '存在差异';
}

/** 确保锚点预案实例 + 可交付评估已落库（幂等）；返回可供采纳/派发引用的真实标识。 */
export async function ensureContingencyAnchor(
  ctx: ContingencyAnchorContext = {},
  signal?: AbortSignal,
): Promise<{ planId: string; projectKey: string; assessmentId: string }> {
  if (!anchorPromise) {
    anchorPromise = (async () => {
      const { planId, projectKey, assessmentId } = CONTINGENCY_ANCHOR;
      await applyOntologyAction(
        'CreateContingencyPlan',
        {
          planId,
          projectKey,
          planName: ctx.planName || '交付预案（数字孪生生成）',
          planVersion: 'V1.0',
          sourceSummary: '由 deriveContingencyRisks 派生批次在数字孪生页固化',
        },
        signal,
      );
      await applyOntologyAction(
        'CreateDeliverabilityAssessment',
        {
          assessmentId,
          projectKey,
          planId,
          decisionId: ctx.decisionId || 'DP-CORE',
          assessmentName: ctx.decisionName || '方案可交付性评估',
          conclusion: toDeliverabilityConclusion(ctx.conclusion),
          deliverabilityIndex: ctx.deliverabilityIndex,
        },
        signal,
      );
      return { planId, projectKey, assessmentId };
    })().catch((err: unknown) => {
      anchorPromise = null; // 允许重试
      throw err;
    });
  }
  return anchorPromise;
}

/** 派生风险自带的 plan/project/assessment 标识优先，缺省落到会话锚点。 */
function riskAnchor(risk: ContingencyRisk): { planId: string; projectKey: string; assessmentId: string } {
  return {
    planId: risk.planId || CONTINGENCY_ANCHOR.planId,
    projectKey: risk.projectKey || CONTINGENCY_ANCHOR.projectKey,
    assessmentId: risk.assessmentId || CONTINGENCY_ANCHOR.assessmentId,
  };
}

/** 「下发处理」：把派生风险建议采纳为正式 RiskItem（AdoptDerivedRisk，写回 overlay）。 */
export async function adoptDerivedRisk(
  risk: ContingencyRisk,
  signal?: AbortSignal,
): Promise<ActionApplyResponse> {
  return applyOntologyAction(
    'AdoptDerivedRisk',
    {
      ...riskAnchor(risk),
      riskId: risk.riskId,
      riskName: risk.riskName,
      riskPoint: risk.riskPoint,
      riskType: risk.riskType,
      severity: risk.severity,
      owner: risk.owner,
      mitigationPlan: risk.mitigationPlan,
      impact: risk.impact,
      description: risk.description,
      state: risk.state || '处理中',
    },
    signal,
  );
}

/** 「一键派发」：为派生风险生成一项整改处置任务（GenerateRemediationTask，写回 overlay）。 */
export async function generateRemediationTask(
  risk: ContingencyRisk,
  signal?: AbortSignal,
): Promise<ActionApplyResponse> {
  return applyOntologyAction(
    'GenerateRemediationTask',
    {
      ...riskAnchor(risk),
      title: `处置：${risk.riskName}`,
      owner: risk.owner,
      sourceSummary: risk.mitigationPlan || risk.description || '由派生风险一键派发',
    },
    signal,
  );
}

/** 「驳回」：把派生风险建议驳回留痕（DismissDerivedRisk，写回 overlay，state=已驳回）。
 * AdoptDerivedRisk 的反操作：不纳入跟踪，但持久化一条「已驳回」记录，避免同建议反复出现。 */
export async function dismissDerivedRisk(
  risk: ContingencyRisk,
  reason?: string,
  signal?: AbortSignal,
): Promise<ActionApplyResponse> {
  return applyOntologyAction(
    'DismissDerivedRisk',
    {
      ...riskAnchor(risk),
      riskId: risk.riskId,
      riskName: risk.riskName,
      riskPoint: risk.riskPoint,
      riskType: risk.riskType,
      severity: risk.severity,
      impact: risk.impact,
      description: risk.description,
      dismissReason: reason || `经评估不纳入风险跟踪：${risk.riskName}`,
      dismissedBy: '数字孪生决策台',
    },
    signal,
  );
}

/* =========================================================
   预案章节正文（ChapterNarrative）——LangGraph + LLM 生成 / 人工编辑 / 智能融合 / 版本
   均为 ontology Function（POST /functions/{name}/execute），写回 ChapterNarrative run-record overlay。
   ========================================================= */

/** 章节正文历史项（versions[]）。 */
export interface NarrativeVersionEntry {
  seq: number;
  source: string; // ai | human | merge | restore | milestone
  text: string;
  savedAt?: string;
  by?: string;
  note?: string;
  versionLabel?: string | null;
}

/** 后端 public_view：一章正文的当前快照 + 合并态。 */
export interface ChapterNarrativeView {
  chapterId: string;
  chapterNo?: string;
  chapterTitle?: string;
  status: string; // NarrativeStatus
  displayText: string;
  generatedText?: string;
  editedText?: string;
  pendingGenerated?: string;
  mergeCandidate?: string;
  generatedModel?: string;
  generatedAt?: string;
  editedAt?: string;
  versions?: NarrativeVersionEntry[];
}

export interface GenerateNarrativesResult {
  projectKey: string;
  planId: string;
  degraded: boolean;
  narratives: ChapterNarrativeView[];
}

export interface PlanVersionRow {
  planVersionLogId: string;
  projectKey: string;
  planVersion: string;
  status?: string;
  createdBy?: string;
  createdAt?: string;
  changeDescription?: string;
  [k: string]: unknown;
}

/** 通用 Function 执行入口：POST /functions/{name}/execute，取 result。 */
async function executeOntologyFunction<T>(
  name: string,
  payload: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  const url = `${ONTOLOGY_BASE}/api/v2/ontologies/${ONTOLOGY_ID}/functions/${name}/execute`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`本体服务返回 ${res.status}${detail ? ` · ${detail.slice(0, 200)}` : ''}`);
  }
  const data = (await res.json()) as { result?: T };
  return data.result as T;
}

export interface GenerateNarrativesParams {
  planId?: string;
  projectKey?: string;
  scope?: 'all' | 'chapter';
  chapterId?: string;
  mode?: 'only_empty' | 'regenerate' | 'smart_merge';
  apply?: boolean;
  referenceDate?: string;
}

/** 跑 generateContingencyNarratives 的 LangGraph，逐章生成 / 重生成 / 智能融合。 */
export async function generateContingencyNarratives(
  params: GenerateNarrativesParams = {},
  signal?: AbortSignal,
): Promise<GenerateNarrativesResult> {
  const payload: Record<string, unknown> = {
    project_key: params.projectKey || CONTINGENCY_ANCHOR.projectKey,
  };
  if (params.planId) payload.plan_id = params.planId;
  if (params.scope) payload.scope = params.scope;
  if (params.chapterId) payload.chapter_id = params.chapterId;
  if (params.mode) payload.mode = params.mode;
  if (params.apply != null) payload.apply = params.apply;
  if (params.referenceDate) payload.reference_date = params.referenceDate;
  return executeOntologyFunction<GenerateNarrativesResult>(
    'generateContingencyNarratives',
    payload,
    signal,
  );
}

/** 保存某章人工修改的正文（editChapterNarrative，人工优先、永不被重生成覆盖）。 */
export async function editChapterNarrative(
  chapterId: string,
  text: string,
  opts: { projectKey?: string; editedBy?: string } = {},
  signal?: AbortSignal,
): Promise<ChapterNarrativeView> {
  return executeOntologyFunction<ChapterNarrativeView>(
    'editChapterNarrative',
    {
      project_key: opts.projectKey || CONTINGENCY_ANCHOR.projectKey,
      chapter_id: chapterId,
      text,
      edited_by: opts.editedBy || '数字孪生决策台',
    },
    signal,
  );
}

/** 解决「待合并」：mine 保留人工稿 / new 采纳新稿 / candidate 采纳智能融合稿（acceptChapterMerge）。 */
export async function acceptChapterMerge(
  chapterId: string,
  choice: 'mine' | 'new' | 'candidate',
  opts: { projectKey?: string; editedBy?: string } = {},
  signal?: AbortSignal,
): Promise<ChapterNarrativeView> {
  return executeOntologyFunction<ChapterNarrativeView>(
    'acceptChapterMerge',
    {
      project_key: opts.projectKey || CONTINGENCY_ANCHOR.projectKey,
      chapter_id: chapterId,
      choice,
      edited_by: opts.editedBy || '数字孪生决策台',
    },
    signal,
  );
}

/** 整案版本里程碑：把各章当前正文打快照 + 跨版本 diff 摘要（saveContingencyPlanVersion → PlanVersionLog）。 */
export async function saveContingencyPlanVersion(
  versionLabel: string,
  opts: { projectKey?: string; planId?: string; createdBy?: string; note?: string } = {},
  signal?: AbortSignal,
): Promise<{ version: PlanVersionRow; changeSummary: string; versions: PlanVersionRow[] }> {
  return executeOntologyFunction(
    'saveContingencyPlanVersion',
    {
      project_key: opts.projectKey || CONTINGENCY_ANCHOR.projectKey,
      version_label: versionLabel,
      plan_id: opts.planId || CONTINGENCY_ANCHOR.planId,
      created_by: opts.createdBy || '数字孪生决策台',
      note: opts.note,
    },
    signal,
  );
}

/** 列出整案版本里程碑（listContingencyPlanVersions）。 */
export async function listContingencyPlanVersions(
  projectKey?: string,
  signal?: AbortSignal,
): Promise<PlanVersionRow[]> {
  const r = await executeOntologyFunction<{ versions: PlanVersionRow[] }>(
    'listContingencyPlanVersions',
    { project_key: projectKey || CONTINGENCY_ANCHOR.projectKey },
    signal,
  );
  return r?.versions || [];
}

/** 单章回滚到某历史版本（restoreChapterNarrativeVersion，按 seq 或 versionLabel）。 */
export async function restoreChapterNarrativeVersion(
  chapterId: string,
  opts: { projectKey?: string; seq?: number | string; versionLabel?: string; editedBy?: string },
  signal?: AbortSignal,
): Promise<ChapterNarrativeView> {
  return executeOntologyFunction<ChapterNarrativeView>(
    'restoreChapterNarrativeVersion',
    {
      project_key: opts.projectKey || CONTINGENCY_ANCHOR.projectKey,
      chapter_id: chapterId,
      seq: opts.seq != null ? String(opts.seq) : undefined,
      version_label: opts.versionLabel,
      edited_by: opts.editedBy || '数字孪生决策台',
    },
    signal,
  );
}

/* =========================================================
   预案章节裁剪（ContingencyOutline）——LangGraph + LLM 按项目裁剪/排序章节目录 + 人工固定/排除
   均为 ontology Function（POST /functions/{name}/execute），写回 ContingencyOutline run-record overlay。
   deriveContingencyRisks 只读该 overlay 做过滤/排序，故裁剪后须 reload 重新派生。
   ========================================================= */

/** 后端 public_view：本项目的章节裁剪决策（含人工固定/排除）。 */
export interface ContingencyOutlineView {
  projectKey?: string;
  include: string[];
  order: string[];
  notes: Record<string, string>;
  /** 融合组：组 id → { title, members[], decisionPoint? }。 */
  groups?: Record<string, ContingencyGroup>;
  pinnedInclude: string[];
  pinnedExclude: string[];
  rationale: string;
  status: string; // ai_draft | human_pinned
  generatedModel?: string;
  generatedAt?: string;
  editedAt?: string;
  chapterCount: number;
  versions?: unknown[];
}

export interface AssembleChaptersResult {
  projectKey: string;
  planId: string;
  degraded: boolean;
  outline: ContingencyOutlineView;
}

export interface AssembleChaptersParams {
  planId?: string;
  projectKey?: string;
  mode?: 'only_empty' | 'regenerate';
  referenceDate?: string;
  /** false = 仅返回建议布局、不落库（「AI 建议布局」），由前端预置进拖拽组装器、确认后再 set 落库。 */
  persist?: boolean;
}

/** 跑 assembleContingencyChapters 的 LangGraph：按本项目事实裁剪/排序预案章节目录（或 persist=false 仅建议）。 */
export async function assembleContingencyChapters(
  params: AssembleChaptersParams = {},
  signal?: AbortSignal,
): Promise<AssembleChaptersResult> {
  const payload: Record<string, unknown> = {
    project_key: params.projectKey || CONTINGENCY_ANCHOR.projectKey,
  };
  if (params.planId) payload.plan_id = params.planId;
  if (params.mode) payload.mode = params.mode;
  if (params.referenceDate) payload.reference_date = params.referenceDate;
  if (params.persist != null) payload.persist = params.persist;
  return executeOntologyFunction<AssembleChaptersResult>('assembleContingencyChapters', payload, signal);
}

/** 人工固定某章取舍（include=强制纳入 / exclude=强制裁掉 / auto=撤销固定）；人工优先、重裁不覆盖。 */
export async function pinContingencyChapter(
  chapterId: string,
  action: 'include' | 'exclude' | 'auto',
  opts: { projectKey?: string; editedBy?: string } = {},
  signal?: AbortSignal,
): Promise<ContingencyOutlineView> {
  return executeOntologyFunction<ContingencyOutlineView>(
    'pinContingencyChapter',
    {
      project_key: opts.projectKey || CONTINGENCY_ANCHOR.projectKey,
      chapter_id: chapterId,
      action,
      edited_by: opts.editedBy || '数字孪生决策台',
    },
    signal,
  );
}

/** 一个可拖拽的「本体要素」(= 一章)：对象类型 + schema 派生字段 + 数据/风险数 + 决策点分组。 */
export interface ContingencyElement {
  id: string;
  no: string;
  title: string;
  objectType: string;
  decisionId: string;
  decisionPoint: string;
  decisionLabel: string;
  fields: Array<{ name: string; key?: string; note?: string }>;
  rowCount: number;
  riskCount: number;
  consolidatesRisks: boolean;
  /** 结构章（无 objectType / 汇总风险）：固定纳入，不可拖出、不入托盘。 */
  structural: boolean;
  /** 临时章（doc-ot-<ObjectType>，本体类型库拖入）：骨架由后端按 id 读时现场派生。 */
  adhoc?: boolean;
  /** 本体类型库候选（尚未纳入 outline）：仅出现在 candidates 列表中。 */
  candidate?: boolean;
  /** ObjectType schema 的 description（候选 chip 的悬浮说明）。 */
  desc?: string;
}

/** 融合组：多个章节融合为一章。include/order 里出现组 id（doc-grp-*）即代表其成员被折叠成组章。 */
export interface ContingencyGroup {
  title: string;
  /** 成员的源 chapterId（doc-* / 临时章 doc-ot-*）。 */
  members: string[];
  /** 可选：组章归属子决策点（取首成员），用于分组/锚点继承。 */
  decisionPoint?: string;
  /** 标题来源：'human'=人工改名（AI 融合标题永不覆盖）；缺省/'auto'/'ai' 允许 AI 融合命名。 */
  titleBy?: 'auto' | 'human' | 'ai';
}

export interface ContingencyChapterList {
  elements: ContingencyElement[];
  include: string[];
  /** 本体类型库：全部可成章但未入目录/outline 的业务 ObjectType（按事实行数降序，0 行也可拖入）。 */
  candidates?: ContingencyElement[];
  /** 当前融合组：组 id → { title, members[], decisionPoint? }。供组装器重开时还原嵌套草稿。 */
  groups?: Record<string, ContingencyGroup>;
}

/** 列出全量本体要素（预案章节目录）+ 当前纳入集，供拖拽组装器使用（只读、无 LLM）。 */
export async function listContingencyChapters(
  projectKey?: string,
  signal?: AbortSignal,
): Promise<ContingencyChapterList> {
  return executeOntologyFunction<ContingencyChapterList>(
    'listContingencyChapters',
    { project_key: projectKey || CONTINGENCY_ANCHOR.projectKey },
    signal,
  );
}

/** 确定性地按拖拽结果设定章节集（**保留传入顺序**、清 pin、status=manual）；之后须 reload 重新派生。
 * chapterIds 可含融合组 id（doc-grp-*），其成员由 groups 定义、折叠成一个组章（单段融合正文）。 */
export async function setContingencyChapters(
  chapterIds: string[],
  groups?: Record<string, ContingencyGroup>,
  projectKey?: string,
  signal?: AbortSignal,
): Promise<ContingencyOutlineView> {
  return executeOntologyFunction<ContingencyOutlineView>(
    'setContingencyChapters',
    {
      project_key: projectKey || CONTINGENCY_ANCHOR.projectKey,
      chapter_ids: chapterIds,
      groups: groups || {},
    },
    signal,
  );
}

/** 还原默认章节目录：清空裁剪/拖拽 overlay，章节回到全量本体派生默认。之后须 reload 重新派生。 */
export async function resetContingencyChapters(
  projectKey?: string,
  signal?: AbortSignal,
): Promise<{ projectKey: string; include: string[]; status: string; chapterCount: number }> {
  return executeOntologyFunction(
    'resetContingencyChapters',
    { project_key: projectKey || CONTINGENCY_ANCHOR.projectKey },
    signal,
  );
}
