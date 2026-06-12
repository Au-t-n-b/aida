/**
 * Mock 数据中心 · xlsx/docx 读写客户端
 */
import type {
  AcceptanceItem,
  AcceptanceTestCase,
  PlanActivity,
  RaciRow,
  SavedTestCaseRow,
} from '@/types/domain';

interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
}

interface FileReadData {
  kind: string;
  rows?: unknown[];
  version?: number;
  cardScale?: number;
  text?: string;
}

const API = '/api/v1';

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = (await res.json()) as ApiEnvelope<T>;
  if (body.code !== 0) throw new Error(body.message || 'API error');
  return body.data;
}

async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = (await res.json()) as ApiEnvelope<T>;
  if (body.code !== 0) throw new Error(body.message || 'API error');
  return body.data;
}

export async function fetchMockFile(logicalPath: string): Promise<FileReadData> {
  const q = new URLSearchParams({ logicalPath });
  return apiGet<FileReadData>(`/mock/file?${q}`);
}

export async function writeMockFile(params: {
  logicalPath: string;
  kind: 'raci' | 'acceptance' | 'testcases';
  projectName: string;
  version: number;
  rows: RaciRow[] | AcceptanceItem[] | SavedTestCaseRow[];
}): Promise<{ path: string; version: number }> {
  return apiPost('/mock/file', params);
}

export async function parseTechProposalUpload(file: File): Promise<AcceptanceItem[]> {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${API}/proposal/parse/tech-proposal`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = (await res.json()) as ApiEnvelope<{ rows: AcceptanceItem[] }>;
  if (body.code !== 0) throw new Error(body.message || 'parse error');
  return body.data.rows ?? [];
}

export function asRaciRows(rows: unknown[]): RaciRow[] {
  return rows.map((r) => {
    const o = r as Record<string, string>;
    return {
      stack: o.stack ?? '',
      cat: o.cat ?? '',
      act: o.act ?? '',
      gts: o.gts ?? '',
      hw: o.hw ?? '',
      partner: o.partner ?? '',
      customer: o.customer ?? '',
    };
  });
}

export function asPlanActivities(rows: unknown[]): PlanActivity[] {
  return rows.map((r) => {
    const o = r as Record<string, unknown>;
    const progress = Number(o.progress ?? 0);
    return {
      name: String(o.name ?? ''),
      start: String(o.start ?? ''),
      end: String(o.end ?? ''),
      actualStart: String(o.actualStart ?? ''),
      actualEnd: String(o.actualEnd ?? ''),
      owner: String(o.owner ?? ''),
      unit: String(o.unit ?? ''),
      status: String(o.status ?? ''),
      progress: Number.isFinite(progress) ? progress : 0,
      progressTone: (o.progressTone as PlanActivity['progressTone']) ?? (progress >= 100 ? 'green' : 'blue'),
    };
  });
}

export function asAcceptanceItems(rows: unknown[]): AcceptanceItem[] {
  return rows.map((r) => {
    const o = r as Record<string, string>;
    return {
      cat: o.cat ?? '',
      scheme: o.scheme ?? '',
      standard: o.standard ?? '',
      milestone: o.milestone ?? '',
      doc: o.doc ?? '',
      payment: o.payment ?? '',
      paymentMilestone: o.paymentMilestone ?? '',
    };
  });
}

export function asTestCases(rows: unknown[]): AcceptanceTestCase[] {
  return rows.map((r) => {
    const o = r as Record<string, unknown>;
    return {
      id: String(o.id ?? ''),
      l1: String(o.l1 ?? ''),
      l2: String(o.l2 ?? ''),
      l3: String(o.l3 ?? ''),
      purpose: String(o.purpose ?? ''),
      topology: String(o.topology ?? ''),
      pre: String(o.pre ?? ''),
      steps: Array.isArray(o.steps) ? (o.steps as string[]) : [],
      expects: Array.isArray(o.expects) ? (o.expects as string[]) : [],
      result: String(o.result ?? ''),
      remark: String(o.remark ?? ''),
    };
  });
}
