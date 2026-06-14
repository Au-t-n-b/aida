/** Manager / 数据中心 API 结构化错误（便于界面排障展示） */

export type ApiErrorDetail = {
  message: string;
  code?: number;
  username?: string;
  projectId?: string;
  operation?: string;
  reason?: string;
  httpStatus?: number;
  method?: string;
  url?: string;
  dcResponse?: unknown;
};

export class ApiRequestError extends Error {
  readonly detail: ApiErrorDetail;

  constructor(detail: ApiErrorDetail) {
    super(detail.message);
    this.name = 'ApiRequestError';
    this.detail = detail;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

export function isApiErrorDetail(value: unknown): value is ApiErrorDetail {
  return isRecord(value) && typeof value.message === 'string';
}

export function parseApiError(err: unknown): ApiErrorDetail | null {
  if (err instanceof ApiRequestError) return err.detail;
  return null;
}

export function formatDcResponse(value: unknown): string {
  if (value == null) return '—';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/** 界面排障信息行（不含主 message，避免重复） */
export function apiErrorDiagnosticLines(detail: ApiErrorDetail): Array<{ label: string; value: string }> {
  const lines: Array<{ label: string; value: string }> = [];
  if (detail.username) lines.push({ label: '账号', value: detail.username });
  if (detail.projectId) lines.push({ label: '项目 ID', value: detail.projectId });
  if (detail.operation) lines.push({ label: '操作', value: detail.operation });
  if (detail.method || detail.httpStatus != null) {
    const method = detail.method || '—';
    const status = detail.httpStatus != null ? String(detail.httpStatus) : '—';
    lines.push({ label: 'HTTP', value: `${method} ${status}` });
  }
  if (detail.url) lines.push({ label: '请求地址', value: detail.url });
  if (detail.reason) lines.push({ label: '原因说明', value: detail.reason });
  if (detail.dcResponse !== undefined) {
    lines.push({ label: '数据中心返回', value: formatDcResponse(detail.dcResponse) });
  }
  if (detail.code != null) lines.push({ label: '错误码', value: String(detail.code) });
  return lines;
}

export function applyApiError(
  err: unknown,
  setMessage: (msg: string) => void,
  setDetail: (detail: ApiErrorDetail | null) => void,
  fallback: string,
) {
  const parsed = parseApiError(err);
  if (parsed) {
    setMessage(parsed.message);
    setDetail(parsed);
    return;
  }
  setMessage(err instanceof Error ? err.message : fallback);
  setDetail(null);
}
