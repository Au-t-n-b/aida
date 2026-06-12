import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

/** 当前工作区选中的项目（id 为业务短码如 K1903，或数据中心 projectId UUID32）。 */
export type CurrentProject = {
  id: string;
  name: string;
  code?: string;
};

type CurrentProjectContextValue = {
  project: CurrentProject | null;
  selectProject: (next: CurrentProject) => void;
  clearCurrentProject: () => void;
};

const STORAGE_KEY = 'aida:current-project';
const CurrentProjectContext = createContext<CurrentProjectContextValue | null>(null);

export function CurrentProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProject] = useState<CurrentProject | null>(() => readStoredProject());

  const selectProject = useCallback((next: CurrentProject) => {
    setProject(next);
    storeProject(next);
  }, []);

  const clearCurrentProject = useCallback(() => {
    setProject(null);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const value = useMemo(
    () => ({ project, selectProject, clearCurrentProject }),
    [project, selectProject, clearCurrentProject],
  );

  return (
    <CurrentProjectContext.Provider value={value}>{children}</CurrentProjectContext.Provider>
  );
}

export function useCurrentProject(): CurrentProjectContextValue {
  const ctx = useContext(CurrentProjectContext);
  if (!ctx) throw new Error('useCurrentProject must be used within CurrentProjectProvider');
  return ctx;
}

/** 从编码字段推导业务短 id（如 PROP-2026-K1903 → K1903）。 */
export function deriveProjectId(
  code?: string,
  proposal?: string,
  fallback?: string,
): string {
  const raw = (code || proposal || '').trim();
  if (!raw) return fallback ?? `draft-${Date.now()}`;
  const tail = raw.match(/-([A-Za-z0-9]+)$/);
  if (tail?.[1]) return tail[1];
  return raw;
}

function readStoredProject(): CurrentProject | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as CurrentProject) : null;
  } catch {
    return null;
  }
}

function storeProject(project: CurrentProject): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(project));
}
