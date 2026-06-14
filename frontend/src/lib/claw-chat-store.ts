/**
 * ClawRail 对话会话 · 按路由隔离 + sessionStorage 持久化
 *
 * 切换页面时保留各路由独立对话；返回同一路由时恢复历史。
 * 交付预案等页面可附加 projectScope（通常为项目名称）按项目隔离会话。
 * 不影响 aida:progress / aida:proposal-reveal-* 等交付预案章节加载事件。
 */
import { useSyncExternalStore } from 'react';

export interface StoredClawMsg {
  role: 'user' | 'ai';
  body: string;
  ts: string;
  chips?: string[];
  reasoning?: Array<{ ix: string; text: string }>;
  actions?: Array<{ label: string; kind: string; icon?: string }>;
  toolEvents?: Array<{
    name: string;
    args?: Record<string, unknown>;
    result?: string;
  }>;
  skillLaunch?: {
    skill: string;
    projectCode: string;
    scenarioRun: string;
    steps: Array<{ step: string; name: string }>;
  };
  skillRun?: { skillId: string };
  choiceCard?: {
    question: string;
    options: Array<{ label: string; value?: string }>;
  };
  pendingApproval?: {
    approval_id: string;
    name: string;
    args: Record<string, unknown>;
    decided?: 'approved' | 'denied';
  };
}

export interface ClawChatSession {
  msgs: StoredClawMsg[];
  convId: string;
}

const STORAGE_KEY = 'aida:claw-chat-by-route';
const memory = new Map<string, ClawChatSession>();
let snapshotVersion = 0;
const listeners = new Set<() => void>();

function notify() {
  snapshotVersion += 1;
  listeners.forEach((l) => l());
}

function routeKey(pathname: string): string {
  return (pathname.split('?')[0] || '/').trim() || '/';
}

/** 会话存储键：路由 + 可选项目范围（如交付预案按项目名称） */
export function clawChatSessionKey(pathname: string, projectScope?: string | null): string {
  const route = routeKey(pathname);
  const scope = projectScope?.trim();
  return scope ? `${route}::${scope}` : route;
}

export function genClawConvId(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? `conv-${crypto.randomUUID()}`
    : `conv-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function emptySession(): ClawChatSession {
  return { msgs: [], convId: genClawConvId() };
}

function readStorage(): Record<string, ClawChatSession> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, ClawChatSession>;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeStorage(all: Record<string, ClawChatSession>) {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  } catch {
    /* quota / private mode */
  }
}

function sanitizeMsgs(msgs: StoredClawMsg[]): StoredClawMsg[] {
  return msgs
    .filter((m) => m.body || (m.toolEvents?.length ?? 0) > 0 || m.choiceCard || m.pendingApproval)
    .map((m) => {
      const { ...rest } = m;
      return rest;
    });
}

export function loadClawChatSession(pathname: string, projectScope?: string | null): ClawChatSession {
  const key = clawChatSessionKey(pathname, projectScope);
  const cached = memory.get(key);
  if (cached) return cached;

  const fromStorage = readStorage()[key];
  if (fromStorage?.convId) {
    const session: ClawChatSession = {
      convId: fromStorage.convId,
      msgs: sanitizeMsgs(fromStorage.msgs ?? []),
    };
    memory.set(key, session);
    return session;
  }

  const session = emptySession();
  memory.set(key, session);
  return session;
}

export function saveClawChatSession(
  pathname: string,
  session: ClawChatSession,
  projectScope?: string | null,
): void {
  const key = clawChatSessionKey(pathname, projectScope);
  const normalized: ClawChatSession = {
    convId: session.convId || genClawConvId(),
    msgs: sanitizeMsgs(session.msgs ?? []),
  };
  memory.set(key, normalized);

  const all = readStorage();
  all[key] = normalized;
  writeStorage(all);

  // 评测页等仍读取全局 conv id
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem('aida-conv-id', normalized.convId);
    } catch {
      /* ignore */
    }
  }
  notify();
}

export function clearClawChatSession(pathname: string, projectScope?: string | null): void {
  const key = clawChatSessionKey(pathname, projectScope);
  memory.delete(key);
  const all = readStorage();
  delete all[key];
  writeStorage(all);
  notify();
}

export function useClawChatSession(pathname: string, projectScope?: string | null): ClawChatSession {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => loadClawChatSession(pathname, projectScope),
    () => emptySession(),
  );
}

export function getClawChatStoreVersion(): number {
  return snapshotVersion;
}
