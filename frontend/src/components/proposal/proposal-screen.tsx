'use client';

import { useState, useEffect, useCallback } from 'react';
import { AcceptanceChapter } from './chapters/acceptance-chapter';
import { CustomerChapterWrapper } from './chapters/customer-chapter';
import { DeviceChapter } from './chapters/device-chapter';
import { IntegrationChapter } from './chapters/integration-chapter';
import { MetaChapter } from './chapters/meta-chapter';
import { NetworkChapterWrapper } from './chapters/network-chapters';
import { PartsChapter } from './chapters/parts-chapter';
import { PlanChapter } from './chapters/plan-chapter';
import { RaciChapter } from './chapters/raci-chapter';
import { RiskChapterWrapper } from './chapters/risk-chapter';
import { RoomChapter } from './chapters/room-chapter';
import { ServiceChapterWrapper } from './chapters/service-chapters';
import { SoftwareChapter } from './chapters/software-chapter';
import { TestCaseChapter } from './chapters/test-case-chapter';
import {
  CHAPTERS_BY_SNAP,
  SNAP_ALIASES,
  SNAPSHOTS,
  type SnapKey,
} from './proposal-data';
import {
  anchorToChapterKey,
  CHAPTER_TARGETS,
  PROPOSAL_OBSERVE_ANCHORS,
  readUrlParam,
} from './proposal-navigation';
import { ProposalOutlineRail } from './proposal-outline-rail';
import { VersionDropdown } from './proposal-version-dropdown';

export default function ProposalScreen() {
  const [snapKey, setSnapKey] = useState<SnapKey>('dtrb');
  const [dirty, setDirty] = useState(false);
  const [activeChapterKey, setActiveChapterKey] = useState<string | null>(null);
  const [pendingTip, setPendingTip] = useState<{ num: string; panel: string } | null>(null);
  const [outlineCollapsed, setOutlineCollapsed] = useState(false);
  const [outlineHover, setOutlineHover] = useState(false);
  const [outlinePinned, setOutlinePinned] = useState(false);
  const [outlineHidden, setOutlineHidden] = useState(false);

  const outlineWide = !outlineCollapsed || outlineHover || outlinePinned;

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
  }, [snapKey]);

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

  const [docToast, setDocToast] = useState<string | null>(null);
  const fireDocToast = useCallback((msg: string) => {
    setDocToast(msg);
    window.setTimeout(() => setDocToast(null), 2400);
  }, []);

  const handleSaveDraft = useCallback(() => {
    setDirty(false);
    fireDocToast('草稿已保存 · 版本号不变');
  }, [fireDocToast]);

  const handleConfirm = useCallback(() => {
    setDirty(false);
    if (typeof window === 'undefined') return;
    const fire = (delay: number, detail: object) =>
      setTimeout(
        () => window.dispatchEvent(new CustomEvent('aida:progress', { detail })),
        delay,
      );
    fire(0, { role: 'user', body: `生成预案并决策 · ${SNAPSHOTS[snapKey].label}` });
    fire(400, {
      role: 'ai',
      body: `预案 ${SNAPSHOTS[snapKey].label} 已发布 · 正在下发任务与风险…`,
      chips: ['预案已发布'],
    });
    fire(1200, {
      role: 'ai',
      body: '任务下发完成：ConnectX-7 数量确认（何博）/ 样本面接入设备补齐（王明）/ k8s 平台版本确认（TD）已进入计划任务列表。',
      chips: ['任务 +3', '已指定责任人'],
      actions: [{ label: '查看计划任务', kind: 'primary', icon: 'Eye' }],
    });
    fire(2200, {
      role: 'ai',
      body: '风险已写入项目孪生风险预警：BOQ 冲突（高）/ 组网缺失（高）/ CAD 缺失（中）· 进入孪生看板可见全貌。',
      chips: ['风险 +3', '已同步看板'],
      actions: [
        { label: '进入项目孪生', kind: 'primary' },
        { label: '查看风险预警', kind: 'ghost' },
      ],
    });
    setTimeout(() => window.location.assign('/cockpit'), 2800);
  }, [snapKey]);

  const snap = SNAPSHOTS[snapKey];
  const chapters = CHAPTERS_BY_SNAP[snapKey] || [];

  const outlinePageClass = outlineHidden
    ? 'proposal-page--outline-hidden'
    : outlineWide
      ? ''
      : 'proposal-page--outline-collapsed';

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
                <h1 className="proposal-doc-title">京东三期项目交付预案</h1>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-normal text-white transition-colors hover:bg-blue-700"
                  onClick={() => fireDocToast('正在导出文档：京东三期项目交付预案.docx')}
                >
                  下载文档
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-normal text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                  onClick={handleSaveDraft}
                >
                  保存草稿
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-normal text-white transition-colors hover:bg-blue-700"
                  onClick={handleConfirm}
                >
                  生成预案并决策
                </button>
              </div>
            </div>
            <div className="proposal-doc-actions">
              <div className="proposal-doc-meta">
                <span>创建人 <b>{snap.createdBy}</b></span>
                <span className="proposal-doc-meta-dot">·</span>
                <span>创建时间 <b>{snap.createdAt}</b></span>
                <span className="proposal-doc-meta-dot">·</span>
                <span>最后修改人 <b>{snap.updatedBy}</b></span>
                <span className="proposal-doc-meta-dot">·</span>
                <span>修改时间 <b>{snap.updatedAt}</b></span>
              </div>
              <div className="proposal-doc-actions-spacer" />
              <VersionDropdown snapKey={snapKey} onSelect={setSnapKey} />
            </div>
          </div>

          <MetaChapter snapKey={snapKey} />
          <CustomerChapterWrapper />

          <DeviceChapter />
          <PartsChapter />
          <SoftwareChapter />
          <NetworkChapterWrapper />

          <IntegrationChapter />

          <RoomChapter />

          <ServiceChapterWrapper />

          <RaciChapter />
          <PlanChapter />
          <AcceptanceChapter />
          <TestCaseChapter />
          <RiskChapterWrapper />
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
