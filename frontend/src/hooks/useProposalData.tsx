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
import type {
  AcceptanceItem,
  AcceptanceTestCase,
  PlanActivity,
  ProposalTableVersions,
  RaciRow,
} from '@/types/domain';
import {
  clearDraftRaci,
  getStoredVersions,
  loadAcceptance,
  loadCardScale,
  loadPlan,
  loadRaciMatrix,
  applyTestCasesFromUpload,
  loadTestCasesIfReady,
  PROPOSAL_PROJECT_NAME,
  saveAcceptanceTable,
  saveRaciTable,
  saveTestCasesTable,
  setAcceptanceCache,
  setDraftRaci,
  setStoredVersions,
} from '@/lib/proposal-data-service';

export interface ProposalDataContextValue {
  projectName: string;
  loading: boolean;
  dirty: boolean;
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
  saveDraft: () => Promise<void>;
  saveAndConfirm: () => Promise<void>;
  setDirty: (v: boolean) => void;
}

const ProposalDataContext = createContext<ProposalDataContextValue | null>(null);

function tcKey(c: AcceptanceTestCase, i: number): string {
  return `tc-${c.id}-${i}`;
}

export function ProposalDataProvider({ children }: { children: ReactNode }) {
  const projectName = PROPOSAL_PROJECT_NAME;
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [raciRows, setRaciRows] = useState<RaciRow[]>([]);
  const [planRows, setPlanRows] = useState<PlanActivity[]>([]);
  const [acceptanceItems, setAcceptanceItems] = useState<AcceptanceItem[]>([]);
  const [testCases, setTestCases] = useState<AcceptanceTestCase[]>([]);
  const [selectedTcKeys, setSelectedTcKeys] = useState<Set<string>>(new Set());
  const [versions, setVersions] = useState<ProposalTableVersions>({ raci: 0, acceptance: 0, testCases: 0 });
  const [cardScale, setCardScale] = useState(384);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const stored = getStoredVersions(projectName);
      const scale = await loadCardScale();
      const [raci, plan, accept, cases] = await Promise.all([
        loadRaciMatrix(projectName),
        loadPlan(projectName),
        loadAcceptance(projectName),
        loadTestCasesIfReady(projectName, scale),
      ]);
      if (cancelled) return;
      setCardScale(scale);
      setRaciRows(raci.rows);
      setVersions({
        raci: raci.version || stored.raci,
        acceptance: stored.acceptance,
        testCases: stored.testCases,
      });
      setPlanRows(plan);
      setAcceptanceItems(accept);
      setTestCases(cases);
      setSelectedTcKeys(new Set(cases.map((c, i) => tcKey(c, i))));
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [projectName]);

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
      saveRaciTable(projectName, raciRows, next.raci),
      saveAcceptanceTable(projectName, acceptanceItems, next.acceptance),
      saveTestCasesTable(projectName, testCases, selectedTcKeys, tcKey, next.testCases),
    ]);

    setStoredVersions(projectName, next);
    setVersions(next);
    clearDraftRaci(projectName);
    setDirty(false);
  }, [projectName, raciRows, acceptanceItems, testCases, selectedTcKeys, versions]);

  const saveDraft = useCallback(() => persistAll(false), [persistAll]);
  const saveAndConfirm = useCallback(() => persistAll(true), [persistAll]);

  const value = useMemo<ProposalDataContextValue>(() => ({
    projectName,
    loading,
    dirty,
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
    saveDraft,
    saveAndConfirm,
    setDirty,
  }), [
    projectName, loading, dirty, raciRows, planRows, acceptanceItems,
    testCases, selectedTcKeys, versions, cardScale,
    updateRaci, setSelectedTc, refreshAcceptance, saveDraft, saveAndConfirm,
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
