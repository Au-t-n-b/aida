/**
 * 交付预案 · 数据加载/缓存/筛选/保存（数据中心优先，mock 降级由后端处理）
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
  writeTableSlot,
} from '@/lib/xlsx-io';

const DRAFT_RACI_KEY = 'aida:proposal:raci-draft';
const PLAN_CACHE_KEY = 'aida:proposal:plan-cache:v6';
const ACCEPT_CACHE_KEY = 'aida:proposal:accept-cache:v5';
const TC_UPLOADED_KEY = 'aida:proposal:tc-uploaded';
const TC_CACHE_KEY = 'aida:proposal:tc-cache';
const VERSIONS_KEY = 'aida:proposal:versions';

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

  return { rows: [{ ...EMPTY_RACI }], version: 0 };
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
  if (data === null) {
    return [{ ...EMPTY_PLAN }];
  }

  const rows: PlanActivity[] = data.rows.length ? asPlanActivities(data.rows) : [];
  const result = rows.length ? rows : [{ ...EMPTY_PLAN }];

  if (typeof window !== 'undefined') {
    sessionStorage.setItem(`${PLAN_CACHE_KEY}:${projectName}`, JSON.stringify(result));
  }
  return result;
}

export async function loadAcceptance(ctx: ProjectDataContext): Promise<AcceptanceItem[]> {
  const { projectName } = ctx;
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

  const saved = await safeFetchSlot(ctx, 'acceptance_out');
  if (saved?.rows.length) {
    const rows = asAcceptanceItems(saved.rows);
    if (rows.length && !isPlaceholderAcceptance(rows)) {
      if (typeof window !== 'undefined') {
        sessionStorage.setItem(`${ACCEPT_CACHE_KEY}:${projectName}`, JSON.stringify(rows));
      }
      return rows;
    }
  }

  const data = await safeFetchSlot(ctx, 'acceptance_input');
  if (data === null) {
    return [{ ...EMPTY_ACCEPT }];
  }

  const rows: AcceptanceItem[] = data.rows.length ? asAcceptanceItems(data.rows) : [];
  const result = rows.length ? rows : [{ ...EMPTY_ACCEPT }];

  if (typeof window !== 'undefined') {
    sessionStorage.setItem(`${ACCEPT_CACHE_KEY}:${projectName}`, JSON.stringify(result));
  }
  return result;
}

export async function loadCardScale(ctx: ProjectDataContext): Promise<number> {
  const data = await safeFetchSlot(ctx, 'card_scale');
  return data?.cardScale ?? 384;
}

export function isTestCasesUploaded(projectName: string): boolean {
  if (typeof window === 'undefined') return false;
  return sessionStorage.getItem(`${TC_UPLOADED_KEY}:${projectName}`) === '1';
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
}

export async function loadTestCasesIfReady(
  ctx: ProjectDataContext,
  cardScale: number,
): Promise<LoadedTestCases> {
  const { projectName } = ctx;

  const saved = await safeFetchSlot(ctx, 'testcases_out');
  if (saved?.rows.length) {
    const raw = saved.rows as SavedTestCaseRow[];
    const cases = asTestCases(raw);
    const selectedKeys = new Set<string>();
    cases.forEach((c, i) => {
      const sel = raw[i]?.selected;
      if (sel !== false) selectedKeys.add(testCaseKey(c, i));
    });
    if (typeof window !== 'undefined') {
      sessionStorage.setItem(`${TC_UPLOADED_KEY}:${projectName}`, '1');
      sessionStorage.setItem(`${TC_CACHE_KEY}:${projectName}`, JSON.stringify(cases));
    }
    return { cases, selectedKeys };
  }

  if (!isTestCasesUploaded(projectName)) return { cases: [], selectedKeys: null };

  if (typeof window !== 'undefined') {
    const cached = sessionStorage.getItem(`${TC_CACHE_KEY}:${projectName}`);
    if (cached) {
      try {
        return { cases: JSON.parse(cached) as AcceptanceTestCase[], selectedKeys: null };
      } catch { /* fall through */ }
    }
  }

  const cases = await loadTestCasesFromXlsx(ctx, cardScale);
  if (typeof window !== 'undefined') {
    sessionStorage.setItem(`${TC_CACHE_KEY}:${projectName}`, JSON.stringify(cases));
  }
  return { cases, selectedKeys: null };
}

export function applyTestCasesFromUpload(
  projectName: string,
  rows: unknown[],
  cardScale: number,
): AcceptanceTestCase[] {
  const cases = filterTestCases(asTestCases(rows), cardScale);
  if (typeof window !== 'undefined') {
    sessionStorage.setItem(`${TC_UPLOADED_KEY}:${projectName}`, '1');
    sessionStorage.setItem(`${TC_CACHE_KEY}:${projectName}`, JSON.stringify(cases));
  }
  return cases;
}

export function setAcceptanceCache(projectName: string, items: AcceptanceItem[]): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(`${ACCEPT_CACHE_KEY}:${projectName}`, JSON.stringify(items));
}

export async function saveRaciTable(
  ctx: ProjectDataContext,
  rows: RaciRow[],
  version: number,
): Promise<void> {
  await writeTableSlot(ctx, 'raci_out', 'raci', ctx.projectName, version, rows);
}

export async function saveAcceptanceTable(
  ctx: ProjectDataContext,
  items: AcceptanceItem[],
  version: number,
): Promise<void> {
  await writeTableSlot(ctx, 'acceptance_out', 'acceptance', ctx.projectName, version, items);
}

export async function saveTestCasesTable(
  ctx: ProjectDataContext,
  cases: AcceptanceTestCase[],
  selectedKeys: Set<string>,
  keyOf: (c: AcceptanceTestCase, i: number) => string,
  version: number,
): Promise<void> {
  const rows: SavedTestCaseRow[] = cases.map((c, i) => ({
    ...c,
    selected: selectedKeys.has(keyOf(c, i)),
  }));
  await writeTableSlot(ctx, 'testcases_out', 'testcases', ctx.projectName, version, rows);
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
