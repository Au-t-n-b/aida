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
    const resp = await loginToClawManager({
      username,
      password,
      project_code: projectCode,
    });
    const next: AidaSessionState = {
      accessToken: resp.access_token,
      sessionId: resp.session_id,
      role: resp.role,
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
