export type LoginResponse = {
  access_token: string;
  role: string;
  session_id: string;
  container_endpoint?: string | null;
  reused: boolean;
};

export type ChatAccessResponse = {
  session_id: string;
  endpoint: string;
  token: string;
  expires_at: number;
  protocol: string;
  paths?: { send?: string };
};

export type TaskStartResponse = {
  task_id: string;
  state: string;
};

export type TaskSnapshotResponse = {
  task_id: string;
  state: string;
  last_seq: number;
  changed_paths: string[];
  message?: string | null;
  progress?: number | null;
  step?: string | null;
  kind?: string | null;
  payload?: Record<string, unknown>;
};

export type ContextResponse = {
  skills: string[];
  datasets: string[];
  models: string[];
  permissions?: Record<string, unknown>;
};

export type ArchiveResponse = {
  session_id: string;
  archived: boolean;
  archive_id?: string | null;
  summary?: Record<string, unknown> | null;
  detail?: string | null;
};

const DEFAULT_MANAGER_BASE = 'http://127.0.0.1:8000';

export function managerBase(): string {
  return (import.meta.env.VITE_CLAWMANAGER_BASE || DEFAULT_MANAGER_BASE).replace(/\/$/, '');
}

export async function loginToClawManager(input: {
  username: string;
  password: string;
  project_code: string;
}): Promise<LoginResponse> {
  return request<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function requestChatAccess(input: {
  accessToken: string;
  sessionId: string;
}): Promise<ChatAccessResponse> {
  return request<ChatAccessResponse>('/api/v1/chat/access', {
    method: 'POST',
    accessToken: input.accessToken,
    body: JSON.stringify({ session_id: input.sessionId }),
  });
}

export async function startClawTask(input: {
  accessToken: string;
  sessionId: string;
  kind: string;
  params?: Record<string, unknown>;
}): Promise<TaskStartResponse> {
  return request<TaskStartResponse>('/api/v1/tasks', {
    method: 'POST',
    accessToken: input.accessToken,
    body: JSON.stringify({
      session_id: input.sessionId,
      kind: input.kind,
      params: input.params ?? {},
    }),
  });
}

export async function getTaskSnapshot(input: {
  accessToken: string;
  taskId: string;
}): Promise<TaskSnapshotResponse> {
  return request<TaskSnapshotResponse>(`/api/v1/tasks/${encodeURIComponent(input.taskId)}`, {
    accessToken: input.accessToken,
  });
}

export function subscribeTaskEvents(input: {
  accessToken: string;
  taskId: string;
  onEvent: (event: TaskSnapshotResponse & { seq?: number }) => void;
  onError?: (error: Event) => void;
}): EventSource {
  const url = new URL(`${managerBase()}/api/v1/tasks/${encodeURIComponent(input.taskId)}/events`);
  url.searchParams.set('access_token', input.accessToken);
  const es = new EventSource(url.toString());
  const onTaskEvent = (event: MessageEvent) => {
    try {
      input.onEvent(JSON.parse(event.data));
    } catch {
      // Ignore malformed task events; the EventSource remains alive.
    }
  };
  es.addEventListener('running', onTaskEvent);
  es.addEventListener('succeeded', onTaskEvent);
  es.addEventListener('failed', onTaskEvent);
  es.addEventListener('canceled', onTaskEvent);
  es.onerror = (event) => input.onError?.(event);
  return es;
}

export async function loadClawContext(accessToken: string): Promise<ContextResponse> {
  return request<ContextResponse>('/api/v1/context', { accessToken });
}

export async function resumeClawTask(input: {
  accessToken: string;
  sessionId: string;
  taskId: string;
  payload?: Record<string, unknown>;
  fromStep?: string | null;
}): Promise<{ ok: boolean; status?: string; mode?: string; message?: string }> {
  return request(`/api/v1/tasks/${encodeURIComponent(input.taskId)}/resume`, {
    method: 'POST',
    accessToken: input.accessToken,
    body: JSON.stringify({
      session_id: input.sessionId,
      payload: input.payload ?? {},
      from_step: input.fromStep ?? null,
    }),
  });
}

export async function logoutFromClawManager(input: {
  accessToken: string;
  sessionId: string;
}): Promise<ArchiveResponse & { destroyed?: boolean }> {
  return request<ArchiveResponse & { destroyed?: boolean }>('/api/v1/auth/logout', {
    method: 'POST',
    accessToken: input.accessToken,
    body: JSON.stringify({ session_id: input.sessionId }),
  });
}

export async function archiveClawSession(input: {
  accessToken: string;
  sessionId: string;
  destroyAfter?: boolean;
}): Promise<ArchiveResponse> {
  return request<ArchiveResponse>('/api/v1/archive', {
    method: 'POST',
    accessToken: input.accessToken,
    body: JSON.stringify({
      session_id: input.sessionId,
      destroy_after: input.destroyAfter ?? false,
    }),
  });
}

export async function postChatMessage(access: ChatAccessResponse, path: string, body: unknown): Promise<void> {
  const resp = await fetch(chatUrl(access, path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(await errorMessage(resp));
  }
}

export async function streamChatMessage(
  access: ChatAccessResponse,
  body: unknown,
  handlers: {
    onDelta?: (delta: string) => void;
    onDone?: () => void;
    onError?: (message: string) => void;
    signal?: AbortSignal;
  } = {},
): Promise<void> {
  const path = access.paths?.send || 'messages';
  const resp = await fetch(chatUrl(access, path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: handlers.signal,
  });
  if (!resp.ok) {
    throw new Error(await errorMessage(resp));
  }
  const reader = resp.body?.getReader();
  if (!reader) {
    handlers.onDone?.();
    return;
  }
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() || '';
    for (const part of parts) {
      handleSseBlock(part, handlers);
    }
  }
  if (buffer.trim()) {
    handleSseBlock(buffer, handlers);
  }
  handlers.onDone?.();
}

export function openChatStream(access: ChatAccessResponse, path: string): EventSource {
  return new EventSource(chatUrl(access, path));
}

export function chatUrl(access: ChatAccessResponse, path: string): string {
  const endpoint = normalizeEndpoint(access.endpoint);
  const cleanPath = path.replace(/^\/+/, '');
  const url = new URL(`/chat/${cleanPath}`, endpoint);
  url.searchParams.set('access_token', access.token);
  return url.toString();
}

async function request<T>(
  path: string,
  init: RequestInit & { accessToken?: string } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  if (init.accessToken) {
    headers.set('Authorization', `Bearer ${init.accessToken}`);
  }
  const resp = await fetch(`${managerBase()}${path}`, { ...init, headers });
  if (!resp.ok) {
    throw new Error(await errorMessage(resp));
  }
  return resp.json() as Promise<T>;
}

async function errorMessage(resp: Response): Promise<string> {
  try {
    const data = await resp.json();
    return data?.detail || `${resp.status} ${resp.statusText}`;
  } catch {
    return `${resp.status} ${resp.statusText}`;
  }
}

function normalizeEndpoint(endpoint: string): string {
  if (/^https?:\/\//.test(endpoint)) return endpoint;
  return `http://${endpoint}`;
}

function handleSseBlock(
  block: string,
  handlers: {
    onDelta?: (delta: string) => void;
    onDone?: () => void;
    onError?: (message: string) => void;
  },
): void {
  const lines = block.split(/\r?\n/);
  const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() || 'message';
  const data = lines
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n');
  if (data === '[DONE]' || event === 'done') {
    handlers.onDone?.();
    return;
  }
  if (event === 'error') {
    handlers.onError?.(data || 'AIDA 流式响应出错');
    return;
  }
  const delta = extractStreamDelta(data);
  if (delta) handlers.onDelta?.(delta);
}

function extractStreamDelta(raw: string): string {
  if (!raw) return '';
  try {
    const data = JSON.parse(raw);
    return String(
      data.delta ??
        data.content ??
        data.text ??
        data.message ??
        data.data?.delta ??
        data.data?.content ??
        data.choices?.[0]?.delta?.content ??
        '',
    );
  } catch {
    return raw;
  }
}
