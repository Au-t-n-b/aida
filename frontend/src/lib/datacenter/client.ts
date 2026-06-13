import type { ApiMeta, ProjectDataContext, ProposalTableSlot, TableReadResult } from './types';
import { notifyDataFallback } from './fallback-notify';

const API = '/api/v1';
const LOG_PREFIX = '[AIDA DC]';
const DC_FETCH_TIMEOUT_MS = 30_000;
const DC_SYNC_TIMEOUT_MS = 120_000;

function dcFetchSignal(): AbortSignal | undefined {
  if (typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function') {
    return AbortSignal.timeout(DC_FETCH_TIMEOUT_MS);
  }
  return undefined;
}

interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
  meta?: ApiMeta;
}

function authHeaders(token?: string): HeadersInit {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

function maskToken(token?: string): string {
  if (!token) return '(none)';
  if (token.length <= 12) return '***';
  return `${token.slice(0, 6)}...${token.slice(-4)}`;
}

export async function readProposalTable(
  ctx: ProjectDataContext,
  slot: ProposalTableSlot,
): Promise<TableReadResult> {
  const url = `${API}/proposal/tables/read`;
  const body = {
    slot,
    projectId: ctx.dcProjectId,
    projectName: ctx.projectName,
    projectCode: ctx.projectCode ?? null,
  };
  console.info(`${LOG_PREFIX} POST ${url}`, {
    slot,
    projectId: ctx.dcProjectId,
    projectName: ctx.projectName,
    projectCode: ctx.projectCode,
    token: maskToken(ctx.token),
  });

  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: authHeaders(ctx.token),
      body: JSON.stringify(body),
      cache: 'no-store',
      signal: dcFetchSignal(),
    });
  } catch (err) {
    console.error(`${LOG_PREFIX} POST ${url} network error`, err);
    throw err;
  }

  const text = await res.text();
  if (!res.ok) {
    console.error(`${LOG_PREFIX} POST ${url} HTTP ${res.status}`, text.slice(0, 500));
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
  }

  let envelope: ApiEnvelope<TableReadResult>;
  try {
    envelope = JSON.parse(text) as ApiEnvelope<TableReadResult>;
  } catch {
    console.error(`${LOG_PREFIX} POST ${url} invalid JSON`, text.slice(0, 500));
    throw new Error('invalid JSON response');
  }

  if (envelope.code !== 0) {
    console.error(`${LOG_PREFIX} POST ${url} code=${envelope.code}`, envelope.message);
    throw new Error(envelope.message || 'read error');
  }

  const rowCount = envelope.data?.rows?.length ?? 0;
  console.info(`${LOG_PREFIX} POST ${url} ok`, {
    source: envelope.meta?.source,
    logicalPath: envelope.meta?.logicalPath,
    rowCount,
    warnings: envelope.meta?.warnings,
  });

  const warnings = envelope.meta?.warnings ?? [];
  if (warnings.length) notifyDataFallback(warnings, envelope.meta?.source);
  return { ...envelope.data, meta: envelope.meta };
}

export async function writeProposalTable(
  ctx: ProjectDataContext,
  slot: 'raci_out' | 'acceptance_out' | 'testcases_out',
  kind: 'raci' | 'acceptance' | 'testcases',
  rows: unknown[],
  version: number,
): Promise<{ path: string; version: number; meta?: ApiMeta }> {
  const url = `${API}/proposal/tables/write`;
  console.info(`${LOG_PREFIX} POST ${url}`, {
    slot,
    kind,
    version,
    rowCount: rows.length,
    projectId: ctx.dcProjectId,
    token: maskToken(ctx.token),
  });

  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: authHeaders(ctx.token),
      body: JSON.stringify({
        slot,
        projectId: ctx.dcProjectId,
        projectName: ctx.projectName,
        projectCode: ctx.projectCode ?? null,
        kind,
        version,
        rows,
      }),
    });
  } catch (err) {
    console.error(`${LOG_PREFIX} POST ${url} network error`, err);
    throw err;
  }

  const text = await res.text();
  if (!res.ok) {
    console.error(`${LOG_PREFIX} POST ${url} HTTP ${res.status}`, text.slice(0, 500));
    throw new Error(`HTTP ${res.status}`);
  }

  const envelope = JSON.parse(text) as ApiEnvelope<{ path: string; version: number }>;
  if (envelope.code !== 0) throw new Error(envelope.message || 'write error');

  console.info(`${LOG_PREFIX} POST ${url} ok`, {
    source: envelope.meta?.source,
    path: envelope.data?.path,
    warnings: envelope.meta?.warnings,
  });

  const warnings = envelope.meta?.warnings ?? [];
  if (warnings.length) notifyDataFallback(warnings, envelope.meta?.source);
  return { ...envelope.data, meta: envelope.meta };
}

export async function parseTechProposalUpload(
  file: File,
  token?: string,
): Promise<unknown[]> {
  const url = `${API}/proposal/parse/tech-proposal`;
  console.info(`${LOG_PREFIX} POST ${url}`, { fileName: file.name, token: maskToken(token) });
  const fd = new FormData();
  fd.append('file', file);
  const headers: HeadersInit = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: fd,
  });
  if (!res.ok) {
    console.error(`${LOG_PREFIX} POST ${url} HTTP ${res.status}`);
    throw new Error(`HTTP ${res.status}`);
  }
  const body = (await res.json()) as ApiEnvelope<{ rows: unknown[] }>;
  if (body.code !== 0) throw new Error(body.message || 'parse error');
  console.info(`${LOG_PREFIX} POST ${url} ok`, { rowCount: body.data.rows?.length ?? 0 });
  return body.data.rows ?? [];
}

export async function parseTestcasesUpload(
  file: File,
  ctx: ProjectDataContext,
): Promise<{ rows: unknown[]; warnings: string[] }> {
  const url = `${API}/proposal/parse/testcases`;
  console.info(`${LOG_PREFIX} POST ${url}`, {
    fileName: file.name,
    projectId: ctx.dcProjectId,
    token: maskToken(ctx.token),
  });
  const fd = new FormData();
  fd.append('file', file);
  fd.append('projectId', ctx.dcProjectId);
  fd.append('projectName', ctx.projectName);
  if (ctx.projectCode) fd.append('projectCode', ctx.projectCode);
  const headers: HeadersInit = {};
  if (ctx.token) headers.Authorization = `Bearer ${ctx.token}`;
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: fd,
  });
  if (!res.ok) {
    console.error(`${LOG_PREFIX} POST ${url} HTTP ${res.status}`);
    throw new Error(`HTTP ${res.status}`);
  }
  const body = (await res.json()) as ApiEnvelope<{ rows: unknown[] }> & { meta?: ApiMeta };
  if (body.code !== 0) throw new Error(body.message || 'parse error');
  console.info(`${LOG_PREFIX} POST ${url} ok`, {
    rowCount: body.data.rows?.length ?? 0,
    templateSource: body.meta?.source,
    warnings: body.meta?.warnings,
  });
  const warnings = body.meta?.warnings ?? [];
  if (warnings.length) notifyDataFallback(warnings, body.meta?.source);
  return { rows: body.data.rows ?? [], warnings };
}

export type { ProjectDataContext, ProposalTableSlot, TableReadResult };

export interface SyncSlotResult {
  status: 'local' | 'downloaded' | 'missing';
  localPath?: string;
  logical?: string;
  bytes?: number;
  error?: string;
}

export async function syncProposalLocalFiles(
  ctx: ProjectDataContext,
  slots?: ProposalTableSlot[],
): Promise<{ slots: Record<string, SyncSlotResult>; ready: number; total: number; warnings: string[] }> {
  const url = `${API}/proposal/sync`;
  const body = {
    projectId: ctx.dcProjectId,
    projectName: ctx.projectName,
    projectCode: ctx.projectCode ?? null,
    slots: slots ?? null,
  };
  console.info(`${LOG_PREFIX} POST ${url}`, {
    projectId: ctx.dcProjectId,
    projectName: ctx.projectName,
    slotCount: slots?.length ?? 'all',
    token: maskToken(ctx.token),
  });

  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: authHeaders(ctx.token),
      body: JSON.stringify(body),
      cache: 'no-store',
      signal:
        typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
          ? AbortSignal.timeout(DC_SYNC_TIMEOUT_MS)
          : dcFetchSignal(),
    });
  } catch (err) {
    console.error(`${LOG_PREFIX} POST ${url} network error`, err);
    throw err;
  }

  const text = await res.text();
  if (!res.ok) {
    console.error(`${LOG_PREFIX} POST ${url} HTTP ${res.status}`, text.slice(0, 500));
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
  }

  const envelope = JSON.parse(text) as ApiEnvelope<{
    slots: Record<string, SyncSlotResult>;
    ready: number;
    total: number;
  }>;
  if (envelope.code !== 0) {
    throw new Error(envelope.message || 'sync error');
  }

  const warnings = envelope.meta?.warnings ?? [];
  console.info(`${LOG_PREFIX} POST ${url} ok`, {
    ready: envelope.data.ready,
    total: envelope.data.total,
    warnings,
  });
  if (warnings.length) notifyDataFallback(warnings, envelope.meta?.source);
  return {
    slots: envelope.data.slots,
    ready: envelope.data.ready,
    total: envelope.data.total,
    warnings,
  };
}
