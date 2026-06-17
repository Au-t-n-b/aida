'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AcceptanceChapter } from './chapters/acceptance-chapter';
import { CustomerChapterWrapper } from './chapters/customer-chapter';
import { DeviceChapter } from './chapters/device-chapter';
import { IntegrationChapter } from './chapters/integration-chapter';
import { MetaChapter } from './chapters/meta-chapter';
import { NetworkChapterWrapper } from './chapters/network-chapters';
import { PartsChapter } from './chapters/parts-chapter';
import { PlanChapter } from './chapters/plan-chapter';
import { RaciChapter } from './chapters/raci-chapter';
import { RoomChapter } from './chapters/room-chapter';
import { ServiceChapterWrapper } from './chapters/service-chapters';
import { SoftwareChapter } from './chapters/software-chapter';
import { TestCaseChapter } from './chapters/test-case-chapter';
import { CHAPTERS_BY_SNAP, SNAP_ALIASES, SNAPSHOTS, type SnapKey } from './proposal-data';
import type { AcceptanceItem, RaciRow } from '@/types/domain';
import { useProposalData, tcKey } from '@/hooks/useProposalData';
import {
  anchorToChapterKey,
  CHAPTER_TARGETS,
  PROPOSAL_OBSERVE_ANCHORS,
  readUrlParam,
} from './proposal-navigation';
import { ProposalOutlineRail } from './proposal-outline-rail';
import { VersionDropdown } from './proposal-version-dropdown';
import {
  exportDocument,
  fetchDraft,
  fetchVersionSnapshot,
  fetchVersions,
  formatProposalDateTime,
  getDefaultProjectId,
  loadChangeLogForDraft,
  loadChangeLogThroughVersion,
  manualLogToChangeRecords,
  ProposalApiError,
  releaseAndDecide,
  resolveVersionInfoMetadata,
  saveDraft,
  proposalApi,
  roomRackApi,
  useProposalApiHeaders,
  type CumulativeChangeEntry,
  type DraftManifest,
  type ManifestActivity,
  type ProposalVersionItem,
  type VersionInfoMetadata,
} from '@/lib/proposal-api';
import { navDebug } from '@/lib/nav-debug';
import { workspaceNavigate } from '@/lib/workspace-nav-link';
import { requestTwinAutoBuild } from '@/lib/twin-phase';
import { useCurrentProject } from '@/lib/current-project';
import { resolveTopBarProjectDisplayName } from '@/data/topbar-projects';

const DEFAULT_MANIFEST: DraftManifest = {
  workingVersionLabel: '草稿',
  status: 'draft',
};

const DEFAULT_METADATA: VersionInfoMetadata = {
  proposalVersion: '草稿',
  projectName: '京东三期项目',
};

/** API 未就绪时仍展示版本下拉（至少草稿一行） */
const FALLBACK_VERSIONS: ProposalVersionItem[] = [
  {
    proposalVersion: 'draft',
    status: 'draft',
    label: '草稿',
    tone: 'amber',
    isLatest: true,
    isEditable: true,
  },
];

function versionSortKey(version: string): string {
  const ts = version.match(/_(\d{14})(?:_|$)/)?.[1];
  return ts ?? version;
}

function pickDefaultVersion(versionList: ProposalVersionItem[]): string {
  const published = versionList.filter(
    (v) => v.status === 'published' && v.proposalVersion !== 'draft',
  );
  if (published.length === 0) return 'draft';
  const latestPublished = published.find((v) => v.isLatest);
  if (latestPublished?.proposalVersion) return latestPublished.proposalVersion;
  const sorted = [...published].sort((a, b) =>
    versionSortKey(a.proposalVersion).localeCompare(versionSortKey(b.proposalVersion)),
  );
  return sorted[sorted.length - 1]?.proposalVersion ?? 'draft';
}

export default function ProposalScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const { project } = useCurrentProject();
  const mountedRef = useRef(true);
  const headers = useProposalApiHeaders();
  const projectId = project?.id?.trim() || getDefaultProjectId();
  const {
    raciRows,
    planRows,
    acceptanceItems,
    testCases,
    selectedTcKeys,
    acceptanceReady,
    testCasesReady,
    updateRaci,
    refreshAcceptance,
    updateTestCaseSelection,
    saveDraftTables,
    saveAndConfirmTables,
    setDirty: setTableDirty,
  } = useProposalData();

  const [proposalVersion, setProposalVersion] = useState('draft');
  const [versions, setVersions] = useState<ProposalVersionItem[]>([]);
  const [manifest, setManifest] = useState<DraftManifest>(DEFAULT_MANIFEST);
  const [metadata, setMetadata] = useState<VersionInfoMetadata>(DEFAULT_METADATA);
  const [cumulativeLog, setCumulativeLog] = useState<CumulativeChangeEntry[]>([]);
  const [manualChangeLog, setManualChangeLog] = useState<CumulativeChangeEntry[]>([]);
  const [draftChapters, setDraftChapters] = useState<Record<string, unknown>>({});
  const [etag, setEtag] = useState<string | undefined>();
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [docToast, setDocToast] = useState<string | null>(null);

  const [snapKey, setSnapKey] = useState<SnapKey>('exec');
  const [activeChapterKey, setActiveChapterKey] = useState<string | null>(null);
  const [pendingTip, setPendingTip] = useState<{ num: string; panel: string } | null>(null);
  const [outlineCollapsed, setOutlineCollapsed] = useState(true);
  const [outlineHover, setOutlineHover] = useState(false);
  const [outlinePinned, setOutlinePinned] = useState(false);
  const [outlineHidden, setOutlineHidden] = useState(false);
  const saveInFlightRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    navDebug('proposal-screen mount', { pathname: location.pathname });
    return () => {
      mountedRef.current = false;
      navDebug('proposal-screen unmount', { pathname: location.pathname });
    };
  }, [location.pathname]);

  const isEditable = proposalVersion === 'draft';
  const outlineWide = !outlineCollapsed || outlineHover || outlinePinned;
  /** 页壳只等草稿/版本元数据；表格 slot 在后台加载，避免整页卡在「加载预案数据」 */
  const pageLoading = loading;

  const fireDocToast = useCallback((msg: string) => {
    setDocToast(msg);
    window.setTimeout(() => setDocToast(null), 2400);
  }, []);

  const handleManifestActivity = useCallback((activity: ManifestActivity) => {
    setMetadata((m) => ({
      ...m,
      ...(activity.updatedBy != null ? { updatedBy: activity.updatedBy } : {}),
      ...(activity.updatedAt != null ? { updatedAt: activity.updatedAt } : {}),
    }));
    if (activity.etag) setEtag(activity.etag);
  }, []);

  /** 保存草稿；若 etag 过期则拉取最新 manifest 后自动重试一次 */
  const saveDraftWithEtagRetry = useCallback(async () => {
    const buildSaveChapters = async (): Promise<Record<string, unknown>> => {
      const chapters = { ...draftChapters };
      try {
        const [netPlanes, netMgmt, clusterDevices, roomRack] = await Promise.all([
          proposalApi.listNetPlanes(),
          proposalApi.initializeNetMgmt(),
          proposalApi.listClusterDevices(),
          roomRackApi.list(),
        ]);
        chapters['5.1'] = {
          chapterKey: '5.1',
          chapterTitle: '5.1 网络平面配置',
          rows: (netPlanes.rows ?? []).map((r) => ({
            type: r.type,
            vendor: r.vendor,
            model: r.model,
            ver: r.ver,
            qty: r.qty,
            source: r.source,
            note: r.note ?? '',
          })),
        };
        chapters['5.2'] = {
          chapterKey: '5.2',
          chapterTitle: '5.2 网管服务器配置',
          rows: (netMgmt.rows ?? []).map((r) => ({
            serverRole: r.server_role,
            serverModel: r.server_model,
            quantity: r.quantity,
            dataSource: r.data_source,
          })),
        };
        chapters['7'] = {
          chapterKey: '7',
          chapterTitle: '7. 机房机柜信息',
          rows: (roomRack.rows ?? []).map((r) => ({
            podName: r.pod_name,
            roomName: r.room_name,
            compute: r.compute,
            bus: r.bus,
            paramLeaf: r.param_leaf,
            bizLeaf: r.biz_leaf,
            mgmt: r.mgmt,
            sampleLeaf: r.sample_leaf,
            dataSource: r.data_source ?? '',
          })),
        };
        chapters['11'] = chapters['11'] ?? {
          chapterKey: '11',
          chapterTitle: '11. 验收策略',
          rows: [],
        };
        chapters['12'] = chapters['12'] ?? {
          chapterKey: '12',
          chapterTitle: '12. 测试用例',
          rows: [],
        };
        if ((clusterDevices.rows ?? []).length > 0) {
          chapters['5.3'] = {
            chapterKey: '5.3',
            chapterTitle: '5.3 集群设备配置',
            rows: (clusterDevices.rows ?? []).map((r) => ({
              clusterId: r.cluster_id ?? '',
              clusterType: r.cluster_type ?? '',
              superPodId: r.super_pod_id ?? '',
              storageClusterId: r.storage_cluster_id ?? '',
              zoneId: r.zone_id ?? '',
              ccaeClusterId: r.ccae_cluster_id ?? '',
              dmeClusterId: r.dme_cluster_id ?? '',
              deviceType: r.device_type ?? '',
              vendor: r.vendor ?? '',
              deviceModel: r.device_model ?? '',
              devicePurpose: r.device_purpose ?? '',
              startDeviceName: r.start_device_name ?? '',
              endDeviceName: r.end_device_name ?? '',
              quantity: r.quantity ?? 0,
              dataSource: r.data_source ?? '',
            })),
          };
        }
      } catch {
        // ignore legacy fetch failures, keep existing draft chapters
      }
      return chapters;
    };

    const attempt = async (matchEtag?: string) =>
      saveDraft(
        projectId,
        headers,
        { manualChangeLog, chapters: await buildSaveChapters() },
        matchEtag,
      );

    try {
      return await attempt(etag);
    } catch (err) {
      if (err instanceof ProposalApiError && err.code === 'ETAG_MISMATCH') {
        const fresh = await fetchDraft(projectId, headers);
        const freshEtag = fresh.manifest?.etag;
        if (freshEtag) setEtag(freshEtag);
        try {
          return await attempt(freshEtag);
        } catch {
          // pass through to force-save fallback below
        }
      }
      // 异常兜底：直接释放锁（不带 If-Match）执行一次强制保存。
      return attempt(undefined);
    }
  }, [draftChapters, etag, headers, manualChangeLog, projectId]);

  const loadProposalState = useCallback(async () => {
    if (!mountedRef.current) return;
    setLoading(true);
    navDebug('proposal-state load start');
    const errors: string[] = [];

    let draftData: Awaited<ReturnType<typeof fetchDraft>> | null = null;
    let versionList: ProposalVersionItem[] = [];
    let changeLog: CumulativeChangeEntry[] = [];

    try {
      try {
        draftData = await fetchDraft(projectId, headers);
      } catch (err) {
        errors.push(
          err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '草稿加载失败',
        );
      }

      try {
        versionList = await fetchVersions(projectId, headers);
      } catch (err) {
        errors.push(
          err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '版本列表加载失败',
        );
      }

      if (!mountedRef.current) {
        navDebug('proposal-state load aborted (unmounted)');
        return;
      }

      if (draftData) {
        try {
          changeLog = await loadChangeLogForDraft(projectId, headers, draftData);
        } catch {
          changeLog = draftData.cumulativeChangeLog ?? [];
        }
        if (!mountedRef.current) {
          navDebug('proposal-state load aborted (unmounted)');
          return;
        }
        setManifest(draftData.manifest ?? DEFAULT_MANIFEST);
        setDraftChapters((draftData.chapters ?? {}) as Record<string, unknown>);
        setMetadata(resolveVersionInfoMetadata(draftData, DEFAULT_METADATA));
        setEtag(draftData.manifest?.etag);
        setDirty(draftData.manifest?.dirty ?? false);
        setCumulativeLog(changeLog);
        setManualChangeLog(
          changeLog.filter((e) => e.editable !== false && e.source !== 'snapshot'),
        );
      } else {
        setCumulativeLog(changeLog);
        setManualChangeLog(
          changeLog.filter((e) => e.editable !== false && e.source !== 'snapshot'),
        );
        setDraftChapters({});
      }

      const nextVersions = versionList.length > 0 ? versionList : FALLBACK_VERSIONS;
      setVersions(nextVersions);
      const defaultVersion = pickDefaultVersion(nextVersions);
      setProposalVersion(defaultVersion);

      if (defaultVersion !== 'draft') {
        try {
          const snap = await fetchVersionSnapshot(projectId, defaultVersion, headers);
          const selectedVersion = nextVersions.find((v) => v.proposalVersion === defaultVersion);
          setManifest({
            workingVersionLabel: defaultVersion,
            status: 'published',
          });
          setMetadata(
            resolveVersionInfoMetadata(
              snap as Record<string, unknown>,
              DEFAULT_METADATA,
              selectedVersion,
            ),
          );
          setDraftChapters(
            ((snap as { chapters?: Record<string, unknown> }).chapters ?? {}) as Record<
              string,
              unknown
            >,
          );
          const changeLogForVersion = await loadChangeLogThroughVersion(
            projectId,
            headers,
            defaultVersion,
            draftData,
          );
          setCumulativeLog(changeLogForVersion);
          setManualChangeLog([]);
          setDirty(false);
          setTableDirty(false);
        } catch (err) {
          const msg =
            err instanceof ProposalApiError
              ? err.message
              : err instanceof Error
                ? err.message
                : '加载版本失败';
          errors.push(msg);
          setProposalVersion('draft');
        }
      }

      if (errors.length > 0) {
        fireDocToast(errors[0] ?? '预案加载失败');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
        navDebug('proposal-state load done');
      }
    }
  }, [fireDocToast, headers, projectId, setTableDirty]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      await loadProposalState();
      if (cancelled) navDebug('proposal-state effect cancelled');
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [loadProposalState]);

  useEffect(() => {
    const v = readUrlParam('snap');
    if (!v) return;
    const k = (v in SNAPSHOTS ? v : SNAP_ALIASES[v as keyof typeof SNAP_ALIASES]) as
      | SnapKey
      | undefined;
    if (k && k in SNAPSHOTS) setSnapKey(k);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const root = document.querySelector('.proposal-main-canvas');
    const targets = PROPOSAL_OBSERVE_ANCHORS.map((id) => document.getElementById(id)).filter(
      Boolean,
    ) as HTMLElement[];
    if (targets.length === 0) return;

    const io = new IntersectionObserver(
      (entries) => {
        if (!mountedRef.current) return;
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length === 0) return;
        const top = visible.reduce((a, b) =>
          a.boundingClientRect.top < b.boundingClientRect.top ? a : b,
        );
        const key = anchorToChapterKey(top.target.id);
        if (key) setActiveChapterKey(key);
      },
      {
        root: root instanceof Element ? root : null,
        rootMargin: '-80px 0px -55% 0px',
        threshold: 0,
      },
    );
    targets.forEach((t) => io.observe(t));
    return () => io.disconnect();
  }, [snapKey, proposalVersion]);

  const handleVersionSelect = useCallback(
    async (version: string) => {
      setProposalVersion(version);
      if (version === 'draft') {
        try {
          const draftData = await fetchDraft(projectId, headers);
          const log = await loadChangeLogForDraft(projectId, headers, draftData);
          setManifest(draftData.manifest ?? DEFAULT_MANIFEST);
          setDraftChapters((draftData.chapters ?? {}) as Record<string, unknown>);
          setMetadata(resolveVersionInfoMetadata(draftData, DEFAULT_METADATA));
          setCumulativeLog(log);
          setManualChangeLog(
            log.filter((e) => e.editable !== false && e.source !== 'snapshot'),
          );
          setEtag(draftData.manifest?.etag);
          setDirty(draftData.manifest?.dirty ?? false);
        } catch {
          /* keep current */
        }
        return;
      }
      try {
        const snap = await fetchVersionSnapshot(projectId, version, headers);
        const verItem = versions.find((v) => v.proposalVersion === version);
        setManifest({
          workingVersionLabel: version,
          status: 'published',
        });
        setMetadata(
          resolveVersionInfoMetadata(
            snap as Record<string, unknown>,
            DEFAULT_METADATA,
            verItem,
          ),
        );
        setDraftChapters(((snap as { chapters?: Record<string, unknown> }).chapters ?? {}) as Record<string, unknown>);
        const draftForOrder = await fetchDraft(projectId, headers);
        const changeLog = await loadChangeLogThroughVersion(
          projectId,
          headers,
          version,
          draftForOrder,
        );
        setCumulativeLog(changeLog);
        setManualChangeLog([]);
        setDirty(false);
        setTableDirty(false);
      } catch (err) {
        const msg =
          err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '加载版本失败';
        fireDocToast(msg);
      }
    },
    [fireDocToast, headers, projectId, setTableDirty, versions],
  );

  const handleChapterJump = useCallback((chapterKey: string) => {
    const t = CHAPTER_TARGETS[chapterKey];
    if (!t) return;
    if (t.pendingPanel) {
      setPendingTip({ num: chapterKey, panel: t.pendingPanel });
      setTimeout(() => setPendingTip(null), 2400);
      return;
    }
    setActiveChapterKey(chapterKey);
    setTimeout(() => {
      const el = document.getElementById(t.anchor);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }, []);

  const handleSaveDraft = useCallback(() => {
    if (!isEditable) {
      fireDocToast('历史版本只读，请切换到草稿编辑');
      return;
    }
    if (saveInFlightRef.current) return;

    fireDocToast('草稿已保存');
    saveInFlightRef.current = true;

    void (async () => {
      try {
        const result = await saveDraftWithEtagRetry();
        await saveDraftTables();
        setDirty(false);
        setTableDirty(false);
        setEtag(result.etag);
        setManifest((m) => ({
          ...m,
          workingVersionLabel: result.workingVersionLabel ?? m.workingVersionLabel,
          dirty: false,
        }));
        if (result.metadata || result.createdBy) {
          setMetadata(
            resolveVersionInfoMetadata(
              { metadata: result.metadata, manifest: { ...manifest, ...result } },
              metadata,
            ),
          );
        }
        const draftAfterSave = await fetchDraft(projectId, headers);
        const logAfterSave = await loadChangeLogForDraft(projectId, headers, draftAfterSave);
        setManifest(draftAfterSave.manifest ?? DEFAULT_MANIFEST);
        setMetadata(resolveVersionInfoMetadata(draftAfterSave, metadata));
        setCumulativeLog(logAfterSave);
        setManualChangeLog(
          logAfterSave.filter((e) => e.editable !== false && e.source !== 'snapshot'),
        );
        if (draftAfterSave.manifest?.etag) setEtag(draftAfterSave.manifest.etag);
        setDirty(draftAfterSave.manifest?.dirty ?? false);
        setTableDirty(false);
      } catch (err) {
        const msg =
          err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '保存失败';
        fireDocToast(msg);
        setDirty(true);
      } finally {
        saveInFlightRef.current = false;
      }
    })();
  }, [fireDocToast, headers, isEditable, manifest, metadata, projectId, saveDraftTables, saveDraftWithEtagRetry, setTableDirty]);

  const handleConfirm = useCallback(async () => {
    if (!isEditable) {
      fireDocToast('历史版本只读，请切换到草稿后再发布');
      return;
    }
    setActionBusy(true);
    try {
      await saveDraftWithEtagRetry();
      await saveAndConfirmTables();
      await releaseAndDecide(projectId, headers, {
        changeRecords: manualLogToChangeRecords(manualChangeLog),
      });
      setDirty(false);
    } catch (err) {
      const msg =
        err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '发布失败';
      fireDocToast(msg);
    } finally {
      setActionBusy(false);
      // 发布成功或被门禁拦截，都跳转到算力底座孪生页：置位一次性请求 → 进入即清除/init 态，
      // 并自动跑「构建算力底座孪生」（分窗 + 创建机房/数字孪生动画）。?view=build 保持 URL 稳定不重挂载。
      requestTwinAutoBuild();
      workspaceNavigate(navigate, '/twin?view=build', location.pathname);
    }
  }, [fireDocToast, headers, isEditable, location.pathname, manualChangeLog, navigate, projectId, saveAndConfirmTables, saveDraftWithEtagRetry]);

  const upsertDraftChapterRows = useCallback(
    (chapterKey: string, chapterTitle: string, rows: Array<Record<string, unknown>>) => {
      let changed = false;
      setDraftChapters((prev) => {
        const prevChapter = (prev[chapterKey] as Record<string, unknown> | undefined) ?? {};
        const prevRows = Array.isArray(prevChapter.rows)
          ? (prevChapter.rows as Array<Record<string, unknown>>)
          : [];
        const prevRowsJson = JSON.stringify(prevRows);
        const nextRowsJson = JSON.stringify(rows);
        if (prevRowsJson === nextRowsJson && prevChapter.chapterTitle === chapterTitle) {
          return prev;
        }
        changed = true;
        return {
          ...prev,
          [chapterKey]: {
            ...prevChapter,
            chapterKey,
            chapterTitle,
            rows,
          },
        };
      });
      if (changed) {
        setDirty(true);
        setTableDirty(true);
      }
    },
    [setTableDirty],
  );

  const handleRaciRowsChange = useCallback(
    (rows: Array<Record<string, unknown>>) => {
      updateRaci(rows as unknown as RaciRow[]);
      upsertDraftChapterRows('9', '9. 责任矩阵信息', rows);
    },
    [updateRaci, upsertDraftChapterRows],
  );

  const handleTestCaseSelectionChange = useCallback(
    (selectedKeys: Set<string>) => {
      updateTestCaseSelection(selectedKeys);
      const rows = testCases.map((c, i) => ({
        ...c,
        selected: selectedKeys.has(tcKey(c, i)),
      }));
      upsertDraftChapterRows('12', '12. 测试用例', rows);
    },
    [testCases, updateTestCaseSelection, upsertDraftChapterRows],
  );

  const handleExport = useCallback(async () => {
    setActionBusy(true);
    try {
      const blob = await exportDocument(projectId, headers, proposalVersion);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download =
        proposalVersion === 'draft'
          ? `${metadata.projectName ?? '交付预案'}_草稿.json`
          : `${metadata.projectName ?? '交付预案'}_${proposalVersion}.json`;
      a.click();
      URL.revokeObjectURL(url);
      fireDocToast('文档已导出');
    } catch (err) {
      const msg =
        err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '导出失败';
      fireDocToast(msg);
    } finally {
      setActionBusy(false);
    }
  }, [fireDocToast, headers, metadata.projectName, projectId, proposalVersion]);

  const handleProposalDirty = useCallback(() => setDirty(true), []);

  const chapters = CHAPTERS_BY_SNAP[snapKey] || [];
  const outlinePageClass = outlineHidden
    ? 'proposal-page--outline-hidden'
    : outlineWide
      ? ''
      : 'proposal-page--outline-collapsed';

  const pageTitle = `${resolveTopBarProjectDisplayName(project)}交付预案`;

  return (
    <div className={`proposal-page${outlinePageClass ? ` ${outlinePageClass}` : ''}`}>
      {pendingTip && (
        <div className="proposal-pending-tip" role="status">
          §{pendingTip.num} 正文体（{pendingTip.panel}）将在后续批次补齐
        </div>
      )}

      <main className="proposal-main-canvas jn-wrap">
        {outlineHidden && (
          <button
            type="button"
            className="proposal-outline-reopen"
            onClick={() => {
              setOutlineHidden(false);
              setOutlineCollapsed(false);
            }}
            aria-label="展开章节大纲"
            title="展开章节大纲"
          >
            章节
          </button>
        )}
        <div className="main-inner proposal-main-inner">
          <div className="proposal-doc-header">
            <div className="proposal-doc-header-top">
              <div className="min-w-0">
                <h1 className="proposal-doc-title">{pageTitle}</h1>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-normal text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                  onClick={() => void handleExport()}
                  disabled={actionBusy || pageLoading}
                >
                  下载文档
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-normal text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                  onClick={() => void handleSaveDraft()}
                  disabled={actionBusy || pageLoading || !isEditable}
                >
                  保存草稿
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-normal text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                  onClick={() => void handleConfirm()}
                  disabled={actionBusy || pageLoading || !isEditable}
                >
                  生成预案并决策
                </button>
              </div>
            </div>
            <div className="proposal-doc-actions">
              <div className="proposal-doc-meta">
                <span>创建人 <b>{metadata.createdBy ?? '—'}</b></span>
                <span className="proposal-doc-meta-dot">·</span>
                <span>创建时间 <b>{formatProposalDateTime(metadata.createdAt)}</b></span>
                <span className="proposal-doc-meta-dot">·</span>
                <span>最后修改人 <b>{metadata.updatedBy ?? '—'}</b></span>
                <span className="proposal-doc-meta-dot">·</span>
                <span>修改时间 <b>{formatProposalDateTime(metadata.updatedAt)}</b></span>
                {dirty && isEditable && (
                  <>
                    <span className="proposal-doc-meta-dot">·</span>
                    <span className="text-amber-600">未保存</span>
                  </>
                )}
              </div>
              <div className="proposal-doc-actions-spacer" />
              <VersionDropdown
                versions={versions.length > 0 ? versions : FALLBACK_VERSIONS}
                currentVersion={proposalVersion}
                onSelect={(v) => void handleVersionSelect(v)}
              />
            </div>
          </div>

          {pageLoading ? (
            <p className="py-8 text-center text-sm text-slate-500">加载预案数据…</p>
          ) : (
            <>
              <MetaChapter
                cumulativeLog={cumulativeLog}
                readOnly={!isEditable}
                onCumulativeLogChange={(entries) => {
                  setManualChangeLog(entries);
                  if (isEditable) setDirty(true);
                }}
              />
              <CustomerChapterWrapper
                initialRows={(draftChapters['1'] as { rows?: unknown[] } | undefined)?.rows}
                readOnly={!isEditable}
                onRowsChange={(rows) => upsertDraftChapterRows('1', '1. 项目背景', rows)}
              />

              <DeviceChapter
                proposalVersion={proposalVersion}
                readOnly={!isEditable}
                onDirty={handleProposalDirty}
                onManifestActivity={handleManifestActivity}
              />
              <PartsChapter
                initialRows={(draftChapters['3'] as { rows?: unknown[] } | undefined)?.rows}
                readOnly={!isEditable}
                onRowsChange={(rows) => upsertDraftChapterRows('3', '3. 部件配置信息', rows)}
              />
              <SoftwareChapter
                initialRows={(draftChapters['4'] as { rows?: unknown[] } | undefined)?.rows}
                readOnly={!isEditable}
                onRowsChange={(rows) => upsertDraftChapterRows('4', '4. 软件配置信息', rows)}
              />
              <NetworkChapterWrapper />

              <IntegrationChapter
                initialRows={(draftChapters['6'] as { rows?: unknown[] } | undefined)?.rows}
                onRowsChange={(rows) => upsertDraftChapterRows('6', '6. 预集成预验证需求', rows)}
              />

              <RoomChapter />

              <ServiceChapterWrapper
                proposalVersion={proposalVersion}
                readOnly={!isEditable}
                onDirty={handleProposalDirty}
                onManifestActivity={handleManifestActivity}
              />

              <RaciChapter
                initialRows={raciRows}
                readOnly={!isEditable}
                onRowsChange={handleRaciRowsChange}
              />
              <PlanChapter
                initialRows={planRows}
                onRowsChange={(rows) => upsertDraftChapterRows('10', '10. 计划', rows)}
              />
              <AcceptanceChapter
                initialRows={acceptanceReady ? acceptanceItems : []}
                onRowsChange={(rows) => {
                  refreshAcceptance(rows as unknown as AcceptanceItem[]);
                  upsertDraftChapterRows('11', '11. 验收策略', rows);
                }}
              />
              <TestCaseChapter
                initialRows={testCasesReady
                  ? testCases.map((c, i) => ({
                      ...c,
                      selected: selectedTcKeys.has(tcKey(c, i)),
                    }))
                  : []}
                readOnly={!isEditable}
                onSelectionChange={handleTestCaseSelectionChange}
              />
            </>
          )}
        </div>
      </main>

      {docToast && <div className="boq-attach-toast">{docToast}</div>}

      {!outlineHidden && (
        <div className="proposal-outline-aside">
          <ProposalOutlineRail
            chapters={chapters}
            onJump={handleChapterJump}
            activeChapterKey={activeChapterKey}
            layout="grid"
            wide={outlineWide}
            pinned={outlinePinned}
            collapsed={outlineCollapsed}
            onCollapsedChange={setOutlineCollapsed}
            onHoverChange={setOutlineHover}
            onPinnedChange={setOutlinePinned}
            onHide={() => {
              setOutlineHidden(true);
              setOutlinePinned(false);
              setOutlineCollapsed(true);
              setOutlineHover(false);
            }}
          />
        </div>
      )}
    </div>
  );
}
