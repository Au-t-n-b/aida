/** 大纲章节 → 正文锚点（P3：每章独立 Card，无 subTab） */
export type ChapterTarget = {
  anchor: string;
  pendingPanel?: string;
};

export const CHAPTER_TARGETS: Record<string, ChapterTarget> = {
  '元数据': { anchor: 'panel-meta' },
  '1': { anchor: 'sec-1-1' },
  '2': { anchor: 'sec-ch-2' },
  '3': { anchor: 'sec-ch-3' },
  '4': { anchor: 'sec-ch-4' },
  '5': { anchor: 'sec-ch-5-1' },
  '5.1': { anchor: 'sec-ch-5-1' },
  '5.2': { anchor: 'sec-ch-5-2' },
  '6': { anchor: 'panel-pre' },
  '7': { anchor: 'panel-rooms' },
  '8': { anchor: 'sec-7-1' },
  '8.1': { anchor: 'sec-7-1' },
  '8.2': { anchor: 'sec-7-2' },
  '8.3': { anchor: 'sec-7-3' },
  '8.4': { anchor: 'sec-7-4' },
  '9': { anchor: 'panel-raci' },
  '10': { anchor: 'panel-plan' },
  '11': { anchor: 'panel-accept' },
  '12': { anchor: 'panel-testcase' },
  '13': { anchor: 'sec-9-1' },
  '13.1': { anchor: 'sec-9-1' },
  '13.2': { anchor: 'sec-9-2' },
};

export const PROPOSAL_OBSERVE_ANCHORS = [
  ...new Set(Object.values(CHAPTER_TARGETS).map((t) => t.anchor)),
];

export function chapterKeyFromName(name: string): string {
  if (name.startsWith('元数据')) return '元数据';
  const m = name.match(/^(\d+(?:\.\d+)?)/);
  if (m?.[1]) return m[1];
  return name.split('.')[0] ?? name;
}

/** 大纲二级章节（如 1.1、5.2） */
export function isSubChapterKey(key: string): boolean {
  return /^\d+\.\d+$/.test(key);
}

export function parentChapterKey(key: string | null): string | null {
  if (!key || !isSubChapterKey(key)) return null;
  return key.split('.')[0] ?? null;
}

export function anchorToChapterKey(anchorId: string): string | null {
  const entries = Object.entries(CHAPTER_TARGETS);
  const exact = entries.find(([, t]) => t.anchor === anchorId);
  if (exact) return exact[0];
  return null;
}

export function readUrlParam(key: string): string | null {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(key);
}
