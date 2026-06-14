'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useAidaSession } from '@/lib/aida-session';
import { useCurrentProject } from '@/lib/current-project';
import type {
  AcceptanceItem,
  AcceptanceTestCase,
  PlanActivity,
  ProposalTableVersions,
  RaciRow,
} from '@/types/domain';
import type { ProjectDataContext } from '@/lib/datacenter/types';
import { syncProposalLocalFiles } from '@/lib/datacenter/client';
import { DEFAULT_PROJECT_ROOT } from '@/data/project-paths';
import {
  buildProjectDataContext,
  clearDraftRaci,
  getStoredVersions,
  isTechProposalUploaded,
  isTestCasesUploaded,
  loadAcceptance,
  loadCardScale,
  loadPlan,
  loadRaciMatrix,
  loadTestCasesIfReady,
  reloadAcceptanceFromXlsx,
  reloadTestCasesFromXlsx,
  saveAcceptanceTable,
  saveRaciTable,
  saveTestCasesTable,
  setAcceptanceCache,
  setDraftRaci,
  setStoredVersions,
  setTestCasesSessionCache,
  testCaseKey,
} from '@/lib/proposal-data-service';
import { navDebug } from '@/lib/nav-debug';

export interface ProposalDataContextValue {
  projectCtx: ProjectDataContext | null;
  projectName: string;
  loading: boolean;
  dirty: boolean;
  dataWarnings: string[];
  raciRows: RaciRow[];
  planRows: PlanActivity[];
  acceptanceItems: AcceptanceItem[];
  testCases: AcceptanceTestCase[];
  selectedTcKeys: Set<string>;
  versions: ProposalTableVersions;
  cardScale: number;
  acceptanceReady: boolean;
  testCasesReady: boolean;
  updateRaci: (rows: RaciRow[]) => void;
  setSelectedTc: (keys: Set<string>) => void;
  updateTestCaseSelection: (keys: Set<string>) => void;
  refreshAcceptance: (items: AcceptanceItem[]) => void;
  refreshTestCases: (cases: AcceptanceTestCase[], selectedKeys?: Set<string>) => void;
  saveDraftTables: () => Promise<void>;
  saveAndConfirmTables: () => Promise<void>;
  setDirty: (v: boolean) => void;
  reload: () => Promise<void>;
}

const ProposalDataContext = createContext<ProposalDataContextValue | null>(null);

function tcKey(c: AcceptanceTestCase, i: number): string {
  return testCaseKey(c, i);
}

export function ProposalDataProvider({ children }: { children: ReactNode }) {
  const { session } = useAidaSession();
  const { project } = useCurrentProject();

  const projectCtx = useMemo<ProjectDataContext | null>(() => {
    if (!project?.id) return null;
    return buildProjectDataContext({
      token: session?.accessToken,
      dcProjectId: project.id,
      projectName: project.name,
      projectCode: DEFAULT_PROJECT_ROOT,
    });
  }, [project?.id, project?.name, project?.code, session?.accessToken]);

  const projectName = project?.name ?? '';

  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [dataWarnings, setDataWarnings] = useState<string[]>([]);
  const [raciRows, setRaciRows] = useState<RaciRow[]>([]);
  const [planRows, setPlanRows] = useState<PlanActivity[]>([]);
  const [acceptanceItems, setAcceptanceItems] = useState<AcceptanceItem[]>([]);
  const [testCases, setTestCases] = useState<AcceptanceTestCase[]>([]);
  const [selectedTcKeys, setSelectedTcKeys] = useState<Set<string>>(new Set());
  const [versions, setVersions] = useState<ProposalTableVersions>({ raci: 0, acceptance: 0, testCases: 0 });
  const [cardScale, setCardScale] = useState(384);
  const [acceptanceReady, setAcceptanceReady] = useState(false);
  const [testCasesReady, setTestCasesReady] = useState(false);

  const loadAll = useCallback(async (isCancelled?: () => boolean) => {
    if (!projectCtx) {
      if (!isCancelled?.()) setLoading(false);
      return;
    }
    if (!isCancelled?.()) setLoading(true);
    navDebug('proposal-data loadAll start', { projectName });
    try {
      const syncResult = await syncProposalLocalFiles(projectCtx);
      if (isCancelled?.()) return;
      if (syncResult.warnings.length) {
        setDataWarnings(syncResult.warnings);
      }
      const stored = getStoredVersions(projectName);
      const [raci, plan, scale] = await Promise.all([
        loadRaciMatrix(projectCtx),
        loadPlan(projectCtx),
        loadCardScale(projectCtx),
      ]);
      if (isCancelled?.()) return;
      setCardScale(scale);
      setRaciRows(raci.rows);
      setVersions({
        raci: raci.version || stored.raci,
        acceptance: stored.acceptance,
        testCases: stored.testCases,
      });
      setPlanRows(plan);

      if (isTechProposalUploaded(projectName)) {
        const items = await loadAcceptance(projectCtx);
        if (isCancelled?.()) return;
        setAcceptanceItems(items);
        setAcceptanceReady(items.length > 0);
      } else {
        setAcceptanceItems([]);
        setAcceptanceReady(false);
      }

      if (isTestCasesUploaded(projectName)) {
        const loaded = await loadTestCasesIfReady(projectCtx, scale);
        if (isCancelled?.()) return;
        setTestCases(loaded.cases);
        setSelectedTcKeys(
          loaded.selectedKeys ?? new Set(loaded.cases.map((c, i) => tcKey(c, i))),
        );
        setTestCasesReady(loaded.cases.length > 0);
      } else {
        setTestCases([]);
        setSelectedTcKeys(new Set());
        setTestCasesReady(false);
      }
    } catch (err) {
      console.error('[AIDA DC] loadAll failed', err);
    } finally {
      if (!isCancelled?.()) {
        setLoading(false);
        navDebug('proposal-data loadAll done', { projectName });
      }
    }
  }, [projectCtx, projectName]);

  const revealAcceptance = useCallback(async () => {
    if (!projectCtx) return;
    const items = await reloadAcceptanceFromXlsx(projectCtx);
    setAcceptanceItems(items);
    setAcceptanceReady(true);
    setDirty(true);
  }, [projectCtx]);

  const revealTestCases = useCallback(async () => {
    console.info('[AIDA TC] claw reveal event received');
    if (!projectCtx) {
      console.warn('[AIDA TC] reveal aborted: no project context (请先选择项目)');
      return;
    }
    try {
      const loaded = await reloadTestCasesFromXlsx(projectCtx, cardScale);
      if (!loaded.cases.length) {
        console.warn('[AIDA TC] reveal finished but 0 cases — 第12章保持空态', {
          source: loaded.source,
          projectName,
        });
        setTestCases([]);
        setSelectedTcKeys(new Set());
        setTestCasesReady(false);
        return;
      }
      console.info('[AIDA TC] reveal success — 展示第12章', {
        caseCount: loaded.cases.length,
        source: loaded.source,
      });
      setTestCases(loaded.cases);
      setSelectedTcKeys(
        loaded.selectedKeys ?? new Set(loaded.cases.map((c, i) => tcKey(c, i))),
      );
      setTestCasesReady(true);
      setDirty(true);
    } catch (err) {
      console.error('[AIDA TC] reveal error', err);
    }
  }, [projectCtx, cardScale, projectName]);

  useEffect(() => {
    let cancelled = false;
    const isCancelled = () => cancelled;
    const run = async () => {
      await loadAll(isCancelled);
      if (cancelled) {
        navDebug('proposal-data loadAll aborted (unmounted)', { projectName });
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [loadAll, projectName]);

  useEffect(() => {
    const onFallback = (e: Event) => {
      const detail = (e as CustomEvent<{ warnings?: string[] }>).detail;
      if (detail?.warnings?.length) {
        setDataWarnings((prev) => [...prev, ...detail.warnings!]);
      }
    };
    window.addEventListener('aida:data-fallback', onFallback);
    return () => window.removeEventListener('aida:data-fallback', onFallback);
  }, []);

  useEffect(() => {
    const onRevealAcceptance = () => { void revealAcceptance(); };
    const onRevealTestCases = () => { void revealTestCases(); };
    window.addEventListener('aida:proposal-reveal-acceptance', onRevealAcceptance);
    window.addEventListener('aida:proposal-reveal-testcases', onRevealTestCases);
    return () => {
      window.removeEventListener('aida:proposal-reveal-acceptance', onRevealAcceptance);
      window.removeEventListener('aida:proposal-reveal-testcases', onRevealTestCases);
    };
  }, [revealAcceptance, revealTestCases]);

  const updateRaci = useCallback((rows: RaciRow[]) => {
    setRaciRows(rows);
    setDraftRaci(projectName, rows);
    setDirty(true);
  }, [projectName]);

  const setSelectedTc = useCallback((keys: Set<string>) => {
    setSelectedTcKeys(keys);
    if (testCases.length) {
      setTestCasesSessionCache(projectName, testCases, keys);
    }
    setDirty(true);
  }, [projectName, testCases]);

  const updateTestCaseSelection = useCallback((keys: Set<string>) => {
    setSelectedTcKeys(keys);
    if (testCases.length) {
      setTestCasesSessionCache(projectName, testCases, keys);
    }
    setDirty(true);
  }, [projectName, testCases]);

  const refreshAcceptance = useCallback((items: AcceptanceItem[]) => {
    setAcceptanceItems(items);
    setAcceptanceCache(projectName, items);
    setDirty(true);
  }, [projectName]);

  const refreshTestCases = useCallback((
    cases: AcceptanceTestCase[],
    selectedKeys?: Set<string>,
  ) => {
    const keys = selectedKeys ?? new Set(cases.map((c, i) => tcKey(c, i)));
    setTestCases(cases);
    setSelectedTcKeys(keys);
    if (cases.length) {
      setTestCasesSessionCache(projectName, cases, keys);
    }
    setDirty(true);
  }, [projectName]);

  const persistAll = useCallback(async (bumpVersion: boolean) => {
    if (!projectCtx) return;
    const cur = getStoredVersions(projectName);
    const next: ProposalTableVersions = {
      raci: bumpVersion ? Math.max(cur.raci, versions.raci) + 1 : Math.max(cur.raci, versions.raci) || 1,
      acceptance: bumpVersion ? Math.max(cur.acceptance, versions.acceptance) + 1 : Math.max(cur.acceptance, versions.acceptance) || 1,
      testCases: bumpVersion ? Math.max(cur.testCases, versions.testCases) + 1 : Math.max(cur.testCases, versions.testCases) || 1,
    };
    if (!bumpVersion && cur.raci === 0 && cur.acceptance === 0 && cur.testCases === 0) {
      next.raci = next.raci || 1;
      next.acceptance = next.acceptance || 1;
      next.testCases = next.testCases || 1;
    }

    const saves: Promise<void>[] = [
      saveRaciTable(projectCtx, raciRows, next.raci),
    ];
    if (acceptanceReady) {
      saves.push(saveAcceptanceTable(projectCtx, acceptanceItems, next.acceptance));
    }
    if (testCasesReady) {
      saves.push(saveTestCasesTable(projectCtx, testCases, selectedTcKeys, tcKey, next.testCases));
    }
    await Promise.all(saves);

    setStoredVersions(projectName, next);
    setVersions(next);
    clearDraftRaci(projectName);
    setDirty(false);
  }, [
    projectCtx, projectName, raciRows, acceptanceItems, testCases,
    selectedTcKeys, versions, acceptanceReady, testCasesReady,
  ]);

  const saveDraftTables = useCallback(() => persistAll(false), [persistAll]);
  const saveAndConfirmTables = useCallback(() => persistAll(true), [persistAll]);

  const value = useMemo<ProposalDataContextValue>(() => ({
    projectCtx,
    projectName,
    loading,
    dirty,
    dataWarnings,
    raciRows,
    planRows,
    acceptanceItems,
    testCases,
    selectedTcKeys,
    versions,
    cardScale,
    acceptanceReady,
    testCasesReady,
    updateRaci,
    setSelectedTc,
    updateTestCaseSelection,
    refreshAcceptance,
    refreshTestCases,
    saveDraftTables,
    saveAndConfirmTables,
    setDirty,
    reload: loadAll,
  }), [
    projectCtx, projectName, loading, dirty, dataWarnings, raciRows, planRows,
    acceptanceItems, testCases, selectedTcKeys, versions, cardScale,
    acceptanceReady, testCasesReady,
    updateRaci, setSelectedTc, updateTestCaseSelection, refreshAcceptance, refreshTestCases,
    saveDraftTables, saveAndConfirmTables, loadAll,
  ]);

  return (
    <ProposalDataContext.Provider value={value}>
      {children}
    </ProposalDataContext.Provider>
  );
}

export function useProposalData(): ProposalDataContextValue {
  const ctx = useContext(ProposalDataContext);
  if (!ctx) throw new Error('useProposalData must be used within ProposalDataProvider');
  return ctx;
}

export { tcKey };
