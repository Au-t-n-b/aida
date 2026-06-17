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
  /** 兼容旧字段：可能是项目编码，也可能是 Proposal ID。新代码优先用 projectCode/proposalId。 */
  code?: string;
  projectCode?: string;
  proposalId?: string;
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

import { DEFAULT_PROJECT_NAME } from '@/data/project-paths';
import { PROJECT_LIST_MINI } from '@/data/topbar-projects';

/** 启动 Agent run 时写入 project 的项目名 / 编码（与 TopBar 当前项目对齐）。 */
export function resolveAgentStartProject(
  project: CurrentProject | null,
): { project_name: string; project_code: string } {
  const fallback = PROJECT_LIST_MINI[0];
  const name = (project?.name || fallback?.name || DEFAULT_PROJECT_NAME).trim();
  const code = (
    project?.projectCode
    || project?.code
    || project?.id
    || fallback?.id
    || 'K1903'
  ).trim();
  return { project_name: name, project_code: code };
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
