export type ClawUserProfile = {
  user_id: string;
  username: string;
  display_name: string;
  email?: string | null;
  status?: number | null;
  global_roles: { roleCode: string; roleName?: string }[];
  permissions: string[];
};

export type LoginResponse = {
  access_token: string;
  token_type?: string;
  role: string;
  session_id: string;
  container_endpoint?: string | null;
  reused: boolean;
  user_id?: number | null;
  username?: string | null;
  expires_in?: number | null;
  user?: ClawUserProfile | null;
};

export type DcEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

export type MyProjectsQuery = {
  page?: number;
  pageSize?: number;
  status?: string;
  keyword?: string;
};

export type CreateProjectBody = {
  projectName: string;
  projectCode?: string;
  bidCode?: string;
  customerName?: string;
  tdUserId?: number;
  pdUserId?: number;
  pcmUserId?: number;
};

export type CreateProjectResult = {
  id: number;
  projectId: string;
  status: string;
  rootPath?: string;
};

/** GET /api/v1/projects/{uuid} — 项目详情（含 members） */
export type DcProjectMember = {
  userProjectRoleId?: number;
  userId?: number;
  username?: string;
  roleCode?: string;
  roleName?: string;
};

export type DcProjectDetail = {
  id?: number;
  projectId: string;
  projectName: string;
  projectCode?: string | null;
  bidCode?: string | null;
  customerName?: string | null;
  status?: string;
  stage?: string | null;
  progress?: number;
  risk?: string;
  description?: string | null;
  deliveryTraits?: unknown[] | null;
  creatorId?: number;
  creatorName?: string | null;
  tdUserId?: number | null;
  tdName?: string | null;
  pdUserId?: number | null;
  pdName?: string | null;
  pcmUserId?: number | null;
  pcmName?: string | null;
  rootPath?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  members?: DcProjectMember[];
};

export type DcMyProjectsData = {
  list: Array<{
    id: number;
    projectId: string;
    projectName: string;
    projectCode?: string | null;
    bidCode?: string | null;
    status: string;
    stage?: string | null;
    progress: number;
    risk: string;
    updatedAt?: string | null;
    myRoles: { roleCode: string; roleName?: string }[];
    canEnter: boolean;
    disabledReason?: string | null;
  }>;
  total: number;
};

export type RegisterResponse = {
  user_id: number;
  username: string;
  message?: string;
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
  const configured = import.meta.env.VITE_CLAWMANAGER_BASE as string | undefined;
  // 开发态留空 → 同源请求走 Vite proxy 到 Manager，避免跨域 Failed to fetch
  if (configured === '' || configured === '/') return '';
  return (configured || DEFAULT_MANAGER_BASE).replace(/\/$/, '');
}

export async function loginToClawManager(input: {
  username: string;
  password: string;
  project_code?: string;
}): Promise<LoginResponse> {
  return request<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({
      username: input.username,
      password: input.password,
      project_code: input.project_code ?? '',
    }),
  });
}

/** 新建项目 POST /api/v1/projects（初始待审批） */
export async function createProject(
  accessToken: string,
  body: CreateProjectBody,
): Promise<DcEnvelope<CreateProjectResult>> {
  return requestEnvelope<CreateProjectResult>('/api/v1/projects', {
    method: 'POST',
    accessToken,
    body: JSON.stringify(body),
  });
}

/** 接口二：当前用户参与的项目列表（Bearer token） */
export async function fetchMyProjects(
  accessToken: string,
  query: MyProjectsQuery = {},
): Promise<DcEnvelope<DcMyProjectsData>> {
  const params = new URLSearchParams();
  if (query.page) params.set('page', String(query.page));
  if (query.pageSize) params.set('pageSize', String(query.pageSize));
  if (query.status) params.set('status', query.status);
  if (query.keyword) params.set('keyword', query.keyword);
  const qs = params.toString();
  const path = `/api/v1/projects/my${qs ? `?${qs}` : ''}`;
  return requestEnvelope(path, { accessToken });
}

/** 项目详情 GET /api/v1/projects/{uuid}（编辑弹窗预填） */
export async function fetchProjectDetail(
  accessToken: string,
  projectId: string,
): Promise<DcEnvelope<DcProjectDetail>> {
  const id = projectId.trim();
  if (!id) throw new Error('缺少项目 ID');
  return requestEnvelope<DcProjectDetail>(`/api/v1/projects/${encodeURIComponent(id)}`, {
    accessToken,
  });
}

export async function registerToClawManager(input: {
  username: string;
  password: string;
  email?: string;
}): Promise<RegisterResponse> {
  return request<RegisterResponse>('/api/v1/auth/register', {
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
  const base = endpoint.endsWith('/') ? endpoint : `${endpoint}/`;
  const url =
    access.protocol === 'aida'
      ? new URL(cleanPath, base)
      : new URL(`/chat/${cleanPath}`, endpoint);
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

async function requestEnvelope<T>(
  path: string,
  init: RequestInit & { accessToken?: string } = {},
): Promise<DcEnvelope<T>> {
  const payload = await request<DcEnvelope<T> | T>(path, init);
  if (payload && typeof payload === 'object' && 'code' in payload && 'data' in payload) {
    const env = payload as DcEnvelope<T>;
    if (env.code !== 0) {
      throw new Error(env.message || '请求失败');
    }
    return env;
  }
  return { code: 0, message: 'success', data: payload as T };
}

async function errorMessage(resp: Response): Promise<string> {
  try {
    const data = await resp.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((item: { msg?: string }) => item?.msg || String(item)).join('; ');
    }
    if (data?.message && data?.code !== undefined && data.code !== 0) {
      return String(data.message);
    }
    if (resp.status === 401) return '用户名或密码错误';
    if (resp.status === 403) return '无权访问该项目';
    return `${resp.status} ${resp.statusText}`;
  } catch {
    if (resp.status === 401) return '用户名或密码错误';
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
