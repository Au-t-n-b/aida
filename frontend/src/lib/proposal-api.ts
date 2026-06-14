/**
 * 交付预案 API
 * Base: /api/v1/projects/{projectId}/proposal
 */
import { useMemo } from 'react';
import { useAidaSession } from '@/lib/aida-session';

const DEFAULT_PROJECT_ID = '56A0TXN';

const PROPOSAL_API_BASE =
  (
    (import.meta.env.VITE_PROPOSAL_API_BASE as string | undefined)
    || (import.meta.env.VITE_AGENT_BASE as string | undefined)
  )?.replace(/\/$/, '') ?? '';

export type DeliveryChannel = '华为' | '客户';
export type DataSource = '自动解析' | '人工录入';
export type ProposalVersionStatus = 'draft' | 'published';
export type ProductPartCategory = '产品' | '部件';
export type HardwareSubtype =
  | '主设备'
  | '板卡·线卡·主控'
  | '网卡·CPU 等部件'
  | '光模块'
  | '电源·风机·硬盘';

export interface DeviceInfoRow {
  rowId: string;
  deviceModel: string;
  productCode: string;
  quantity: number;
  version: string;
  lifecycleStatus: string;
  gaActualDate?: string | null;
  gaPlanDate?: string | null;
  eomActualDate?: string | null;
  eomPlanDate?: string | null;
  eosActualDate?: string | null;
  eosPlanDate?: string | null;
  deviceUHeight?: number | null;
  dataSource: DataSource;
  proposalVersion?: string | null;
  productPartCategory: ProductPartCategory;
  partCode: string;
  hardwareSubtype: HardwareSubtype;
  deviceRole: string;
  sourceFile?: string | null;
}

export interface ServiceDeliveryUiRow {
  rowId: string;
  serviceMajor: string;
  serviceItem: string;
  deliveryChannel: DeliveryChannel;
  dataSource: DataSource;
  proposalVersion?: string | null;
}

export type RowLevel = 'L1' | 'L2';

export interface ServiceContentRow {
  rowId: string;
  serviceName: string;
  serviceContent: string;
  quantity: number;
  unit: string;
  rowLevel: RowLevel;
  parentRowId?: string | null;
  dataSource: DataSource;
  proposalVersion?: string | null;
}

export interface MaintenanceStrategyRow {
  rowId: string;
  seq: number;
  productModel: string;
  warrantyPolicy: string;
  maintenancePolicy: string;
  maintYears?: number | null;
  maintTypeCode?: string | null;
  maintStartDate: string;
  maintEndDate: string;
  productEosDate?: string | null;
  overEos: '是' | '否';
  overEosApproval: string;
  dataSource: DataSource;
  proposalVersion?: string | null;
}

export interface MaintenanceSlaRow {
  rowId: string;
  seq?: string;
  severityLevel: string;
  coveragePeriod: string;
  responseTime: string;
  restoreTime: string;
  resolveTime: string;
  serviceItem?: string | null;
  dataSource: DataSource;
  proposalVersion?: string | null;
}

export interface MaintenanceSlaResponse {
  hardwareSupport: string;
  serviceLevel: string;
  rows: MaintenanceSlaRow[];
  meta?: { hint?: string };
}

/** @deprecated 累计修改记录改由 cumulative-change-log API 提供 */
export interface ChangeRecord {
  seq: number;
  chapter: string;
  description: string;
}

export interface VersionInfoMetadata {
  projectId?: string;
  projectName?: string;
  proposalVersion?: string;
  createdBy?: string | null;
  createdAt?: string | null;
  updatedBy?: string | null;
  updatedAt?: string | null;
  changeDescription?: string;
  documentSummary?: string;
}

export interface CumulativeChangeEntry {
  seq: number;
  /** 发布快照拼接用；手工行用 chapter */
  proposalVersion?: string;
  chapter?: string;
  changeDescription: string;
  editable?: boolean;
  source?: 'snapshot' | 'manual';
}

export interface DraftManifest extends ManifestActivity {
  projectId?: string;
  baseProposalVersion?: string | null;
  workingVersionLabel?: string;
  status?: ProposalVersionStatus;
  dirty?: boolean;
  etag?: string;
  /** 旧版后端草稿修改记录（新 API 用 cumulativeChangeLog） */
  changeRecords?: ChangeRecord[];
  /** 已发布版本号列表（时间升序），用于按版本截止展示修改记录 */
  publishedVersions?: string[];
}

export interface DraftPayload {
  manifest: DraftManifest;
  metadata?: VersionInfoMetadata;
  metadataDependencies?: { code: string; message: string }[];
  cumulativeChangeLog?: CumulativeChangeEntry[];
  chapters?: Record<string, unknown>;
}

export interface ProposalVersionItem {
  proposalVersion: string;
  status: ProposalVersionStatus;
  label: string;
  tone: 'green' | 'amber';
  baseProposalVersion?: string | null;
  createdBy?: string | null;
  createdAt?: string | null;
  updatedBy?: string | null;
  updatedAt?: string | null;
  isLatest?: boolean;
  isEditable?: boolean;
  dirty?: boolean;
}

export interface SaveDraftResult extends ManifestActivity {
  status: string;
  baseProposalVersion?: string | null;
  workingVersionLabel?: string;
  dirty: boolean;
  etag?: string;
}

export interface ReleaseProgressItem {
  role: 'user' | 'ai';
  body: string;
  chips?: string[];
  actions?: { label: string; kind: string; icon?: string }[];
}

export interface ReleaseAndDecideResult {
  proposalVersion: string;
  status: string;
  createdBy?: string;
  updatedBy?: string;
  updatedAt?: string;
  decisionEvalJobId?: string;
  sideEffects?: {
    tasksCreated?: number;
    risksCreated?: number;
    integrationRequirementsCreated?: number;
    documentsArchived?: string[];
  };
  progress?: ReleaseProgressItem[];
}

export interface ManifestActivity {
  createdBy?: string | null;
  createdAt?: string | null;
  updatedBy?: string | null;
  updatedAt?: string | null;
  /** 章节 PATCH 后 manifest 乐观锁 token，保存草稿时需同步 */
  etag?: string | null;
}

interface ApiEnvelope<T> {
  data: T;
  meta?: {
    projectId?: string;
    proposalVersion?: string;
    sourceLayer?: string;
    manifestActivity?: ManifestActivity;
  };
}

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

export class ProposalApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ProposalApiError';
    this.status = status;
    this.code = code;
  }
}

export function mapProposalRole(role: string | undefined): string {
  if (role === 'td' || role === 'pd' || role === 'admin') return role === 'admin' ? 'td' : role;
  return 'td';
}

export function getDefaultProjectId(): string {
  return DEFAULT_PROJECT_ID;
}

function normalizeLegacyPublishedUpdatedAt(meta: VersionInfoMetadata): VersionInfoMetadata {
  const version = meta.proposalVersion;
  const updatedAt = meta.updatedAt;
  if (!version || version === 'draft' || version === '草稿' || !updatedAt) return meta;
  if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(updatedAt)) return meta;

  const ts = version.match(/_(\d{14})(?:_|$)/)?.[1];
  if (!ts) return meta;
  const releaseAt = new Date(
    Number(ts.slice(0, 4)),
    Number(ts.slice(4, 6)) - 1,
    Number(ts.slice(6, 8)),
    Number(ts.slice(8, 10)),
    Number(ts.slice(10, 12)),
    Number(ts.slice(12, 14)),
    0,
  );
  const currAt = new Date(
    Number(updatedAt.slice(0, 4)),
    Number(updatedAt.slice(5, 7)) - 1,
    Number(updatedAt.slice(8, 10)),
    Number(updatedAt.slice(11, 13)),
    Number(updatedAt.slice(14, 16)),
    0,
  );
  if (Number.isNaN(releaseAt.getTime()) || Number.isNaN(currAt.getTime())) return meta;

  const diffMs = releaseAt.getTime() - currAt.getTime();
  const eightHours = 8 * 60 * 60 * 1000;
  const tolerance = 20 * 60 * 1000;
  if (Math.abs(diffMs - eightHours) > tolerance) return meta;

  const fixed = new Date(currAt.getTime() + eightHours);
  const pad = (n: number) => String(n).padStart(2, '0');
  return {
    ...meta,
    updatedAt: `${fixed.getFullYear()}-${pad(fixed.getMonth() + 1)}-${pad(fixed.getDate())} ${pad(fixed.getHours())}:${pad(fixed.getMinutes())}`,
  };
}

/** 页头创建/修改时间展示；兼容 ISO 与已格式化的 `yyyy-MM-dd HH:mm` */
/** 兼容新版 metadata 字段与旧版 manifest / 扁平 version snapshot */
export function resolveVersionInfoMetadata(
  source: Record<string, unknown> | DraftPayload | null | undefined,
  fallback: VersionInfoMetadata,
  versionItem?: ProposalVersionItem | null,
): VersionInfoMetadata {
  const normalize = (meta: VersionInfoMetadata): VersionInfoMetadata =>
    normalizeLegacyPublishedUpdatedAt(meta);

  const withDefined = (
    base: VersionInfoMetadata,
    patch: Partial<VersionInfoMetadata>,
  ): VersionInfoMetadata => {
    const next = { ...base };
    (Object.keys(patch) as Array<keyof VersionInfoMetadata>).forEach((key) => {
      const value = patch[key];
      if (value !== undefined) {
        next[key] = value as never;
      }
    });
    return next;
  };

  if (!source) {
    return normalize(versionItem
      ? {
          ...fallback,
          createdBy: versionItem.createdBy ?? fallback.createdBy,
          createdAt: versionItem.createdAt ?? fallback.createdAt,
          updatedBy: versionItem.updatedBy ?? fallback.updatedBy,
          updatedAt: versionItem.updatedAt ?? fallback.updatedAt,
          proposalVersion:
            versionItem.proposalVersion === 'draft'
              ? '草稿'
              : versionItem.proposalVersion,
        }
      : fallback);
  }

  const rec = source as Record<string, unknown>;
  const meta = rec.metadata as VersionInfoMetadata | undefined;
  const manifest = rec.manifest as DraftManifest | undefined;

  if (
    meta &&
    (meta.createdBy || meta.createdAt || meta.updatedBy || meta.updatedAt)
  ) {
    return normalize(withDefined(
      withDefined(fallback, meta),
      versionItem
        ? {
            createdBy: meta.createdBy ?? versionItem.createdBy ?? fallback.createdBy,
            createdAt: meta.createdAt ?? versionItem.createdAt ?? fallback.createdAt,
            updatedBy: meta.updatedBy ?? versionItem.updatedBy ?? fallback.updatedBy,
            updatedAt: meta.updatedAt ?? versionItem.updatedAt ?? fallback.updatedAt,
            proposalVersion:
              meta.proposalVersion ??
              (versionItem.proposalVersion === 'draft'
                ? '草稿'
                : versionItem.proposalVersion),
          }
        : {},
    ));
  }

  if (
    manifest &&
    (manifest.createdBy || manifest.createdAt || manifest.updatedBy || manifest.updatedAt)
  ) {
    const resolved = withDefined(
      withDefined(fallback, meta ?? {}),
      {
        projectId: manifest.projectId ?? meta?.projectId,
        proposalVersion:
          meta?.proposalVersion ??
          (manifest.workingVersionLabel === '草稿' ? '草稿' : manifest.workingVersionLabel) ??
          fallback.proposalVersion,
        // 创建字段优先保留 metadata，manifest 仅兜底
        createdBy: meta?.createdBy ?? manifest.createdBy ?? fallback.createdBy,
        createdAt: meta?.createdAt ?? manifest.createdAt ?? fallback.createdAt,
        updatedBy: manifest.updatedBy ?? meta?.updatedBy ?? fallback.updatedBy,
        updatedAt: manifest.updatedAt ?? meta?.updatedAt ?? fallback.updatedAt,
      },
    );
    return normalize(resolved);
  }

  if (rec.createdBy || rec.createdAt || rec.updatedBy || rec.updatedAt) {
    return normalize(withDefined(
      withDefined(fallback, meta ?? {}),
      {
        projectId: (rec.projectId as string) ?? meta?.projectId,
        projectName: (rec.projectName as string) ?? meta?.projectName,
        proposalVersion:
          (rec.proposalVersion as string) ??
          meta?.proposalVersion ??
          fallback.proposalVersion,
        createdBy:
          meta?.createdBy ??
          ((rec.createdBy as string | null | undefined) ?? fallback.createdBy),
        createdAt:
          meta?.createdAt ??
          ((rec.createdAt as string | null | undefined) ?? fallback.createdAt),
        updatedBy:
          (rec.updatedBy as string | null | undefined) ??
          meta?.updatedBy ??
          fallback.updatedBy,
        updatedAt:
          (rec.updatedAt as string | null | undefined) ??
          meta?.updatedAt ??
          fallback.updatedAt,
      },
    ));
  }

  if (versionItem) {
    return normalize({
      ...fallback,
      ...meta,
      createdBy: versionItem.createdBy ?? meta?.createdBy ?? fallback.createdBy,
      createdAt: versionItem.createdAt ?? meta?.createdAt ?? fallback.createdAt,
      updatedBy: versionItem.updatedBy ?? meta?.updatedBy ?? fallback.updatedBy,
      updatedAt: versionItem.updatedAt ?? meta?.updatedAt ?? fallback.updatedAt,
      proposalVersion:
        versionItem.proposalVersion === 'draft'
          ? '草稿'
          : versionItem.proposalVersion,
    });
  }

  return normalize(meta ? { ...fallback, ...meta } : fallback);
}

export function legacyChangeRecordsToCumulative(
  records: ChangeRecord[] | undefined,
  source: 'manual' | 'snapshot' = 'manual',
): CumulativeChangeEntry[] {
  if (!records?.length) return [];
  return records.map((r, i) => ({
    seq: r.seq ?? i + 1,
    chapter: r.chapter,
    changeDescription: r.description,
    editable: source === 'manual',
    source,
  }));
}

export function manualLogToChangeRecords(
  entries: CumulativeChangeEntry[] | undefined,
): ChangeRecord[] {
  if (!entries?.length) return [];
  return entries
    .filter((e) => (e.chapter || '').trim() || (e.changeDescription || '').trim())
    .map((e, i) => ({
      seq: e.seq ?? i + 1,
      chapter: (e.chapter || '').trim(),
      description: e.changeDescription || '',
    }));
}

function expandChangeDescriptionText(
  text: string,
  startSeq: number,
): { entries: CumulativeChangeEntry[]; nextSeq: number } {
  const entries: CumulativeChangeEntry[] = [];
  let seq = startSeq;
  const trimmed = text.trim();
  if (!trimmed || trimmed === '—') return { entries, nextSeq: seq };

  const parts = trimmed.split('；').map((p) => p.trim()).filter(Boolean);
  for (const part of parts.length ? parts : [trimmed]) {
    const colon = part.indexOf('：');
    seq += 1;
    if (colon >= 0) {
      entries.push({
        seq,
        chapter: part.slice(0, colon).trim(),
        changeDescription: part.slice(colon + 1).trim(),
        editable: false,
        source: 'snapshot',
      });
    } else {
      entries.push({
        seq,
        chapter: part,
        changeDescription: '',
        editable: false,
        source: 'snapshot',
      });
    }
  }
  return { entries, nextSeq: seq };
}

function snapshotToCumulativeEntries(
  snap: Record<string, unknown>,
  startSeq: number,
): { entries: CumulativeChangeEntry[]; nextSeq: number } {
  const records = snap.changeRecords as ChangeRecord[] | undefined;
  if (Array.isArray(records) && records.length > 0) {
    const entries = legacyChangeRecordsToCumulative(records, 'snapshot').map((e, i) => ({
      ...e,
      // 保留发布时写入的累计序号；无 seq 时再按当前拼接位置递增
      seq: e.seq ?? startSeq + i + 1,
    }));
    const nextSeq = entries.reduce((max, e) => Math.max(max, e.seq ?? 0), startSeq);
    return { entries, nextSeq };
  }
  // 不再把快照 changeDescription（章节 diff 自动生成）展开为修改记录行
  return { entries: [], nextSeq: startSeq };
}

async function loadSnapshotsChangeLog(
  projectId: string,
  headers: HeadersInit,
  versionIds: string[],
): Promise<CumulativeChangeEntry[]> {
  const entries: CumulativeChangeEntry[] = [];
  let seq = 0;
  for (const ver of versionIds) {
    const snap = await fetchVersionSnapshot(projectId, ver, headers);
    const part = snapshotToCumulativeEntries(snap as Record<string, unknown>, seq);
    entries.push(...part.entries);
    seq = part.nextSeq;
  }
  return entries;
}

/** 按版本后缀时间戳升序（V1.10 在 V1.9 之后，而非字符串 V1.1 之前） */
function sortPublishedVersionsChronologically(versionIds: string[]): string[] {
  const ts = (id: string) => id.match(/_(\d{14})$/)?.[1] ?? id;
  return [...versionIds].sort((a, b) => ts(a).localeCompare(ts(b)));
}

async function resolvePublishedVersionOrder(
  projectId: string,
  headers: HeadersInit,
  draftData?: DraftPayload | null,
): Promise<string[]> {
  const fromManifest = draftData?.manifest?.publishedVersions;
  if (fromManifest && fromManifest.length > 0) {
    return [...fromManifest];
  }
  const versions = await fetchVersions(projectId, headers);
  const ordered = sortPublishedVersionsChronologically(
    versions
      .filter((v) => v.proposalVersion !== 'draft')
      .map((v) => v.proposalVersion),
  );
  return ordered;
}

/**
 * 草稿态：各版本手工 changeRecords + 当前草稿可编辑行（不含章节 diff 自动生成）。
 */
export async function loadChangeLogForDraft(
  projectId: string,
  headers: HeadersInit,
  draftData?: DraftPayload | null,
): Promise<CumulativeChangeEntry[]> {
  // get_draft 已带 cumulativeChangeLog，优先用内嵌数据，避免再卡 cumulative-change-log 接口
  if (draftData?.cumulativeChangeLog && draftData.cumulativeChangeLog.length > 0) {
    return draftData.cumulativeChangeLog;
  }

  try {
    const fromApi = await fetchCumulativeChangeLog(projectId, headers);
    if (fromApi.length > 0) {
      return fromApi;
    }
  } catch {
    /* 旧后端无此路由 */
  }

  try {
    const ordered = await resolvePublishedVersionOrder(projectId, headers, draftData);
    const snapshotEntries = await loadSnapshotsChangeLog(projectId, headers, ordered);
    const manual = legacyChangeRecordsToCumulative(draftData?.manifest?.changeRecords, 'manual');
    let seq = snapshotEntries.reduce((max, e) => Math.max(max, e.seq ?? 0), 0);
    const manualNumbered = manual.map((row) => {
      seq += 1;
      return { ...row, seq: row.seq ?? seq };
    });
    return [...snapshotEntries, ...manualNumbered];
  } catch {
    return legacyChangeRecordsToCumulative(draftData?.manifest?.changeRecords, 'manual');
  }
}

/**
 * 查看某一已发布版本：仅展示该版本及之前版本的修改记录（时点快照，不含后续版本）。
 */
export async function loadChangeLogThroughVersion(
  projectId: string,
  headers: HeadersInit,
  throughVersion: string,
  draftData?: DraftPayload | null,
): Promise<CumulativeChangeEntry[]> {
  try {
    const ordered = await resolvePublishedVersionOrder(projectId, headers, draftData);
    const idx = ordered.indexOf(throughVersion);
    const slice = idx >= 0 ? ordered.slice(0, idx + 1) : [throughVersion];
    return loadSnapshotsChangeLog(projectId, headers, slice);
  } catch {
    const snap = await fetchVersionSnapshot(projectId, throughVersion, headers);
    return snapshotToCumulativeEntries(snap as Record<string, unknown>, 0).entries;
  }
}

/** @deprecated 使用 loadChangeLogForDraft / loadChangeLogThroughVersion */
export async function loadCumulativeChangeLogSafe(
  projectId: string,
  headers: HeadersInit,
  draftData?: DraftPayload | null,
): Promise<CumulativeChangeEntry[]> {
  return loadChangeLogForDraft(projectId, headers, draftData);
}

export function formatProposalDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(value)) return value;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function proposalUrl(projectId: string, path: string, query?: Record<string, string>): string {
  const base = `${PROPOSAL_API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/proposal${path}`;
  if (!query || Object.keys(query).length === 0) return base;
  const qs = new URLSearchParams(query).toString();
  return `${base}?${qs}`;
}

const PROPOSAL_FETCH_TIMEOUT_MS = 30_000;

/** 禁用浏览器 HTTP 缓存，避免 GET 返回 304 空 body 导致解析失败或 loading 卡住 */
function withNoCache(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers);
  headers.set('Cache-Control', 'no-cache, no-store, must-revalidate');
  headers.set('Pragma', 'no-cache');
  return { ...init, headers, cache: 'no-store' };
}

function fetchTimeoutSignal(): AbortSignal {
  if (typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function') {
    return AbortSignal.timeout(PROPOSAL_FETCH_TIMEOUT_MS);
  }
  if (typeof window !== 'undefined') {
    const ctrl = new AbortController();
    window.setTimeout(() => ctrl.abort(), PROPOSAL_FETCH_TIMEOUT_MS);
    return ctrl.signal;
  }
  return new AbortController().signal;
}

async function proposalFetch<T>(
  projectId: string,
  path: string,
  init: RequestInit & { query?: Record<string, string> } = {},
): Promise<T> {
  const { query, ...rest } = init;
  const headers = new Headers(rest.headers);
  if (!headers.has('Content-Type') && rest.body) {
    headers.set('Content-Type', 'application/json');
  }

  const doFetch = (extraQuery?: Record<string, string>) =>
    fetch(
      proposalUrl(projectId, path, { ...query, ...extraQuery }),
      withNoCache({ ...rest, headers, signal: fetchTimeoutSignal() }),
    );

  let resp = await doFetch();
  if (resp.status === 304) {
    console.warn('[proposal-api] 304 Not Modified, retry with cache buster', path);
    resp = await doFetch({ _t: String(Date.now()) });
  }

  const text = await resp.text();
  let json: (ApiEnvelope<T> & ApiErrorBody) | null = null;
  if (text) {
    try {
      json = JSON.parse(text) as ApiEnvelope<T> & ApiErrorBody;
    } catch {
      throw new ProposalApiError(resp.status, 'PARSE_ERROR', text || resp.statusText);
    }
  }

  if (!resp.ok) {
    throw new ProposalApiError(
      resp.status,
      json?.error?.code ?? 'HTTP_ERROR',
      json?.error?.message ?? (resp.statusText || `HTTP ${resp.status}`),
    );
  }
  if (!json || !('data' in json)) {
    throw new ProposalApiError(resp.status, 'PARSE_ERROR', '响应缺少 data 字段');
  }
  return json.data;
}

export function buildProposalHeaders(role: string, account?: string): HeadersInit {
  return {
    'X-User-Role': mapProposalRole(role),
    'X-User-Account': account ?? 'frontend',
  };
}

export async function fetchDraft(
  projectId: string,
  headers: HeadersInit,
): Promise<DraftPayload> {
  return proposalFetch<DraftPayload>(projectId, '/draft', { headers });
}

export async function fetchMetadata(
  projectId: string,
  headers: HeadersInit,
  version = 'draft',
): Promise<VersionInfoMetadata> {
  return proposalFetch<VersionInfoMetadata>(projectId, '/metadata', {
    headers,
    query: { version },
  });
}

export async function patchMetadata(
  projectId: string,
  headers: HeadersInit,
  body: { documentSummary?: string; manualChangeLog?: CumulativeChangeEntry[] },
): Promise<VersionInfoMetadata> {
  return proposalFetch<VersionInfoMetadata>(projectId, '/metadata', {
    method: 'PATCH',
    headers,
    body: JSON.stringify(body),
    query: { version: 'draft' },
  });
}

export async function fetchCumulativeChangeLog(
  projectId: string,
  headers: HeadersInit,
): Promise<CumulativeChangeEntry[]> {
  const data = await proposalFetch<{ entries: CumulativeChangeEntry[] }>(
    projectId,
    '/metadata/cumulative-change-log',
    { headers },
  );
  return data.entries ?? [];
}

export async function saveDraft(
  projectId: string,
  headers: HeadersInit,
  body: {
    manualChangeLog?: CumulativeChangeEntry[];
    changeRecords?: ChangeRecord[];
    chapters?: Record<string, unknown>;
  } = {},
  etag?: string,
): Promise<SaveDraftResult & { metadata?: VersionInfoMetadata; cumulativeChangeLog?: CumulativeChangeEntry[] }> {
  const reqHeaders = new Headers(headers);
  if (etag) reqHeaders.set('If-Match', etag);
  const changeRecords =
    body.changeRecords ?? manualLogToChangeRecords(body.manualChangeLog);
  return proposalFetch<SaveDraftResult>(projectId, '/draft', {
    method: 'PUT',
    headers: reqHeaders,
    body: JSON.stringify({
      ...body,
      changeRecords,
      manualChangeLog: body.manualChangeLog,
    }),
  });
}

export async function fetchVersions(
  projectId: string,
  headers: HeadersInit,
): Promise<ProposalVersionItem[]> {
  const data = await proposalFetch<{ versions: ProposalVersionItem[] }>(
    projectId,
    '/versions',
    { headers },
  );
  return data.versions ?? [];
}

export async function fetchVersionSnapshot(
  projectId: string,
  proposalVersion: string,
  headers: HeadersInit,
): Promise<Record<string, unknown>> {
  return proposalFetch<Record<string, unknown>>(
    projectId,
    `/versions/${proposalVersion}`,
    { headers },
  );
}

export async function releaseAndDecide(
  projectId: string,
  headers: HeadersInit,
  body?: {
    reviewTagHint?: string;
    changeRecords?: ChangeRecord[];
  },
): Promise<ReleaseAndDecideResult> {
  return proposalFetch<ReleaseAndDecideResult>(projectId, '/release-and-decide', {
    method: 'POST',
    headers,
    body: JSON.stringify(body ?? {}),
  });
}

export async function exportDocument(
  projectId: string,
  headers: HeadersInit,
  version = 'draft',
): Promise<Blob> {
  const resp = await fetch(
    proposalUrl(projectId, '/export/document', { version }),
    { headers },
  );
  if (!resp.ok) {
    const text = await resp.text();
    let code = 'HTTP_ERROR';
    let message = resp.statusText;
    try {
      const json = JSON.parse(text) as ApiErrorBody;
      code = json.error?.code ?? code;
      message = json.error?.message ?? message;
    } catch {
      message = text || message;
    }
    throw new ProposalApiError(resp.status, code, message);
  }
  return resp.blob();
}

export async function fetchDeviceInfo(
  projectId: string,
  headers: HeadersInit,
  version = 'draft',
): Promise<{ rows: DeviceInfoRow[]; total: number }> {
  return proposalFetch<{ rows: DeviceInfoRow[]; total: number }>(
    projectId,
    '/chapters/2/device-info',
    { headers, query: { version } },
  );
}

export async function parseDeviceBoq(
  projectId: string,
  headers: HeadersInit,
  options?: { force?: boolean; enrich?: boolean; version?: string },
): Promise<{ rows: DeviceInfoRow[]; total: number }> {
  const query: Record<string, string> = { version: options?.version ?? 'draft' };
  if (options?.force) query.force = 'true';
  if (options?.enrich) query.enrich = 'true';
  return proposalFetch<{ rows: DeviceInfoRow[]; total: number }>(
    projectId,
    '/parse/device-boq',
    { method: 'POST', headers, query },
  );
}

export async function enrichDeviceInfo(
  projectId: string,
  headers: HeadersInit,
  version = 'draft',
): Promise<{ rows: DeviceInfoRow[]; total: number }> {
  return proposalFetch<{ rows: DeviceInfoRow[]; total: number }>(
    projectId,
    '/chapters/2/device-info/enrich',
    { method: 'POST', headers, query: { version } },
  );
}

function deviceRowNeedsEnrichment(row: DeviceInfoRow): boolean {
  if (!row.deviceModel) return false;
  // productCode may be prefilled from partCode fallback, but lifecycle fields are still missing.
  // Keep enrichment enabled until lifecycle timeline is present.
  return !(
    row.lifecycleStatus
    || row.gaActualDate
    || row.gaPlanDate
    || row.eomActualDate
    || row.eomPlanDate
    || row.eosActualDate
    || row.eosPlanDate
  );
}

export function deviceRowsNeedEnrichment(rows: DeviceInfoRow[]): boolean {
  return rows.some(deviceRowNeedsEnrichment);
}

const LEGACY_DEVICE_MODEL = /^[A-Z]{2,}[\dA-Z]*-[A-Z0-9-]+$/i;
const LEGACY_PART_MODEL = /^X\d{6,}$/i;

/** Detect leaf-level rows from the old assembler (sales_code / part models). */
export function deviceRowsLookLegacy(rows: DeviceInfoRow[]): boolean {
  return rows.some((row) => {
    const model = row.deviceModel.trim();
    if (!model) return false;
    if (LEGACY_DEVICE_MODEL.test(model)) return true;
    if (LEGACY_PART_MODEL.test(model)) return true;
    if (model === 'Spanner_2') return true;
    if (/^\d{6,}$/.test(row.productCode) && !row.productCode.startsWith('OFFE')) return true;
    return false;
  });
}

export async function patchDeviceInfoRow(
  projectId: string,
  rowId: string,
  body: Partial<
    Pick<
      DeviceInfoRow,
      | 'deviceModel'
      | 'productCode'
      | 'quantity'
      | 'version'
      | 'lifecycleStatus'
      | 'gaActualDate'
      | 'gaPlanDate'
      | 'eomActualDate'
      | 'eomPlanDate'
      | 'eosActualDate'
      | 'eosPlanDate'
      | 'deviceUHeight'
    >
  >,
  headers: HeadersInit,
): Promise<{ row: DeviceInfoRow; manifestActivity?: ManifestActivity }> {
  const hdrs = new Headers(headers);
  hdrs.set('Content-Type', 'application/json');
  const resp = await fetch(
    proposalUrl(projectId, `/chapters/2/device-info/${encodeURIComponent(rowId)}`),
    { method: 'PATCH', headers: hdrs, body: JSON.stringify(body) },
  );
  const text = await resp.text();
  let json: (ApiEnvelope<DeviceInfoRow> & ApiErrorBody) | null = null;
  if (text) {
    try {
      json = JSON.parse(text) as ApiEnvelope<DeviceInfoRow> & ApiErrorBody;
    } catch {
      throw new ProposalApiError(resp.status, 'PARSE_ERROR', text || resp.statusText);
    }
  }
  if (!resp.ok) {
    throw new ProposalApiError(
      resp.status,
      json?.error?.code ?? 'HTTP_ERROR',
      json?.error?.message ?? resp.statusText,
    );
  }
  if (!json?.data) {
    throw new ProposalApiError(resp.status, 'PARSE_ERROR', '响应缺少 data 字段');
  }
  return { row: json.data, manifestActivity: json.meta?.manifestActivity };
}

export async function fetchServiceDeliveryUi(
  projectId: string,
  headers: HeadersInit,
  version = 'draft',
): Promise<ServiceDeliveryUiRow[]> {
  const data = await proposalFetch<{ rows: ServiceDeliveryUiRow[] }>(
    projectId,
    '/chapters/8.1/service-delivery-ui',
    { headers, query: { version } },
  );
  return data.rows ?? [];
}

export async function initializeServiceDeliveryUi(
  projectId: string,
  headers: HeadersInit,
  strategy: 'skip' | 'merge' = 'skip',
): Promise<ServiceDeliveryUiRow[]> {
  const data = await proposalFetch<{ rows: ServiceDeliveryUiRow[] }>(
    projectId,
    '/chapters/8.1/service-delivery-ui/initialize',
    { method: 'POST', headers, query: { strategy } },
  );
  return data.rows ?? [];
}

export async function patchServiceDeliveryUiRow(
  projectId: string,
  rowId: string,
  deliveryChannel: DeliveryChannel,
  headers: HeadersInit,
): Promise<{ row: ServiceDeliveryUiRow; manifestActivity?: ManifestActivity }> {
  const hdrs = new Headers(headers);
  hdrs.set('Content-Type', 'application/json');
  const resp = await fetch(
    proposalUrl(projectId, `/chapters/8.1/service-delivery-ui/${encodeURIComponent(rowId)}`),
    {
      method: 'PATCH',
      headers: hdrs,
      body: JSON.stringify({ deliveryChannel }),
    },
  );
  const text = await resp.text();
  let json: (ApiEnvelope<ServiceDeliveryUiRow> & ApiErrorBody) | null = null;
  if (text) {
    try {
      json = JSON.parse(text) as ApiEnvelope<ServiceDeliveryUiRow> & ApiErrorBody;
    } catch {
      throw new ProposalApiError(resp.status, 'PARSE_ERROR', text || resp.statusText);
    }
  }
  if (!resp.ok) {
    throw new ProposalApiError(
      resp.status,
      json?.error?.code ?? 'HTTP_ERROR',
      json?.error?.message ?? resp.statusText,
    );
  }
  if (!json?.data) {
    throw new ProposalApiError(resp.status, 'PARSE_ERROR', '响应缺少 data 字段');
  }
  return {
    row: json.data,
    manifestActivity: json.meta?.manifestActivity,
  };
}

export async function fetchServiceContent(
  projectId: string,
  headers: HeadersInit,
  options?: {
    collapse?: boolean;
    expandOfferingId?: string;
    version?: string;
    page?: number;
    pageSize?: number;
  },
): Promise<{ rows: ServiceContentRow[]; total: number }> {
  const query: Record<string, string> = {
    version: options?.version ?? 'draft',
    collapse: String(options?.collapse ?? true),
  };
  if (options?.expandOfferingId) query.expandOfferingId = options.expandOfferingId;
  if (options?.page) query.page = String(options.page);
  if (options?.pageSize) query.pageSize = String(options.pageSize);

  return proposalFetch<{ rows: ServiceContentRow[]; total: number }>(
    projectId,
    '/chapters/8.2/service-content',
    { headers, query },
  );
}

export async function parseServiceBoq(
  projectId: string,
  headers: HeadersInit,
  options?: { force?: boolean; version?: string },
): Promise<{ rows: ServiceContentRow[]; total: number }> {
  const query: Record<string, string> = { version: options?.version ?? 'draft' };
  if (options?.force) query.force = 'true';
  return proposalFetch<{ rows: ServiceContentRow[]; total: number }>(
    projectId,
    '/parse/service-boq',
    { method: 'POST', headers, query },
  );
}

export async function patchServiceContentRow(
  projectId: string,
  rowId: string,
  body: Partial<Pick<ServiceContentRow, 'serviceName' | 'serviceContent' | 'quantity' | 'unit'>>,
  headers: HeadersInit,
): Promise<{ row: ServiceContentRow; manifestActivity?: ManifestActivity }> {
  const hdrs = new Headers(headers);
  hdrs.set('Content-Type', 'application/json');
  const resp = await fetch(
    proposalUrl(projectId, `/chapters/8.2/service-content/${encodeURIComponent(rowId)}`),
    { method: 'PATCH', headers: hdrs, body: JSON.stringify(body) },
  );
  const text = await resp.text();
  let json: (ApiEnvelope<ServiceContentRow> & ApiErrorBody) | null = null;
  if (text) {
    try {
      json = JSON.parse(text) as ApiEnvelope<ServiceContentRow> & ApiErrorBody;
    } catch {
      throw new ProposalApiError(resp.status, 'PARSE_ERROR', text || resp.statusText);
    }
  }
  if (!resp.ok) {
    throw new ProposalApiError(
      resp.status,
      json?.error?.code ?? 'HTTP_ERROR',
      json?.error?.message ?? resp.statusText,
    );
  }
  if (!json?.data) {
    throw new ProposalApiError(resp.status, 'PARSE_ERROR', '响应缺少 data 字段');
  }
  return { row: json.data, manifestActivity: json.meta?.manifestActivity };
}

export async function fetchMaintenanceStrategy(
  projectId: string,
  headers: HeadersInit,
  version = 'draft',
): Promise<MaintenanceStrategyRow[]> {
  const data = await proposalFetch<{ rows: MaintenanceStrategyRow[] }>(
    projectId,
    '/chapters/8.3/maintenance-strategy',
    { headers, query: { version } },
  );
  return data.rows ?? [];
}

export async function parseMaintenanceBoq(
  projectId: string,
  headers: HeadersInit,
  options?: { force?: boolean; version?: string },
): Promise<MaintenanceStrategyRow[]> {
  const query: Record<string, string> = { version: options?.version ?? 'draft' };
  if (options?.force) query.force = 'true';
  const data = await proposalFetch<{ rows: MaintenanceStrategyRow[] }>(
    projectId,
    '/parse/maintenance-boq',
    { method: 'POST', headers, query },
  );
  return data.rows ?? [];
}

export async function patchMaintenanceStrategyRow(
  projectId: string,
  rowId: string,
  body: Partial<{
    productModel: string;
    warrantyPolicy: string;
    maintenancePolicy: string;
    maintStartDate: string;
    maintEndDate: string;
    productEosDate: string | null;
    overEosApproval: string;
    recalculateEnd: boolean;
  }>,
  headers: HeadersInit,
): Promise<{ row: MaintenanceStrategyRow; manifestActivity?: ManifestActivity }> {
  const hdrs = new Headers(headers);
  hdrs.set('Content-Type', 'application/json');
  const resp = await fetch(
    proposalUrl(
      projectId,
      `/chapters/8.3/maintenance-strategy/${encodeURIComponent(rowId)}`,
    ),
    { method: 'PATCH', headers: hdrs, body: JSON.stringify(body) },
  );
  const text = await resp.text();
  let json: (ApiEnvelope<MaintenanceStrategyRow> & ApiErrorBody) | null = null;
  if (text) {
    try {
      json = JSON.parse(text) as ApiEnvelope<MaintenanceStrategyRow> & ApiErrorBody;
    } catch {
      throw new ProposalApiError(resp.status, 'PARSE_ERROR', text || resp.statusText);
    }
  }
  if (!resp.ok) {
    throw new ProposalApiError(
      resp.status,
      json?.error?.code ?? 'HTTP_ERROR',
      json?.error?.message ?? resp.statusText,
    );
  }
  if (!json?.data) {
    throw new ProposalApiError(resp.status, 'PARSE_ERROR', '响应缺少 data 字段');
  }
  return { row: json.data, manifestActivity: json.meta?.manifestActivity };
}

export async function fetchMaintenanceSla(
  projectId: string,
  headers: HeadersInit,
  version = 'draft',
): Promise<MaintenanceSlaResponse> {
  return proposalFetch<MaintenanceSlaResponse>(
    projectId,
    '/chapters/8.4/maintenance-sla',
    { headers, query: { version } },
  );
}

export async function parseMaintenanceProposalDoc(
  projectId: string,
  headers: HeadersInit,
  options?: { force?: boolean; version?: string },
): Promise<MaintenanceSlaResponse> {
  const query: Record<string, string> = { version: options?.version ?? 'draft' };
  if (options?.force) query.force = 'true';
  return proposalFetch<MaintenanceSlaResponse>(
    projectId,
    '/parse/maintenance-proposal-doc',
    { method: 'POST', headers, query },
  );
}

export async function patchMaintenanceSlaRow(
  projectId: string,
  rowId: string,
  body: Partial<{
    severityLevel: string;
    coveragePeriod: string;
    responseTime: string;
    restoreTime: string;
    resolveTime: string;
  }>,
  headers: HeadersInit,
): Promise<{ row: MaintenanceSlaRow; manifestActivity?: ManifestActivity }> {
  const hdrs = new Headers(headers);
  hdrs.set('Content-Type', 'application/json');
  const resp = await fetch(
    proposalUrl(
      projectId,
      `/chapters/8.4/maintenance-sla/${encodeURIComponent(rowId)}`,
    ),
    { method: 'PATCH', headers: hdrs, body: JSON.stringify(body) },
  );
  const text = await resp.text();
  let json: (ApiEnvelope<MaintenanceSlaRow> & ApiErrorBody) | null = null;
  if (text) {
    try {
      json = JSON.parse(text) as ApiEnvelope<MaintenanceSlaRow> & ApiErrorBody;
    } catch {
      throw new ProposalApiError(resp.status, 'PARSE_ERROR', text || resp.statusText);
    }
  }
  if (!resp.ok) {
    throw new ProposalApiError(
      resp.status,
      json?.error?.code ?? 'HTTP_ERROR',
      json?.error?.message ?? resp.statusText,
    );
  }
  if (!json?.data) {
    throw new ProposalApiError(resp.status, 'PARSE_ERROR', '响应缺少 data 字段');
  }
  return { row: json.data, manifestActivity: json.meta?.manifestActivity };
}

export async function patchMaintenanceSlaHardwareSupport(
  projectId: string,
  body: { hardwareSupport: string },
  headers: HeadersInit,
): Promise<{ hardwareSupport: string; serviceLevel: string; manifestActivity?: ManifestActivity }> {
  const hdrs = new Headers(headers);
  hdrs.set('Content-Type', 'application/json');
  const resp = await fetch(
    proposalUrl(projectId, '/chapters/8.4/maintenance-sla/hardware-support'),
    { method: 'PATCH', headers: hdrs, body: JSON.stringify(body) },
  );
  const text = await resp.text();
  let json: (ApiEnvelope<{ hardwareSupport: string; serviceLevel: string }> & ApiErrorBody) | null =
    null;
  if (text) {
    try {
      json = JSON.parse(text) as ApiEnvelope<{ hardwareSupport: string; serviceLevel: string }> &
        ApiErrorBody;
    } catch {
      throw new ProposalApiError(resp.status, 'PARSE_ERROR', text || resp.statusText);
    }
  }
  if (!resp.ok) {
    throw new ProposalApiError(
      resp.status,
      json?.error?.code ?? 'HTTP_ERROR',
      json?.error?.message ?? resp.statusText,
    );
  }
  if (!json?.data) {
    throw new ProposalApiError(resp.status, 'PARSE_ERROR', '响应缺少 data 字段');
  }
  return { ...json.data, manifestActivity: json.meta?.manifestActivity };
}

export function useProposalApiHeaders(): HeadersInit {
  const { session } = useAidaSession();
  return useMemo(
    () => buildProposalHeaders(session?.role ?? 'td', session?.sessionId),
    [session?.role, session?.sessionId],
  );
}

// ---------------------------------------------------------------------------
// Legacy chapter 5 / 7 compatibility (network-chapters, room-chapter)
// ---------------------------------------------------------------------------

export interface NetPlaneRow {
  row_id: string;
  type: string;
  vendor: string;
  model: string;
  ver: string;
  qty: number;
  source: string;
  proposal_version: string | null;
  note: string | null;
}

export interface AvailableDeviceItem {
  vendor: string;
  device_model: string;
  device_version: string;
  boq_quantity: number;
}

export interface NetMgmtRow {
  row_id: string;
  server_role: string;
  server_model: string;
  quantity: number;
  data_source: string;
}

export interface ClusterDeviceRow {
  row_id: string;
  source_net_plane_id: string | null;
  max_quantity: number;
  cluster_id: string | null;
  cluster_type: string;
  super_pod_id: string | null;
  storage_cluster_id: string | null;
  zone_id: string | null;
  ccae_cluster_id: string | null;
  dme_cluster_id: string | null;
  device_type: string;
  vendor: string;
  device_model: string;
  device_purpose: string | null;
  start_device_name: string | null;
  end_device_name: string | null;
  quantity: number;
  data_source: string;
  proposal_version: string | null;
}

export interface RoomRackRow {
  row_id: string;
  pod_name: string;
  room_name: string;
  compute: string;
  bus: string;
  param_leaf: string;
  biz_leaf: string;
  mgmt: string;
  sample_leaf: string;
  data_source?: string;
}

export interface UploadedFileResult {
  saved_path: string;
  logical_path?: string;
  uploaded: boolean;
  warning?: string;
}

export interface ChapterUploadResult<Row> extends UploadedFileResult {
  rows: Row[];
  common_plane?: UploadedFileResult;
}

export function chapterUploadMessage(result: ChapterUploadResult<unknown>): string {
  const describe = (file: UploadedFileResult, label = '') => {
    const prefix = label ? `${label}：` : '';
    const remote = file.uploaded
      ? `已上传远端 ${file.logical_path || '上传成功'}`
      : `远端未上传 ${file.warning || '未返回远端路径'}`;
    return `${prefix}已保存本地 ${file.saved_path}；${remote}`;
  };
  const messages = [describe(result)];
  if (result.common_plane) messages.push(describe(result.common_plane, '共平面类型表'));
  return messages.join('\n');
}

interface LegacyEnvelope<T> {
  data?: T;
  detail?: string | { message?: string };
}

function chapterRequestContext(
  url: string,
  init?: RequestInit,
): { url: string; init?: RequestInit } {
  let resolvedUrl = url;
  const headers = new Headers(init?.headers);
  try {
    const project = JSON.parse(sessionStorage.getItem('aida:current-project') || '{}') as {
      id?: string;
      code?: string;
    };
    const session = JSON.parse(sessionStorage.getItem('aida:session') || '{}') as {
      accessToken?: string;
    };
    const defaultProjectSegment = `/api/v1/projects/${DEFAULT_PROJECT_ID}/proposal/chapters/`;
    const currentProjectSegment = project.code
      ? `/api/v1/projects/${encodeURIComponent(project.code)}/proposal/chapters/`
      : '';
    const usesCurrentProject = url.includes(defaultProjectSegment)
      || Boolean(currentProjectSegment && url.includes(currentProjectSegment));
    if (project.code && url.includes(defaultProjectSegment)) {
      resolvedUrl = url.replace(defaultProjectSegment, currentProjectSegment);
    }
    if (session.accessToken) headers.set('Authorization', `Bearer ${session.accessToken}`);
    if (usesCurrentProject && project.id && /^[0-9a-f]{32}$/i.test(project.id)) {
      headers.set('X-Data-Center-Project-Id', project.id);
    }
  } catch {
    // Session context is optional; explicit projectId and caller headers remain authoritative.
  }
  if (PROPOSAL_API_BASE && resolvedUrl.startsWith('/')) {
    resolvedUrl = `${PROPOSAL_API_BASE}${resolvedUrl}`;
  }
  return {
    url: resolvedUrl,
    init: { ...init, headers },
  };
}

async function legacyRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, withNoCache({
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
    signal: fetchTimeoutSignal(),
  }));
  const text = await resp.text();
  let json: LegacyEnvelope<T> | null = null;
  if (text) {
    try {
      json = JSON.parse(text) as LegacyEnvelope<T>;
    } catch {
      if (!resp.ok) throw new Error(text || `HTTP ${resp.status}`);
      throw new Error('响应解析失败');
    }
  }
  if (!resp.ok) {
    const detail = json?.detail;
    if (typeof detail === 'string') throw new Error(detail);
    if (detail && typeof detail === 'object' && detail.message) throw new Error(detail.message);
    throw new Error(`HTTP ${resp.status}`);
  }
  if (json && 'data' in json) return json.data as T;
  return undefined as T;
}

async function chapterRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const request = chapterRequestContext(url, init);
  const headers = new Headers(request.init?.headers);
  if (!(request.init?.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const resp = await fetch(request.url, withNoCache({
    ...request.init,
    headers,
    signal: fetchTimeoutSignal(),
  }));
  const text = await resp.text();
  let json: LegacyEnvelope<T> | null = null;
  if (text) {
    try {
      json = JSON.parse(text) as LegacyEnvelope<T>;
    } catch {
      if (!resp.ok) throw new Error(text || `HTTP ${resp.status}`);
      throw new Error('响应解析失败');
    }
  }
  if (!resp.ok) {
    const detail = json?.detail;
    if (typeof detail === 'string') throw new Error(detail);
    if (detail && typeof detail === 'object' && detail.message) throw new Error(detail.message);
    throw new Error(`HTTP ${resp.status}`);
  }
  if (json && 'data' in json) return json.data as T;
  return undefined as T;
}

export const proposalApi = {
  listNetPlanes(projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ rows: NetPlaneRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane`,
    );
  },
  listAvailableDevices(projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ devices: AvailableDeviceItem[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/available-devices`,
    );
  },
  createNetPlane(sourceRowId: string, projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ row: NetPlaneRow }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane`,
      { method: 'POST', body: JSON.stringify({ source_row_id: sourceRowId }) },
    );
  },
  updateNetPlane(
    rowId: string,
    patch: {
      type?: string;
      vendor?: string;
      model?: string;
      ver?: string;
      qty?: number;
      source?: string;
      note?: string | null;
    },
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return chapterRequest<{ row: NetPlaneRow; warnings: { code: string; message: string }[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/${rowId}`,
      { method: 'PATCH', body: JSON.stringify(patch) },
    );
  },
  deleteNetPlane(rowId: string, projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ deleted: string }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/${rowId}?confirm=true`,
      { method: 'DELETE' },
    );
  },
  importNetPlanes(file: File, projectId = DEFAULT_PROJECT_ID) {
    const body = new FormData();
    body.append('file', file);
    return chapterRequest<{ rows: NetPlaneRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/upload`,
      { method: 'POST', body },
    );
  },
  autosaveNetPlanes(rows: NetPlaneRow[], commonPlaneTypes: string[], projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<ChapterUploadResult<NetPlaneRow>>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/autosave`,
      { method: 'POST', body: JSON.stringify({ rows, common_plane_types: commonPlaneTypes }) },
    );
  },
  /** @deprecated 使用 autosaveNetPlanes */
  exportNetPlanes(rows: NetPlaneRow[], commonPlaneTypes: string[], projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ saved_path: string; logical_path?: string; uploaded: boolean }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/export`,
      { method: 'POST', body: JSON.stringify({ rows, common_plane_types: commonPlaneTypes }) },
    );
  },
  initializeNetMgmt(projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ rows: NetMgmtRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/initialize`,
      { method: 'POST' },
    );
  },
  updateNetMgmt(
    rowId: string,
    patch: { server_model?: string; quantity?: number },
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return chapterRequest<NetMgmtRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/${rowId}`,
      { method: 'PATCH', body: JSON.stringify(patch) },
    );
  },
  deleteNetMgmt(rowId: string, projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<void>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/${rowId}`,
      { method: 'DELETE' },
    );
  },
  importNetMgmt(file: File, projectId = DEFAULT_PROJECT_ID) {
    const body = new FormData();
    body.append('file', file);
    return chapterRequest<{ rows: NetMgmtRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/upload`,
      { method: 'POST', body },
    );
  },
  autosaveNetMgmt(rows: NetMgmtRow[], projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<ChapterUploadResult<NetMgmtRow>>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/autosave`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },
  /** @deprecated 使用 autosaveNetMgmt */
  exportNetMgmt(rows: NetMgmtRow[], projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ saved_path: string; logical_path?: string; uploaded: boolean }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/export`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },
  listClusterDevices(projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ rows: ClusterDeviceRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list`,
    );
  },
  createClusterDevice(sourceNetPlaneId: string, projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<ClusterDeviceRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list`,
      { method: 'POST', body: JSON.stringify({ source_net_plane_id: sourceNetPlaneId }) },
    );
  },
  updateClusterDevice(
    rowId: string,
    patch: {
      cluster_id?: string;
      cluster_type?: string;
      super_pod_id?: string;
      storage_cluster_id?: string;
      zone_id?: string;
      ccae_cluster_id?: string;
      dme_cluster_id?: string;
      device_type?: string;
      device_purpose?: string;
      start_device_name?: string;
      end_device_name?: string;
      quantity?: number;
    },
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return chapterRequest<ClusterDeviceRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list/${rowId}`,
      { method: 'PATCH', body: JSON.stringify(patch) },
    );
  },
  deleteClusterDevice(rowId: string, projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<void>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list/${rowId}?confirm=true`,
      { method: 'DELETE' },
    );
  },
  importClusterDevices(file: File, projectId = DEFAULT_PROJECT_ID) {
    const body = new FormData();
    body.append('file', file);
    return chapterRequest<{ rows: ClusterDeviceRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list/upload`,
      { method: 'POST', body },
    );
  },
  autosaveClusterDevices(rows: ClusterDeviceRow[], projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<ChapterUploadResult<ClusterDeviceRow>>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list/autosave`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },
  /** @deprecated 使用 autosaveClusterDevices */
  exportClusterDevices(rows: ClusterDeviceRow[], projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ saved_path: string; logical_path?: string; uploaded: boolean }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list/export`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },
};

export const roomRackApi = {
  list(projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ rows: RoomRackRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack`,
    );
  },
  createAfter(
    sourceRowId: string,
    row: Partial<Omit<RoomRackRow, 'row_id' | 'data_source'>>,
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return chapterRequest<RoomRackRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack?source_row_id=${encodeURIComponent(sourceRowId)}`,
      { method: 'POST', body: JSON.stringify(row) },
    );
  },
  update(
    rowId: string,
    patch: Partial<Omit<RoomRackRow, 'row_id' | 'data_source'>>,
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return chapterRequest<RoomRackRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack/${rowId}`,
      { method: 'PATCH', body: JSON.stringify(patch) },
    );
  },
  delete(rowId: string, projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<void>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack/${rowId}?confirm=true`,
      { method: 'DELETE' },
    );
  },
  import(file: File, projectId = DEFAULT_PROJECT_ID) {
    const body = new FormData();
    body.append('file', file);
    return chapterRequest<{ rows: RoomRackRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack/upload`,
      { method: 'POST', body },
    );
  },
  autosave(rows: RoomRackRow[], projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<ChapterUploadResult<RoomRackRow>>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack/autosave`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },
  /** @deprecated 使用 autosave */
  export(rows: RoomRackRow[], projectId = DEFAULT_PROJECT_ID) {
    return chapterRequest<{ saved_path: string; logical_path?: string; uploaded: boolean }>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack/export`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },
};
