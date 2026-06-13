'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
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
  useProposalApiHeaders,
  type CumulativeChangeEntry,
  type DraftManifest,
  type ManifestActivity,
  type ProposalVersionItem,
  type VersionInfoMetadata,
} from '@/lib/proposal-api';
import { useCurrentProject } from '@/lib/current-project';
import { useProposalData } from '@/hooks/useProposalData';

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

export default function ProposalScreen() {
  const headers = useProposalApiHeaders();
  const { project } = useCurrentProject();
  const projectId = project?.code ?? getDefaultProjectId();
  const {
    projectCtx,
    dataWarnings,
    saveDraftTables,
    saveAndConfirmTables,
  } = useProposalData();

  const [proposalVersion, setProposalVersion] = useState('draft');
  const [versions, setVersions] = useState<ProposalVersionItem[]>([]);
  const [manifest, setManifest] = useState<DraftManifest>(DEFAULT_MANIFEST);
  const [metadata, setMetadata] = useState<VersionInfoMetadata>(DEFAULT_METADATA);
  const [cumulativeLog, setCumulativeLog] = useState<CumulativeChangeEntry[]>([]);
  const [manualChangeLog, setManualChangeLog] = useState<CumulativeChangeEntry[]>([]);
  const [etag, setEtag] = useState<string | undefined>();
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [docToast, setDocToast] = useState<string | null>(null);

  const [snapKey, setSnapKey] = useState<SnapKey>('exec');
  const [activeChapterKey, setActiveChapterKey] = useState<string | null>(null);
  const [pendingTip, setPendingTip] = useState<{ num: string; panel: string } | null>(null);
  const [outlineCollapsed, setOutlineCollapsed] = useState(false);
  const [outlineHover, setOutlineHover] = useState(false);
  const [outlinePinned, setOutlinePinned] = useState(false);
  const [outlineHidden, setOutlineHidden] = useState(false);
  const loadGenRef = useRef(0);

  const isEditable = proposalVersion === 'draft';
  const outlineWide = !outlineCollapsed || outlineHover || outlinePinned;

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
    const attempt = async (matchEtag?: string) =>
      saveDraft(projectId, headers, { manualChangeLog }, matchEtag);

    try {
      return await attempt(etag);
    } catch (err) {
      if (err instanceof ProposalApiError && err.code === 'ETAG_MISMATCH') {
        const fresh = await fetchDraft(projectId, headers);
        const freshEtag = fresh.manifest?.etag;
        if (freshEtag) setEtag(freshEtag);
        return attempt(freshEtag);
      }
      throw err;
    }
  }, [etag, headers, manualChangeLog, projectId]);

  const loadProposalState = useCallback(async () => {
    const gen = ++loadGenRef.current;
    setLoading(true);
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

      if (draftData) {
        try {
          changeLog = await loadChangeLogForDraft(projectId, headers, draftData);
        } catch (err) {
          errors.push(
            err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '修改记录加载失败',
          );
        }
        setManifest(draftData.manifest ?? DEFAULT_MANIFEST);
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
      }

      setVersions(versionList.length > 0 ? versionList : FALLBACK_VERSIONS);
      setProposalVersion('draft');

      if (errors.length > 0) {
        console.warn('[proposal] loadProposalState partial errors', errors);
        fireDocToast(errors[0] ?? '预案加载失败');
      }
    } finally {
      if (gen === loadGenRef.current) {
        setLoading(false);
      }
    }
  }, [fireDocToast, headers, projectId]);

  useEffect(() => {
    void loadProposalState();
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
          setMetadata(resolveVersionInfoMetadata(draftData, DEFAULT_METADATA));
          setCumulativeLog(log);
          setManualChangeLog(
            log.filter((e) => e.editable !== false && e.source !== 'snapshot'),
          );
          setEtag(draftData.manifest?.etag);
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
        const draftForOrder = await fetchDraft(projectId, headers);
        const changeLog = await loadChangeLogThroughVersion(
          projectId,
          headers,
          version,
          draftForOrder,
        );
        setCumulativeLog(changeLog);
        setManualChangeLog([]);
      } catch (err) {
        const msg =
          err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '加载版本失败';
        fireDocToast(msg);
      }
    },
    [fireDocToast, headers, projectId, versions],
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

  const handleSaveDraft = useCallback(async () => {
    if (!isEditable) {
      fireDocToast('历史版本只读，请切换到草稿编辑');
      return;
    }
    setActionBusy(true);
    try {
      const result = await saveDraftWithEtagRetry();
      setDirty(false);
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
      setCumulativeLog(logAfterSave);
      setManualChangeLog(
        logAfterSave.filter((e) => e.editable !== false && e.source !== 'snapshot'),
      );
      if (draftAfterSave.manifest?.etag) setEtag(draftAfterSave.manifest.etag);
      await saveDraftTables();
      fireDocToast('草稿已保存 · 版本号不变');
    } catch (err) {
      const msg =
        err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '保存失败';
      fireDocToast(msg);
    } finally {
      setActionBusy(false);
    }
  }, [fireDocToast, headers, isEditable, manifest, metadata, manualChangeLog, projectId, saveDraftTables, saveDraftWithEtagRetry]);

  const handleConfirm = useCallback(async () => {
    if (!isEditable) {
      fireDocToast('历史版本只读，请切换到草稿后再发布');
      return;
    }
    setActionBusy(true);
    try {
      await saveDraftWithEtagRetry();
      await saveAndConfirmTables();
      const result = await releaseAndDecide(projectId, headers, {
        changeRecords: manualLogToChangeRecords(manualChangeLog),
      });
      setDirty(false);

      if (typeof window !== 'undefined' && result.progress) {
        result.progress.forEach((item, idx) => {
          setTimeout(
            () => window.dispatchEvent(new CustomEvent('aida:progress', { detail: item })),
            idx === 0 ? 0 : idx * 400,
          );
        });
      }

      const versionList = await fetchVersions(projectId, headers);
      setVersions(versionList);
      const draftData = await fetchDraft(projectId, headers);
      const log = await loadChangeLogForDraft(projectId, headers, draftData);
      setProposalVersion('draft');
      setManifest(draftData.manifest ?? DEFAULT_MANIFEST);
      setMetadata(resolveVersionInfoMetadata(draftData, DEFAULT_METADATA));
      setCumulativeLog(log);
      setManualChangeLog(
        log.filter((e) => e.editable !== false && e.source !== 'snapshot'),
      );
      setEtag(draftData.manifest?.etag);

      const delay = (result.progress?.length ?? 1) * 400 + 400;
      setTimeout(() => window.location.assign('/cockpit'), Math.max(delay, 2800));
    } catch (err) {
      const msg =
        err instanceof ProposalApiError ? err.message : err instanceof Error ? err.message : '发布失败';
      fireDocToast(msg);
      setActionBusy(false);
    }
  }, [fireDocToast, headers, isEditable, manualChangeLog, projectId, saveAndConfirmTables, saveDraftWithEtagRetry]);

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

  const chapters = CHAPTERS_BY_SNAP[snapKey] || [];
  const outlinePageClass = outlineHidden
    ? 'proposal-page--outline-hidden'
    : outlineWide
      ? ''
      : 'proposal-page--outline-collapsed';

  const pageTitle = `${metadata.projectName ?? '京东三期项目'}交付预案`;

  return (
    <div className={`proposal-page${outlinePageClass ? ` ${outlinePageClass}` : ''}`}>
      {!projectCtx && (
        <div className="proposal-pending-tip" role="alert">
          请从落地页选择项目后再加载数据中心文件（第 9–12 章）
        </div>
      )}
      {dataWarnings.length > 0 && (
        <div className="proposal-pending-tip" role="status" style={{ background: '#fef3c7', color: '#92400e' }}>
          {dataWarnings[dataWarnings.length - 1]}
        </div>
      )}
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
                  disabled={actionBusy || loading}
                >
                  下载文档
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-normal text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                  onClick={() => void handleSaveDraft()}
                  disabled={actionBusy || loading || !isEditable}
                >
                  保存草稿
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-normal text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                  onClick={() => void handleConfirm()}
                  disabled={actionBusy || loading || !isEditable}
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

          {loading ? (
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
              <CustomerChapterWrapper />

              <DeviceChapter
                proposalVersion={proposalVersion}
                readOnly={!isEditable}
                onDirty={() => setDirty(true)}
                onManifestActivity={handleManifestActivity}
              />
              <PartsChapter />
              <SoftwareChapter />
              <NetworkChapterWrapper />

              <IntegrationChapter />

              <RoomChapter />

              <ServiceChapterWrapper
                proposalVersion={proposalVersion}
                readOnly={!isEditable}
                onDirty={() => setDirty(true)}
                onManifestActivity={handleManifestActivity}
              />

              <RaciChapter />
              <PlanChapter />
              <AcceptanceChapter />
              <TestCaseChapter />
            </>
          )}
        </div>

        {docToast && <div className="boq-attach-toast">{docToast}</div>}
      </main>

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
