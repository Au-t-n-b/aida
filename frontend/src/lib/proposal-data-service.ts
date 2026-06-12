/**
 * 交付预案 · 数据加载/缓存/筛选/保存
 */
import {
  DEFAULT_PROJECT_NAME,
  ProposalMockPaths,
} from '@/data/project-paths';
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
  fetchMockFile,
  writeMockFile,
} from '@/lib/xlsx-io';

const DRAFT_RACI_KEY = 'aida:proposal:raci-draft';
/** v4：计划表改读 mock数据/项目管理/计划/项目计划进度表.xlsx */
const PLAN_CACHE_KEY = 'aida:proposal:plan-cache:v4';
const ACCEPT_CACHE_KEY = 'aida:proposal:accept-cache:v3';
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

/** 从用例名称提取节点数 → 卡数（节点 × 8） */
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

async function safeFetch(path: string): Promise<{ rows: unknown[]; version: number; cardScale?: number } | null> {
  try {
    const data = await fetchMockFile(path);
    return { rows: data.rows ?? [], version: data.version ?? 0, cardScale: data.cardScale };
  } catch {
    return null;
  }
}

function isPlaceholderPlan(rows: PlanActivity[]): boolean {
  return rows.length === 1 && !rows[0]?.name?.trim();
}

function isPlaceholderAcceptance(rows: AcceptanceItem[]): boolean {
  return rows.length === 1 && !rows[0]?.cat?.trim() && !rows[0]?.scheme?.trim();
}

export async function loadRaciMatrix(projectName: string): Promise<{ rows: RaciRow[]; version: number }> {
  const draft = getDraftRaci(projectName);
  if (draft?.length) return { rows: draft, version: getStoredVersions(projectName).raci };

  const saved = await safeFetch(ProposalMockPaths.raciOut);
  if (saved?.rows.length) {
    return { rows: asRaciRows(saved.rows), version: saved.version || 1 };
  }

  const template = await safeFetch(ProposalMockPaths.raciTemplate);
  if (template?.rows.length) {
    return { rows: asRaciRows(template.rows), version: 0 };
  }

  return { rows: [{ ...EMPTY_RACI }], version: 0 };
}

export async function loadPlan(projectName: string): Promise<PlanActivity[]> {
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

  const data = await safeFetch(ProposalMockPaths.planSchedule);
  if (data === null) {
    // Agent 未就绪或网络失败：不缓存，便于同会话内 Agent 启动后刷新页面即可加载
    return [{ ...EMPTY_PLAN }];
  }

  const rows: PlanActivity[] = data.rows.length ? asPlanActivities(data.rows) : [];
  const result = rows.length ? rows : [{ ...EMPTY_PLAN }];

  if (typeof window !== 'undefined') {
    sessionStorage.setItem(`${PLAN_CACHE_KEY}:${projectName}`, JSON.stringify(result));
  }
  return result;
}

export async function loadAcceptance(projectName: string): Promise<AcceptanceItem[]> {
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

  // 0610 SSOT：首次从输入文件技术建议书.docx 解析；无文件/无结果时不回退静态 mock
  const data = await safeFetch(ProposalMockPaths.techProposalIn);
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

export async function loadCardScale(): Promise<number> {
  const data = await safeFetch(ProposalMockPaths.simulationDeviceMd);
  return data?.cardScale ?? 384;
}

export function isTestCasesUploaded(projectName: string): boolean {
  if (typeof window === 'undefined') return false;
  return sessionStorage.getItem(`${TC_UPLOADED_KEY}:${projectName}`) === '1';
}

async function loadTestCasesFromXlsx(cardScale: number): Promise<AcceptanceTestCase[]> {
  const data = await safeFetch(ProposalMockPaths.testCasesIn);
  if (!data?.rows.length) return [];
  return filterTestCases(asTestCases(data.rows), cardScale);
}

/** 未上传场景测试用例时返回空数组；已上传则读缓存或 xlsx 默认条目并筛选 */
export async function loadTestCasesIfReady(
  projectName: string,
  cardScale: number,
): Promise<AcceptanceTestCase[]> {
  if (!isTestCasesUploaded(projectName)) return [];

  if (typeof window !== 'undefined') {
    const cached = sessionStorage.getItem(`${TC_CACHE_KEY}:${projectName}`);
    if (cached) {
      try {
        return JSON.parse(cached) as AcceptanceTestCase[];
      } catch { /* fall through */ }
    }
  }

  const cases = await loadTestCasesFromXlsx(cardScale);
  if (typeof window !== 'undefined') {
    sessionStorage.setItem(`${TC_CACHE_KEY}:${projectName}`, JSON.stringify(cases));
  }
  return cases;
}

/** 上传解析成功后：筛选、写缓存、标记已上传 */
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
  projectName: string,
  rows: RaciRow[],
  version: number,
): Promise<void> {
  await writeMockFile({
    logicalPath: ProposalMockPaths.raciOut,
    kind: 'raci',
    projectName,
    version,
    rows,
  });
}

export async function saveAcceptanceTable(
  projectName: string,
  items: AcceptanceItem[],
  version: number,
): Promise<void> {
  await writeMockFile({
    logicalPath: ProposalMockPaths.acceptanceOut,
    kind: 'acceptance',
    projectName,
    version,
    rows: items,
  });
}

export async function saveTestCasesTable(
  projectName: string,
  cases: AcceptanceTestCase[],
  selectedKeys: Set<string>,
  keyOf: (c: AcceptanceTestCase, i: number) => string,
  version: number,
): Promise<void> {
  const rows: SavedTestCaseRow[] = cases.map((c, i) => ({
    ...c,
    selected: selectedKeys.has(keyOf(c, i)),
  }));
  await writeMockFile({
    logicalPath: ProposalMockPaths.testCasesOut,
    kind: 'testcases',
    projectName,
    version,
    rows,
  });
}

export const PROPOSAL_PROJECT_NAME = DEFAULT_PROJECT_NAME;
