/**
 * 交付预案 · 数据加载/缓存/筛选/保存
 * 主写入链路：PUT /api/v1/projects/{id}/proposal/draft（见 proposal-api.ts）
 * 读取兼容：仍可从 slot 适配层拉取历史输出（只读）
 */
import type { ProjectDataContext } from '@/lib/datacenter/types';
import type {
  AcceptanceItem,
  AcceptanceTestCase,
  PlanActivity,
  ProposalTableVersions,
  RaciRow,
  SavedTestCaseRow,
} from '@/types/domain';
import {
  asAcceptanceItems,
  asPlanActivities,
  asRaciRows,
  asTestCases,
  fetchTableSlot,
  parseTestcasesUpload,
} from '@/lib/xlsx-io';

const DRAFT_RACI_KEY = 'aida:proposal:raci-draft';
const PLAN_CACHE_KEY = 'aida:proposal:plan-cache:v6';
const ACCEPT_CACHE_KEY = 'aida:proposal:accept-cache:v5';
const TC_UPLOADED_KEY = 'aida:proposal:tc-uploaded';
const TECH_PROPOSAL_UPLOADED_KEY = 'aida:proposal:tech-proposal-uploaded';
const TC_CACHE_KEY = 'aida:proposal:tc-cache';
const TC_SELECTED_KEY = 'aida:proposal:tc-selected';
const UPLOAD_META_KEY = 'aida:proposal:upload-meta';
const VERSIONS_KEY = 'aida:proposal:versions';
const TC_LOG = '[AIDA TC]';

const EMPTY_RACI: RaciRow = {
  stack: '', cat: '', act: '', gts: '', hw: '', partner: '', customer: '',
};

const EMPTY_PLAN: PlanActivity = {
  name: '', start: '', end: '', actualStart: '', actualEnd: '',
  owner: '', unit: '', status: '', progress: 0, progressTone: 'blue',
};

const EMPTY_ACCEPT: AcceptanceItem = {
  cat: '', scheme: '', standard: '', milestone: '', doc: '', payment: '', paymentMilestone: '',
};

export function getDraftRaci(projectName: string): RaciRow[] | null {
  if (typeof window === 'undefined') return null;
  const raw = sessionStorage.getItem(`${DRAFT_RACI_KEY}:${projectName}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as RaciRow[];
  } catch {
    return null;
  }
}

export function setDraftRaci(projectName: string, rows: RaciRow[]): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(`${DRAFT_RACI_KEY}:${projectName}`, JSON.stringify(rows));
}

export function clearDraftRaci(projectName: string): void {
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem(`${DRAFT_RACI_KEY}:${projectName}`);
}

export function getStoredVersions(projectName: string): ProposalTableVersions {
  if (typeof window === 'undefined') return { raci: 0, acceptance: 0, testCases: 0 };
  const raw = localStorage.getItem(`${VERSIONS_KEY}:${projectName}`);
  if (!raw) return { raci: 0, acceptance: 0, testCases: 0 };
  try {
    return JSON.parse(raw) as ProposalTableVersions;
  } catch {
    return { raci: 0, acceptance: 0, testCases: 0 };
  }
}

export function setStoredVersions(projectName: string, v: ProposalTableVersions): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(`${VERSIONS_KEY}:${projectName}`, JSON.stringify(v));
}

export function extractCaseCardCount(l3: string): number {
  const m = l3.match(/(\d+)\s*节点/);
  if (!m) return 0;
  return parseInt(m[1] ?? '0', 10) * 8;
}

export function filterTestCases(cases: AcceptanceTestCase[], cardScale: number): AcceptanceTestCase[] {
  return cases.filter((c) => {
    const l2 = c.l2 ?? '';
    const isPerf =
      l2.includes('集群集合通信测试') || l2.includes('模型集群训练性能测试');
    if (!isPerf) return true;
    const cards = extractCaseCardCount(c.l3);
    if (cards === 0) return true;
    return cards <= cardScale;
  });
}

async function safeFetchSlot(
  ctx: ProjectDataContext,
  slot: Parameters<typeof fetchTableSlot>[1],
): Promise<{ rows: unknown[]; version: number; cardScale?: number } | null> {
  try {
    const data = await fetchTableSlot(ctx, slot);
    return {
      rows: data.rows ?? [],
      version: data.version ?? 0,
      cardScale: data.cardScale,
    };
  } catch (err) {
    console.error('[AIDA DC] safeFetchSlot failed', {
      slot,
      projectId: ctx.dcProjectId,
      projectName: ctx.projectName,
      hasToken: Boolean(ctx.token),
      error: err instanceof Error ? err.message : String(err),
    });
    return null;
  }
}

function isPlaceholderPlan(rows: PlanActivity[]): boolean {
  return rows.length === 1 && !rows[0]?.name?.trim();
}

function isPlaceholderAcceptance(rows: AcceptanceItem[]): boolean {
  return rows.length === 1 && !rows[0]?.cat?.trim() && !rows[0]?.scheme?.trim();
}

export async function loadRaciMatrix(
  ctx: ProjectDataContext,
): Promise<{ rows: RaciRow[]; version: number }> {
  const { projectName } = ctx;
  const draft = getDraftRaci(projectName);
  if (draft?.length) return { rows: draft, version: getStoredVersions(projectName).raci };

  const saved = await safeFetchSlot(ctx, 'raci_out');
  if (saved?.rows.length) {
    return { rows: asRaciRows(saved.rows), version: saved.version || 1 };
  }

  const template = await safeFetchSlot(ctx, 'raci_template');
  if (template?.rows.length) {
    return { rows: asRaciRows(template.rows), version: 0 };
  }

  return { rows: [], version: 0 };
}

export async function loadPlan(ctx: ProjectDataContext): Promise<PlanActivity[]> {
  const { projectName } = ctx;
  if (typeof window !== 'undefined') {
    const cached = sessionStorage.getItem(`${PLAN_CACHE_KEY}:${projectName}`);
    if (cached) {
      try {
        const parsed = JSON.parse(cached) as PlanActivity[];
        if (parsed.length && !isPlaceholderPlan(parsed)) {
          return parsed;
        }
      } catch { /* fall through */ }
    }
  }

  const data = await safeFetchSlot(ctx, 'plan');
  if (data === null || !data.rows.length) {
    return [];
  }

  const rows: PlanActivity[] = asPlanActivities(data.rows);
  const result = rows.filter((r) => r.name?.trim());

  if (typeof window !== 'undefined' && result.length) {
    sessionStorage.setItem(`${PLAN_CACHE_KEY}:${projectName}`, JSON.stringify(result));
  }
  return result;
}

async function loadAcceptanceFromOut(ctx: ProjectDataContext): Promise<AcceptanceItem[]> {
  const { projectName } = ctx;
  const saved = await safeFetchSlot(ctx, 'acceptance_out');
  if (!saved?.rows.length) return [];

  const rows = asAcceptanceItems(saved.rows).filter(
    (r) => r.cat?.trim() || r.scheme?.trim(),
  );
  if (rows.length && typeof window !== 'undefined') {
    sessionStorage.setItem(`${ACCEPT_CACHE_KEY}:${projectName}`, JSON.stringify(rows));
  }
  return rows;
}

export async function loadAcceptance(ctx: ProjectDataContext): Promise<AcceptanceItem[]> {
  const { projectName } = ctx;
  if (!isTechProposalUploaded(projectName)) {
    return [];
  }

  if (typeof window !== 'undefined') {
    const cached = sessionStorage.getItem(`${ACCEPT_CACHE_KEY}:${projectName}`);
    if (cached) {
      try {
        const parsed = JSON.parse(cached) as AcceptanceItem[];
        if (parsed.length && !isPlaceholderAcceptance(parsed)) {
          return parsed;
        }
      } catch { /* fall through */ }
    }
  }

  return loadAcceptanceFromOut(ctx);
}

export async function reloadAcceptanceFromXlsx(ctx: ProjectDataContext): Promise<AcceptanceItem[]> {
  markTechProposalUploaded(ctx.projectName);
  if (typeof window !== 'undefined') {
    sessionStorage.removeItem(`${ACCEPT_CACHE_KEY}:${ctx.projectName}`);
  }
  return loadAcceptanceFromOut(ctx);
}

export async function loadCardScale(ctx: ProjectDataContext): Promise<number> {
  const data = await safeFetchSlot(ctx, 'card_scale');
  return data?.cardScale ?? 384;
}

export function isTechProposalUploaded(projectName: string): boolean {
  if (typeof window === 'undefined') return false;
  return sessionStorage.getItem(`${TECH_PROPOSAL_UPLOADED_KEY}:${projectName}`) === '1';
}

export function markTechProposalUploaded(projectName: string): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(`${TECH_PROPOSAL_UPLOADED_KEY}:${projectName}`, '1');
}

export function isTestCasesUploaded(projectName: string): boolean {
  if (typeof window === 'undefined') return false;
  return sessionStorage.getItem(`${TC_UPLOADED_KEY}:${projectName}`) === '1';
}

export function markTestCasesUploaded(projectName: string): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(`${TC_UPLOADED_KEY}:${projectName}`, '1');
}

export function getUploadMeta(projectName: string): Record<string, string> {
  if (typeof window === 'undefined' || !projectName) return {};
  const raw = sessionStorage.getItem(`${UPLOAD_META_KEY}:${projectName}`);
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, string>;
  } catch {
    return {};
  }
}

export function setUploadMetaDoc(projectName: string, docKey: string, sizeLabel: string): void {
  if (typeof window === 'undefined' || !projectName) return;
  const prev = getUploadMeta(projectName);
  sessionStorage.setItem(
    `${UPLOAD_META_KEY}:${projectName}`,
    JSON.stringify({ ...prev, [docKey]: sizeLabel }),
  );
}

function getTcSelectedCache(projectName: string): Set<string> | null {
  if (typeof window === 'undefined') return null;
  const raw = sessionStorage.getItem(`${TC_SELECTED_KEY}:${projectName}`);
  if (!raw) return null;
  try {
    return new Set(JSON.parse(raw) as string[]);
  } catch {
    return null;
  }
}

export function setTestCasesSessionCache(
  projectName: string,
  cases: AcceptanceTestCase[],
  selectedKeys: Set<string>,
): void {
  if (typeof window === 'undefined' || !projectName) return;
  sessionStorage.setItem(`${TC_CACHE_KEY}:${projectName}`, JSON.stringify(cases));
  sessionStorage.setItem(`${TC_SELECTED_KEY}:${projectName}`, JSON.stringify([...selectedKeys]));
}

function clearTestCasesSessionCache(projectName: string): void {
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem(`${TC_CACHE_KEY}:${projectName}`);
  sessionStorage.removeItem(`${TC_SELECTED_KEY}:${projectName}`);
}

export function testCaseKey(c: AcceptanceTestCase, i: number): string {
  return `tc-${c.id}-${i}`;
}

async function loadTestCasesFromXlsx(
  ctx: ProjectDataContext,
  cardScale: number,
): Promise<AcceptanceTestCase[]> {
  const data = await safeFetchSlot(ctx, 'testcases_template');
  if (!data?.rows.length) return [];
  return filterTestCases(asTestCases(data.rows), cardScale);
}

export interface LoadedTestCases {
  cases: AcceptanceTestCase[];
  selectedKeys: Set<string> | null;
  source?: 'cache' | 'testcases_out' | 'testcases_template' | 'gate' | 'none';
}

function parseTcSelected(v: unknown): boolean {
  if (v === false || v === '否' || v === '0' || v === 'false') return false;
  return true;
}

function buildSelectedKeys(raw: SavedTestCaseRow[], cases: AcceptanceTestCase[]): Set<string> {
  const rawById = new Map<string, SavedTestCaseRow>();
  for (const r of raw) {
    const id = String((r as unknown as Record<string, unknown>).id ?? '').trim();
    if (id) rawById.set(id, r);
  }
  const selectedKeys = new Set<string>();
  cases.forEach((c, i) => {
    const src = rawById.get(c.id);
    const sel = src ? (src as unknown as Record<string, unknown>).selected : undefined;
    if (parseTcSelected(sel)) selectedKeys.add(testCaseKey(c, i));
  });
  return selectedKeys;
}

export async function loadTestCasesIfReady(
  ctx: ProjectDataContext,
  cardScale: number,
): Promise<LoadedTestCases> {
  const { projectName } = ctx;

  if (!isTestCasesUploaded(projectName)) {
    console.info(`${TC_LOG} load skipped: upload gate (等待 Claw 假装解析完成)`, { projectName });
    return { cases: [], selectedKeys: null, source: 'gate' };
  }

  console.info(`${TC_LOG} load start`, { projectName, cardScale });

  // 优先 session 缓存（用户编辑后的权威数据源）
  if (typeof window !== 'undefined') {
    const cached = sessionStorage.getItem(`${TC_CACHE_KEY}:${projectName}`);
    if (cached) {
      try {
        const cases = JSON.parse(cached) as AcceptanceTestCase[];
        if (cases.length) {
          const selectedKeys =
            getTcSelectedCache(projectName) ?? new Set(cases.map((c, i) => testCaseKey(c, i)));
          console.info(`${TC_LOG} load ok from session cache`, { caseCount: cases.length });
          return { cases, selectedKeys, source: 'cache' };
        }
      } catch {
        console.warn(`${TC_LOG} session cache parse failed, falling through to xlsx`);
      }
    }
  }

  return loadTestCasesFromExcel(ctx, cardScale);
}

/** 从落盘 xlsx（输出结果）或模板读取，并写入 session 缓存 */
export async function loadTestCasesFromExcel(
  ctx: ProjectDataContext,
  cardScale: number,
): Promise<LoadedTestCases> {
  const { projectName } = ctx;

  const saved = await safeFetchSlot(ctx, 'testcases_out');
  if (saved?.rows.length) {
    const raw = saved.rows as SavedTestCaseRow[];
    const allCases = asTestCases(raw);
    const cases = filterTestCases(allCases, cardScale);
    const selectedKeys = buildSelectedKeys(raw, cases);
    console.info(`${TC_LOG} load from testcases_out`, {
      rawRows: raw.length,
      parsedRows: allCases.length,
      afterFilter: cases.length,
      version: saved.version,
    });
    if (typeof window !== 'undefined' && cases.length) {
      setTestCasesSessionCache(projectName, cases, selectedKeys);
    }
    return { cases, selectedKeys, source: 'testcases_out' };
  }

  console.info(`${TC_LOG} testcases_out empty or missing, try template`);

  const template = await safeFetchSlot(ctx, 'testcases_template');
  if (template?.rows.length) {
    const raw = template.rows as SavedTestCaseRow[];
    const allCases = asTestCases(raw);
    const cases = filterTestCases(allCases, cardScale);
    const selectedKeys = new Set(cases.map((c, i) => testCaseKey(c, i)));
    console.info(`${TC_LOG} load from testcases_template`, {
      rawRows: raw.length,
      parsedRows: allCases.length,
      afterFilter: cases.length,
    });
    if (typeof window !== 'undefined' && cases.length) {
      setTestCasesSessionCache(projectName, cases, selectedKeys);
    }
    return { cases, selectedKeys, source: 'testcases_template' };
  }

  console.warn(`${TC_LOG} load failed: no rows from out or template`, { projectName });
  return { cases: [], selectedKeys: null, source: 'none' };
}

export async function reloadTestCasesFromXlsx(
  ctx: ProjectDataContext,
  cardScale: number,
): Promise<LoadedTestCases> {
  console.info(`${TC_LOG} reload after fake parse`, {
    projectName: ctx.projectName,
    projectId: ctx.dcProjectId,
    cardScale,
  });
  markTestCasesUploaded(ctx.projectName);
  if (typeof window !== 'undefined') {
    clearTestCasesSessionCache(ctx.projectName);
  }
  const loaded = await loadTestCasesFromExcel(ctx, cardScale);
  if (loaded.cases.length) {
    console.info(`${TC_LOG} reload success`, {
      source: loaded.source,
      caseCount: loaded.cases.length,
    });
  } else {
    console.warn(`${TC_LOG} reload got 0 cases`, {
      source: loaded.source,
      hint: '检查 mock 目录下 输出结果/测试用例.xlsx 或 输入文件/测试用例/测试用例模板.xlsx',
    });
  }
  return loaded;
}

/** 上传场景测试用例 docx：解析 + 模板合并 + 卡规模筛选 → 写入输出结果/测试用例.xlsx */
export async function parseAndSaveScenarioTestCases(
  ctx: ProjectDataContext,
  file: File,
): Promise<LoadedTestCases> {
  if (typeof window !== 'undefined') {
    clearTestCasesSessionCache(ctx.projectName);
  }
  const cardScale = await loadCardScale(ctx);
  const { rows } = await parseTestcasesUpload(file, ctx);
  const cases = applyTestCasesFromUpload(ctx.projectName, rows, cardScale);
  const selectedKeys = new Set(cases.map((c, i) => testCaseKey(c, i)));
  const ver = Math.max(getStoredVersions(ctx.projectName).testCases, 1);
  await saveTestCasesTable(ctx, cases, selectedKeys, testCaseKey, ver);
  return { cases, selectedKeys };
}

export function applyTestCasesFromUpload(
  projectName: string,
  rows: unknown[],
  cardScale: number,
): AcceptanceTestCase[] {
  const cases = filterTestCases(asTestCases(rows), cardScale);
  if (typeof window !== 'undefined') {
    sessionStorage.setItem(`${TC_UPLOADED_KEY}:${projectName}`, '1');
    const selectedKeys = new Set(cases.map((c, i) => testCaseKey(c, i)));
    setTestCasesSessionCache(projectName, cases, selectedKeys);
  }
  return cases;
}

export function setAcceptanceCache(projectName: string, items: AcceptanceItem[]): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(`${ACCEPT_CACHE_KEY}:${projectName}`, JSON.stringify(items));
}

export async function saveRaciTable(
  _ctx: ProjectDataContext,
  _rows: RaciRow[],
  version: number,
): Promise<void> {
  /** @deprecated 写入请走 proposal-screen → saveDraft；此处仅更新本地版本号 */
  setStoredVersions(_ctx.projectName, {
    ...getStoredVersions(_ctx.projectName),
    raci: version,
  });
}

export async function saveAcceptanceTable(
  ctx: ProjectDataContext,
  items: AcceptanceItem[],
  version: number,
): Promise<void> {
  setAcceptanceCache(ctx.projectName, items);
  setStoredVersions(ctx.projectName, {
    ...getStoredVersions(ctx.projectName),
    acceptance: version,
  });
}

export async function saveTestCasesTable(
  ctx: ProjectDataContext,
  cases: AcceptanceTestCase[],
  selectedKeys: Set<string>,
  keyOf: (c: AcceptanceTestCase, i: number) => string,
  version: number,
): Promise<void> {
  setTestCasesSessionCache(ctx.projectName, cases, selectedKeys);
  setStoredVersions(ctx.projectName, {
    ...getStoredVersions(ctx.projectName),
    testCases: version,
  });
  void keyOf;
}

export function buildProjectDataContext(params: {
  token?: string;
  dcProjectId: string;
  projectName: string;
  projectCode?: string;
}): ProjectDataContext {
  return {
    token: params.token,
    dcProjectId: params.dcProjectId,
    projectName: params.projectName,
    projectCode: params.projectCode,
  };
}
