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
import {
  buildProjectDataContext,
  clearDraftRaci,
  getStoredVersions,
  loadAcceptance,
  loadCardScale,
  loadPlan,
  loadRaciMatrix,
  applyTestCasesFromUpload,
  loadTestCasesIfReady,
  saveAcceptanceTable,
  saveRaciTable,
  saveTestCasesTable,
  setAcceptanceCache,
  setDraftRaci,
  setStoredVersions,
  testCaseKey,
} from '@/lib/proposal-data-service';

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
  updateRaci: (rows: RaciRow[]) => void;
  setSelectedTc: (keys: Set<string>) => void;
  refreshAcceptance: (items: AcceptanceItem[]) => void;
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
      projectCode: project.code,
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

  const loadAll = useCallback(async () => {
    if (!projectCtx) {
      console.warn('[AIDA DC] loadAll skipped: no projectCtx', {
        projectId: project?.id,
        projectName: project?.name,
        hasToken: Boolean(session?.accessToken),
      });
      setLoading(false);
      return;
    }
    console.info('[AIDA DC] loadAll start', {
      projectId: projectCtx.dcProjectId,
      projectName: projectCtx.projectName,
      projectCode: projectCtx.projectCode,
      hasToken: Boolean(projectCtx.token),
    });
    setLoading(true);
    try {
      const syncResult = await syncProposalLocalFiles(projectCtx);
      if (syncResult.warnings.length) {
        setDataWarnings(syncResult.warnings);
      }
      const stored = getStoredVersions(projectName);
      const scale = await loadCardScale(projectCtx);
      const [raci, plan, accept, tcLoaded] = await Promise.all([
        loadRaciMatrix(projectCtx),
        loadPlan(projectCtx),
        loadAcceptance(projectCtx),
        loadTestCasesIfReady(projectCtx, scale),
      ]);
      setCardScale(scale);
      setRaciRows(raci.rows);
      setVersions({
        raci: raci.version || stored.raci,
        acceptance: stored.acceptance,
        testCases: stored.testCases,
      });
      setPlanRows(plan);
      setAcceptanceItems(accept);
      setTestCases(tcLoaded.cases);
      setSelectedTcKeys(
        tcLoaded.selectedKeys ?? new Set(tcLoaded.cases.map((c, i) => tcKey(c, i))),
      );
      console.info('[AIDA DC] loadAll done', {
        raciRows: raci.rows.length,
        planRows: plan.length,
        acceptanceItems: accept.length,
        testCases: tcLoaded.cases.length,
      });
    } catch (err) {
      console.error('[AIDA DC] loadAll failed', err);
    } finally {
      setLoading(false);
    }
  }, [projectCtx, projectName, project?.id, project?.name, session?.accessToken]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

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
    const onParsed = (e: Event) => {
      const detail = (e as CustomEvent<{ rows?: AcceptanceItem[] }>).detail;
      if (detail?.rows?.length) {
        setAcceptanceItems(detail.rows);
        setAcceptanceCache(projectName, detail.rows);
      }
    };
    window.addEventListener('aida:proposal-acceptance-parsed', onParsed);
    return () => window.removeEventListener('aida:proposal-acceptance-parsed', onParsed);
  }, [projectName]);

  useEffect(() => {
    const onTcParsed = (e: Event) => {
      const detail = (e as CustomEvent<{ rows?: unknown[] }>).detail;
      if (!detail?.rows) return;
      const cases = applyTestCasesFromUpload(projectName, detail.rows, cardScale);
      setTestCases(cases);
      setSelectedTcKeys(new Set(cases.map((c, i) => tcKey(c, i))));
      setDirty(true);
    };
    window.addEventListener('aida:proposal-testcases-parsed', onTcParsed);
    return () => window.removeEventListener('aida:proposal-testcases-parsed', onTcParsed);
  }, [projectName, cardScale]);

  const updateRaci = useCallback((rows: RaciRow[]) => {
    setRaciRows(rows);
    setDraftRaci(projectName, rows);
    setDirty(true);
  }, [projectName]);

  const setSelectedTc = useCallback((keys: Set<string>) => {
    setSelectedTcKeys(keys);
    setDirty(true);
  }, []);

  const refreshAcceptance = useCallback((items: AcceptanceItem[]) => {
    setAcceptanceItems(items.length ? items : acceptanceItems);
    setAcceptanceCache(projectName, items);
    setDirty(true);
  }, [projectName, acceptanceItems]);

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

    await Promise.all([
      saveRaciTable(projectCtx, raciRows, next.raci),
      saveAcceptanceTable(projectCtx, acceptanceItems, next.acceptance),
      saveTestCasesTable(projectCtx, testCases, selectedTcKeys, tcKey, next.testCases),
    ]);

    setStoredVersions(projectName, next);
    setVersions(next);
    clearDraftRaci(projectName);
    setDirty(false);
  }, [projectCtx, projectName, raciRows, acceptanceItems, testCases, selectedTcKeys, versions]);

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
    updateRaci,
    setSelectedTc,
    refreshAcceptance,
    saveDraftTables,
    saveAndConfirmTables,
    setDirty,
    reload: loadAll,
  }), [
    projectCtx, projectName, loading, dirty, dataWarnings, raciRows, planRows,
    acceptanceItems, testCases, selectedTcKeys, versions, cardScale,
    updateRaci, setSelectedTc, refreshAcceptance, saveDraftTables, saveAndConfirmTables, loadAll,
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
