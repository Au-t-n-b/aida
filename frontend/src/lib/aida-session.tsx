import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  loginToClawManager,
  logoutFromClawManager,
  requestChatAccess,
  type ChatAccessResponse,
} from './claw-manager-client';

type AidaSessionState = {
  accessToken: string;
  sessionId: string;
  role: string;
  containerEndpoint?: string | null;
  chatAccess?: ChatAccessResponse | null;
};

type AidaSessionContextValue = {
  session: AidaSessionState | null;
  login: (username: string, password: string, projectCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  logoutLocal: () => void;
  getChatAccess: () => Promise<ChatAccessResponse>;
};

const STORAGE_KEY = 'aida:session';
const DEFAULT_PROJECT = 'K1903';
const AidaSessionContext = createContext<AidaSessionContextValue | null>(null);

export function AidaSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AidaSessionState | null>(() => readStoredSession());

  const login = useCallback(async (username: string, password: string, projectCode = DEFAULT_PROJECT) => {
    let next: AidaSessionState;
    try {
      const resp = await loginToClawManager({
        username,
        password,
        project_code: projectCode,
      });
      next = {
        accessToken: resp.access_token,
        sessionId: resp.session_id,
        role: resp.role,
        containerEndpoint: resp.container_endpoint,
        chatAccess: null,
      };
    } catch (err) {
      // ClawManager 鉴权服务不可达（本地 / 演示环境没有 8000 端口的后端）时退化为本地演示会话，
      // 让登录在无后端的情况下也能进入。真实鉴权失败（HTTP 4xx/5xx）不是网络错误，仍照常抛出。
      if (!isNetworkError(err)) throw err;
      console.warn('[AIDA] ClawManager 不可达，已使用本地演示会话登录', err);
      next = buildDemoSession(username, projectCode);
    }
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
    if (session) {
      await logoutFromClawManager({
        accessToken: session.accessToken,
        sessionId: session.sessionId,
      });
    }
    setSession(null);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem(STORAGE_KEY);
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

  const value = useMemo(
    () => ({ session, login, logout, logoutLocal, getChatAccess }),
    [session, login, logout, logoutLocal, getChatAccess],
  );

  return <AidaSessionContext.Provider value={value}>{children}</AidaSessionContext.Provider>;
}

export function useAidaSession(): AidaSessionContextValue {
  const ctx = useContext(AidaSessionContext);
  if (!ctx) throw new Error('useAidaSession must be used within AidaSessionProvider');
  return ctx;
}

function isNetworkError(err: unknown): boolean {
  // fetch() 在连接被拒绝 / 服务未启动时抛 TypeError（"Failed to fetch" / "Load failed" /
  // "NetworkError…"）。我们自己的 HTTP 错误经 errorMessage() 包装成普通 Error，不是 TypeError，
  // 因此用 instanceof 即可把「后端不可达」与「真实鉴权失败」区分开。
  return err instanceof TypeError;
}

function buildDemoSession(username: string, projectCode: string): AidaSessionState {
  const who = username.trim() || 'demo';
  return {
    accessToken: `demo-${projectCode}`,
    sessionId: `demo-${projectCode}-${who}`,
    role: 'demo',
    containerEndpoint: null,
    chatAccess: null,
  };
}

function readStoredSession(): AidaSessionState | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AidaSessionState) : null;
  } catch {
    return null;
  }
}

function storeSession(session: AidaSessionState): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}
