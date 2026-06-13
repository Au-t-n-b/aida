const DEFAULT_THROTTLE_MS = 24 * 60 * 60 * 1000;

export interface NarrativeChapterLike {
  id?: string;
  /** 融合组章：标题与概述按需自动生成（不受 eligibleIds 白名单限制）。 */
  isGroup?: boolean;
  narrative?: string | null;
  narrativeGenerated?: string | null;
  narrativeEdited?: string | null;
  pendingGenerated?: string | null;
  mergeCandidate?: string | null;
}

export interface NarrativeAutogenScope {
  projectKey?: string | null;
  planId?: string | null;
  chapterIds: readonly string[];
}

export interface NarrativeAutogenStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function hasText(value: string | null | undefined): boolean {
  return typeof value === 'string' && value.trim().length > 0;
}

export function chapterHasNarrativeText(chapter: NarrativeChapterLike): boolean {
  return hasText(chapter.narrative)
    || hasText(chapter.narrativeGenerated)
    || hasText(chapter.narrativeEdited)
    || hasText(chapter.pendingGenerated)
    || hasText(chapter.mergeCandidate);
}

export function getMissingNarrativeChapterIds(
  chapters: readonly NarrativeChapterLike[],
  eligibleIds?: ReadonlySet<string>,
): string[] {
  // 待自动生成 = 正文为空 且（在白名单内 或 是融合组章）。融合组章总是自动产出标题+概述，
  // 不受 eligibleIds 限制（组 id 是动态的）。
  return chapters
    .filter((chapter) => !!chapter.id
      && (!!chapter.isGroup || !eligibleIds || eligibleIds.has(chapter.id))
      && !chapterHasNarrativeText(chapter))
    .map((chapter) => chapter.id as string);
}

export function makeNarrativeAutogenKey(scope: NarrativeAutogenScope): string {
  const project = encodeURIComponent((scope.projectKey || 'default-project').trim());
  const plan = encodeURIComponent((scope.planId || 'default-plan').trim());
  const chapters = scope.chapterIds.map((id) => encodeURIComponent(id)).join(',');
  return `aida:twin:narrative-autogen:${project}:${plan}:${chapters}`;
}

export function shouldRunNarrativeAutogen(
  store: NarrativeAutogenStore | null | undefined,
  key: string,
  nowMs = Date.now(),
  throttleMs = DEFAULT_THROTTLE_MS,
): boolean {
  if (!store) return true;
  const raw = store.getItem(key);
  if (!raw) return true;
  const lastMs = Number(raw);
  if (!Number.isFinite(lastMs)) return true;
  return nowMs < lastMs || nowMs - lastMs > throttleMs;
}

export function markNarrativeAutogenAttempt(
  store: NarrativeAutogenStore | null | undefined,
  key: string,
  nowMs = Date.now(),
): void {
  if (!store) return;
  store.setItem(key, String(nowMs));
}
