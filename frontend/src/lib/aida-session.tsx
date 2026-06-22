import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  loginToClawManager,
  logoutFromClawManager,
  requestChatAccess,
  enterProject,
  sessionHeartbeat,
  waitContainerReady,
  type ChatAccessResponse,
  type ClawUserProfile,
  type EnterProjectResponse,
} from './claw-manager-client';

export type AidaSessionState = {
  /** 数据中心 Bearer token，后续 API 统一携带 */
  accessToken: string;
  tokenType: string;
  sessionId: string;
  role: string;
  user: ClawUserProfile | null;
  expiresAt?: number | null;
  containerEndpoint?: string | null;
  chatAccess?: ChatAccessResponse | null;
};

type AidaSessionContextValue = {
  session: AidaSessionState | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  logoutLocal: () => void;
  getChatAccess: () => Promise<ChatAccessResponse>;
  enterProject: (projectId: string, projectCode?: string) => Promise<EnterProjectResponse>;
};

const STORAGE_KEY = 'aida:session';
const PROJECT_STORAGE_KEY = 'aida:current-project';
const HEARTBEAT_IN_PROJECT_MS = 60 * 1000;
const HEARTBEAT_IDLE_MS = 5 * 60 * 1000;
const AidaSessionContext = createContext<AidaSessionContextValue | null>(null);

export function AidaSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AidaSessionState | null>(() => readStoredSession());

  const login = useCallback(async (username: string, password: string) => {
    const resp = await loginToClawManager({ username, password });
    const expiresAt = resp.expires_in
      ? Date.now() + resp.expires_in * 1000
      : null;
    const next: AidaSessionState = {
      accessToken: resp.access_token,
      tokenType: resp.token_type || 'Bearer',
      sessionId: resp.session_id,
      role: resp.role,
      user: resp.user ?? null,
      expiresAt,
      containerEndpoint: resp.container_endpoint,
      chatAccess: null,
    };
    setSession(next);
    storeSession(next);
  }, []);

  const logoutLocal = useCallback(() => {
    setSession(null);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const logout = useCallback(async () => {
    const current = session;
    try {
      if (current) {
        await logoutFromClawManager({
          accessToken: current.accessToken,
          sessionId: current.sessionId,
        });
      }
    } finally {
      setSession(null);
      if (typeof window !== 'undefined') {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    }
  }, [session]);

  const getChatAccess = useCallback(async () => {
    if (!session) {
      throw new Error('请先登录 AIDA');
    }
    const cached = session.chatAccess;
    if (cached && cached.expires_at * 1000 > Date.now() + 30_000) {
      return cached;
    }
    const access = await requestChatAccess({
      accessToken: session.accessToken,
      sessionId: session.sessionId,
    });
    const next = { ...session, chatAccess: access };
    setSession(next);
    storeSession(next);
    return access;
  }, [session]);

  const enterProjectForSession = useCallback(
    async (projectId: string, projectCode?: string) => {
      if (!session) {
        throw new Error('请先登录 AIDA');
      }
      const resp = await enterProject({
        accessToken: session.accessToken,
        sessionId: session.sessionId,
        projectId,
        projectCode,
      });
      if (!resp.container_ready) {
        await waitContainerReady({
          accessToken: session.accessToken,
          sessionId: session.sessionId,
        });
      }
      const next: AidaSessionState = {
        ...session,
        containerEndpoint: resp.container_endpoint,
        chatAccess: null,
      };
      setSession(next);
      storeSession(next);
      return resp;
    },
    [session],
  );

  useEffect(() => {
    if (!session?.sessionId || !session.accessToken) return undefined;
    const tick = () => {
      const project = readStoredProjectSnapshot();
      void sessionHeartbeat({
        accessToken: session.accessToken,
        sessionId: session.sessionId,
        projectId: project?.id,
        projectCode: project?.projectCode || project?.code,
      }).then((hb) => {
        if (hb.container_endpoint) {
          setSession((prev) => {
            if (!prev || prev.containerEndpoint === hb.container_endpoint) return prev;
            const next = { ...prev, containerEndpoint: hb.container_endpoint };
            storeSession(next);
            return next;
          });
        }
      }).catch(() => {
        // 心跳失败不打断作业
      });
    };
    tick();
    const intervalMs = readStoredProjectSnapshot()?.id || session.containerEndpoint
      ? HEARTBEAT_IN_PROJECT_MS
      : HEARTBEAT_IDLE_MS;
    const id = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(id);
  }, [session?.sessionId, session?.accessToken, session?.containerEndpoint]);

  const value = useMemo(
    () => ({
      session,
      login,
      logout,
      logoutLocal,
      getChatAccess,
      enterProject: enterProjectForSession,
    }),
    [session, login, logout, logoutLocal, getChatAccess, enterProjectForSession],
  );

  return <AidaSessionContext.Provider value={value}>{children}</AidaSessionContext.Provider>;
}

export function useAidaSession(): AidaSessionContextValue {
  const ctx = useContext(AidaSessionContext);
  if (!ctx) throw new Error('useAidaSession must be used within AidaSessionProvider');
  return ctx;
}

function readStoredSession(): AidaSessionState | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AidaSessionState>;
    if (!parsed.accessToken || !parsed.sessionId) return null;
    return {
      accessToken: parsed.accessToken,
      tokenType: parsed.tokenType || 'Bearer',
      sessionId: parsed.sessionId,
      role: parsed.role || 'user',
      user: parsed.user ?? null,
      expiresAt: parsed.expiresAt ?? null,
      containerEndpoint: parsed.containerEndpoint ?? null,
      chatAccess: parsed.chatAccess ?? null,
    };
  } catch {
    return null;
  }
}

function storeSession(session: AidaSessionState): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

type ProjectSnapshot = { id: string; code?: string; projectCode?: string };

function readStoredProjectSnapshot(): ProjectSnapshot | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(PROJECT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ProjectSnapshot>;
    if (!parsed.id?.trim()) return null;
    return {
      id: parsed.id.trim(),
      code: parsed.code,
      projectCode: parsed.projectCode,
    };
  } catch {
    return null;
  }
}
