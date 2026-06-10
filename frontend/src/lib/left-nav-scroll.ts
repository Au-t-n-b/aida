/** 侧栏菜单滚动位置 · 跨路由 AppShell 重挂载时保持，避免点击菜单后滚回顶部 */
const STORAGE_KEY = 'aida:left-nav-scroll';

let cachedScrollTop: number | null = null;

export function getLeftNavScrollTop(): number {
  if (cachedScrollTop !== null) return cachedScrollTop;
  if (typeof sessionStorage === 'undefined') return 0;
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (raw == null) return 0;
  const n = Number(raw);
  const safe = Number.isFinite(n) && n >= 0 ? n : 0;
  cachedScrollTop = safe;
  return safe;
}

export function setLeftNavScrollTop(top: number) {
  cachedScrollTop = Math.max(0, top);
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem(STORAGE_KEY, String(cachedScrollTop));
  }
}

export function restoreLeftNavScroll(el: HTMLElement | null) {
  if (!el) return;
  const top = getLeftNavScrollTop();
  el.scrollTop = top;
}
