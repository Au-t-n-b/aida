'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  ProposalTooltipProvider,
} from '../ui/tooltip';
import {
  CHAPTER_TARGETS,
  chapterKeyFromName,
  isSubChapterKey,
  parentChapterKey,
} from './proposal-navigation';

type ChapterRow = { name: string; state: string; note?: string };

const iconClass = 'w-4 h-4 shrink-0 text-slate-400 transition-colors';

const IconPin = ({ className = iconClass }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M12 17v5" />
    <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-2.5 1.12a1 1 0 0 0-.39 1.36l1.12 2.5a2 2 0 0 1 1.79 1.11L12 22l2.12-1.36a2 2 0 0 1 1.79-1.11l2.5-1.12a1 1 0 0 0 .39-1.36l-1.12-2.5a2 2 0 0 1-1.11-1.79L15 10.76V6a3 3 0 0 0-6 0v4.76Z" />
  </svg>
);

const IconChevronRight = ({ className = iconClass }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="m9 18 6-6-6-6" />
  </svg>
);

const IconChevronLeft = ({ className = iconClass }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="m15 18-6-6 6-6" />
  </svg>
);

const IconX = ({ className = iconClass }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </svg>
);

/** 一级章聚合子章风险：miss 优先于 partial */
function buildTopLevelRiskMap(chapters: ChapterRow[]): Map<string, 'miss' | 'partial'> {
  const map = new Map<string, 'miss' | 'partial'>();
  for (const c of chapters) {
    const key = chapterKeyFromName(c.name);
    const topKey = isSubChapterKey(key) ? (key.split('.')[0] ?? key) : key;
    if (c.state === 'miss') {
      map.set(topKey, 'miss');
    } else if (c.state === 'partial' && map.get(topKey) !== 'miss') {
      map.set(topKey, 'partial');
    }
  }
  return map;
}

export function ProposalOutlineRail({
  chapters,
  onJump,
  activeChapterKey,
  layout = 'grid',
  wide = true,
  pinned = false,
  collapsed = false,
  onCollapsedChange,
  onHoverChange,
  onPinnedChange,
  onHide,
}: {
  chapters: ChapterRow[];
  onJump: (chapterKey: string) => void;
  activeChapterKey: string | null;
  layout?: 'grid' | 'fixed';
  wide?: boolean;
  pinned?: boolean;
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  onHoverChange?: (hover: boolean) => void;
  onPinnedChange?: (pinned: boolean) => void;
  onHide?: () => void;
}) {
  const inGrid = layout === 'grid';
  const isOpen = wide;
  const topLevelRisk = buildTopLevelRiskMap(chapters);

  const isChapterActive = (chapterKey: string) => {
    if (activeChapterKey === chapterKey) return true;
    if (!isOpen && activeChapterKey && parentChapterKey(activeChapterKey) === chapterKey) {
      return true;
    }
    return false;
  };

  const visibleChapters = isOpen
    ? chapters
    : chapters.filter((c) => !isSubChapterKey(chapterKeyFromName(c.name)));

  const collapse = () => {
    onPinnedChange?.(false);
    onCollapsedChange?.(true);
    onHoverChange?.(false);
  };

  const expand = () => {
    onCollapsedChange?.(false);
  };

  const actionBtnClass =
    'proposal-outline-rail-action flex items-center justify-center w-[22px] h-[22px] rounded p-0 border-0 bg-transparent cursor-pointer text-slate-400 hover:text-slate-700 transition-colors';

  return (
    <ProposalTooltipProvider>
      <aside
        className={`proposal-outline-rail${isOpen ? ' expanded' : ''}${pinned ? ' pinned' : ''}${inGrid ? ' proposal-outline-rail--in-grid' : ''}`}
        onMouseEnter={() => {
          if (collapsed) onHoverChange?.(true);
        }}
        onMouseLeave={() => {
          if (!pinned) onHoverChange?.(false);
        }}
        aria-label="预案章节大纲"
      >
        <div className="proposal-outline-rail-head">
          <span className="proposal-outline-rail-title">章节</span>
          <span className="proposal-outline-rail-count">{chapters.length}</span>
          <div className="proposal-outline-rail-actions">
            {isOpen ? (
              <>
                <button
                  type="button"
                  className={`${actionBtnClass} proposal-outline-rail-pin${pinned ? ' on' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onPinnedChange?.(!pinned);
                    if (!pinned) onCollapsedChange?.(false);
                  }}
                  title={pinned ? '取消固定' : '固定常驻'}
                  aria-label={pinned ? '取消固定大纲' : '固定大纲'}
                >
                  <IconPin className={pinned ? 'w-4 h-4 text-blue-600' : 'w-4 h-4 text-slate-400 hover:text-slate-700'} />
                </button>
                <button
                  type="button"
                  className={`${actionBtnClass} proposal-outline-rail-toggle`}
                  onClick={(e) => {
                    e.stopPropagation();
                    collapse();
                  }}
                  title="收起大纲"
                  aria-label="收起大纲"
                >
                  <IconChevronRight />
                </button>
                {onHide && (
                  <button
                    type="button"
                    className={`${actionBtnClass} proposal-outline-rail-toggle`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onHide();
                    }}
                    title="隐藏大纲"
                    aria-label="隐藏大纲"
                  >
                    <IconX />
                  </button>
                )}
              </>
            ) : (
              <button
                type="button"
                className={`${actionBtnClass} proposal-outline-rail-toggle`}
                onClick={(e) => {
                  e.stopPropagation();
                  expand();
                }}
                title="展开大纲"
                aria-label="展开大纲"
              >
                <IconChevronLeft />
              </button>
            )}
          </div>
        </div>
        <div className="proposal-outline-rail-list">
          {visibleChapters.map((c) => {
            const chapterKey = chapterKeyFromName(c.name);
            const t = CHAPTER_TARGETS[chapterKey];
            const isActive = isChapterActive(chapterKey);
            const isPending = !!(t && t.pendingPanel);
            const isSub = isSubChapterKey(chapterKey);
            const showSubTree = isOpen && isSub;
            const displayNum = c.name.startsWith('元数据')
              ? '◎'
              : c.name.match(/^(\d+(?:\.\d+)?)/)?.[1] || chapterKey;
            const topKey = isSubChapterKey(chapterKey)
              ? (chapterKey.split('.')[0] ?? chapterKey)
              : chapterKey;
            const collapsedRisk = !isOpen ? topLevelRisk.get(topKey) : null;

            const item = (
              <button
                type="button"
                className={[
                  'proposal-outline-rail-item',
                  isActive ? 'active' : '',
                  isPending ? 'pending' : '',
                  isOpen
                    ? isSub
                      ? 'proposal-outline-rail-item--plain-sub'
                      : 'proposal-outline-rail-item--plain-top'
                    : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onClick={() => onJump(chapterKey)}
              >
                {/* 收起态（44px）：保留数字圆圈 + 风险角标 */}
                {!isOpen && (
                  <span className="proposal-outline-rail-num-wrap">
                    <span
                      className={[
                        'proposal-outline-rail-num',
                        isActive
                          ? 'proposal-outline-rail-num--active'
                          : 'proposal-outline-rail-num--neutral',
                      ].join(' ')}
                    >
                      {displayNum}
                    </span>
                    {collapsedRisk && (
                      <span
                        className={[
                          'proposal-outline-rail-risk-badge',
                          collapsedRisk === 'miss'
                            ? 'proposal-outline-rail-risk-badge--miss'
                            : 'proposal-outline-rail-risk-badge--partial',
                        ].join(' ')}
                        aria-hidden
                      />
                    )}
                  </span>
                )}
                {/* 展开态：朴素文本树 — 一级章前置折叠三角，二级缩进 */}
                {isOpen && !isSub && (
                  <span className="proposal-outline-rail-tri" aria-hidden>▾</span>
                )}
                <span className="proposal-outline-rail-body">
                  <span className="proposal-outline-rail-name">
                    {isOpen ? c.name : c.name.replace(/^(?:元数据信息|\d+(?:\.\d+)?)\s*/, '')}
                  </span>
                  {c.note && <span className="proposal-outline-rail-note">{c.note}</span>}
                </span>
                {isOpen && (
                  <span
                    className={`outline-state-dot ${isPending ? 'pending' : c.state}`}
                    title={
                      isPending
                        ? '待补齐'
                        : c.state === 'ok'
                          ? '齐备'
                          : c.state === 'partial'
                            ? '部分完成'
                            : '缺失'
                    }
                  />
                )}
              </button>
            );

            return (
              <Tooltip key={c.name} delayDuration={200}>
                <TooltipTrigger asChild>{item}</TooltipTrigger>
                <TooltipContent side="left">{c.name}</TooltipContent>
              </Tooltip>
            );
          })}
        </div>
        <div className="proposal-outline-rail-foot">
          {isOpen ? '点击章节跳转正文 · 固定大纲常驻' : '移入展开大纲'}
        </div>
      </aside>
    </ProposalTooltipProvider>
  );
}
